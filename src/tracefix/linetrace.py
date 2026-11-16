"""Which of the fix's lines run: executable lines from compiled code, and fix-line coverage of the
guarding tests (ROADMAP, report only: decided by the developer, 6 Oct 2026; L2 keeps its meaning).

Lines are found by compiling head's source (never running it) and reading each code object's
line table. The tracing itself happens inside the runs, in attack_runtime's coverage plugin.
"""

import ast
import inspect
import json
import secrets
import types
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from tracefix.attack_rules import read_events
from tracefix.diffscope import DiffScope
from tracefix.guard import pr_test_candidates, source_files
from tracefix.harness import runtime_modules
from tracefix.isolation import TamperingDetected, run_checked
from tracefix.repro import REPRO_TIMEOUT_S, ReproResult, ReproStatus
from tracefix.runner import Probe, RunResult
from tracefix.workspace import Workspace


def _code_objects(code: types.CodeType) -> list[types.CodeType]:
    found, stack = [], [code]
    while stack:
        current = stack.pop()
        found.append(current)
        stack += [c for c in current.co_consts if isinstance(c, types.CodeType)]
    return found


def executable_lines(text: str, path: str, *, bodies_only: bool = False) -> frozenset[int]:
    """Lines of `text` that can run (each has an entry in a code object's line table). With
    `bodies_only`, only lines inside function bodies, without their `def` lines: what a call can
    run, as opposed to what runs when the module is imported. Empty if the text doesn't compile."""
    try:
        module = compile(text, path, "exec", dont_inherit=True)
    except (SyntaxError, ValueError, RecursionError):
        return frozenset()
    lines: set[int] = set()
    for code in _code_objects(module):
        function = bool(code.co_flags & inspect.CO_OPTIMIZED)  # module and class bodies aren't
        if bodies_only and not function:
            continue
        for _, _, line in code.co_lines():
            if line is not None and not (bodies_only and line == code.co_firstlineno):
                lines.add(line)
    return frozenset(lines)


def _span(node: ast.AST) -> set[int]:
    start, end = getattr(node, "lineno", None), getattr(node, "end_lineno", None)
    return set(range(start, end + 1)) if start is not None and end is not None else set()


def _value_lines_of(body: Sequence[ast.stmt], lines: set[int]) -> None:
    for index, node in enumerate(body):
        if isinstance(node, ast.Import | ast.ImportFrom | ast.Pass):
            continue
        if (
            index == 0
            and isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            continue  # a docstring
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            for part in [*node.decorator_list, *node.args.defaults, *node.args.kw_defaults]:
                if part is not None:
                    lines |= _span(part)
        elif isinstance(node, ast.ClassDef):
            for part in [*node.decorator_list, *node.bases, *(k.value for k in node.keywords)]:
                lines |= _span(part)
            _value_lines_of(node.body, lines)
        elif isinstance(node, ast.If | ast.While):
            lines |= _span(node.test)
            _value_lines_of([*node.body, *node.orelse], lines)
        elif isinstance(node, ast.For | ast.AsyncFor):
            lines |= _span(node.target) | _span(node.iter)
            _value_lines_of([*node.body, *node.orelse], lines)
        elif isinstance(node, ast.With | ast.AsyncWith):
            for item in node.items:
                lines |= _span(item.context_expr)
            _value_lines_of(node.body, lines)
        elif isinstance(node, ast.Try | ast.TryStar):
            for handler in node.handlers:
                if handler.type is not None:
                    lines |= _span(handler.type)
                _value_lines_of(handler.body, lines)
            _value_lines_of([*node.body, *node.orelse, *node.finalbody], lines)
        else:
            lines |= _span(node)  # an assignment or expression: a constant, a regex, a table


def import_time_value_lines(text: str) -> frozenset[int]:
    """Lines of module-level code that compute values when the module is imported: assignments
    and expressions (also in class bodies and module-level if/for/try), decorators, default
    values, base classes. Not imports, docstrings or `def`/`class` lines: changing those changes
    no value a call uses (verifier round 2: an added `import` excused nothing). Empty if the text
    doesn't parse."""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError):
        return frozenset()
    lines: set[int] = set()
    _value_lines_of(tree.body, lines)
    return frozenset(lines)


# Decorators whose removal, along with their function, changes no value other code can read:
# they only mark the function (an abstract method's mark matters only to code that names it).
_MARKERS = frozenset({"staticmethod", "classmethod", "abstractmethod", "override"})
# Names that can read a namespace without naming what they read (`getattr(cls, name)`).
DYNAMIC_LOOKUPS = frozenset({"getattr", "hasattr", "vars", "dir", "globals", "locals", "eval",
                             "exec", "__import__", "__dict__", "getmembers",
                             "__abstractmethods__"})  # fmt: skip


def _import_time_body(body: Sequence[ast.stmt]) -> list[ast.stmt]:
    """A module or class body without what runs no value at import: imports, `pass` and the
    docstring (as in import_time_value_lines)."""
    out = []
    for index, node in enumerate(body):
        if isinstance(node, ast.Import | ast.ImportFrom | ast.Pass):
            continue
        if (
            index == 0
            and isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            continue
        out.append(node)
    return out


def _header(node: ast.stmt) -> str:
    """What a `def` or `class` statement computes at import: the statement without its body."""
    shell = ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
    body = node.body if isinstance(node, shell) else []
    if isinstance(node, shell):
        node.body = []
    try:
        return ast.dump(node)
    finally:
        if isinstance(node, shell):
            node.body = body


def _marked_def(node: ast.stmt) -> str | None:
    """The name of a function whose definition computes nothing but marks: decorators from
    _MARKERS only, constant defaults, and no call in any annotation. None for anything else,
    and for a special method (`__eq__`, `__init_subclass__`, a module's `__getattr__`): Python
    calls those without any source naming them."""
    if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        return None
    if node.name.startswith("__") and node.name.endswith("__"):
        return None
    for decorator in node.decorator_list:
        name = decorator.attr if isinstance(decorator, ast.Attribute) else None
        name = decorator.id if isinstance(decorator, ast.Name) else name
        if name not in _MARKERS:
            return None
    defaults = [d for d in (*node.args.defaults, *node.args.kw_defaults) if d is not None]
    if not all(isinstance(d, ast.Constant) for d in defaults) or "Call(" in _header(node):
        return None
    return node.name


def _removed_defs(base: Sequence[ast.stmt], head: Sequence[ast.stmt], out: set[str]) -> bool:
    """Is `head` the same body as `base` at import time, but for marked functions removed (added
    to `out`)? Function bodies don't run at import, so only their headers are compared; a class
    is compared by its header and then its body, the same way."""
    left, right = _import_time_body(base), _import_time_body(head)
    i = 0
    for node in left:
        match = right[i] if i < len(right) else None
        if match is not None and _header(node) == _header(match):
            if (
                isinstance(node, ast.ClassDef)
                and isinstance(match, ast.ClassDef)
                and not _removed_defs(node.body, match.body, out)
            ):
                return False
            i += 1
        elif (name := _marked_def(node)) is not None:
            out.add(name)
        else:
            return False
    return i == len(right)


def removed_marked_defs(base: str, head: str) -> frozenset[str]:
    """The names of the functions the fix removed, when that is all it changed at import time
    in this file: no constant, decorator, default, base class or other module-level code
    changed (M11 early, twyn-317: a removed abstract method marked the next function's
    unchanged decorator as a fix line). Empty when anything else changed, or nothing was
    removed, or a side doesn't parse. Function bodies may differ: they run only when called,
    where the line tracer sees them."""
    try:
        base_tree, head_tree = ast.parse(base), ast.parse(head)
    except (SyntaxError, ValueError, RecursionError):
        return frozenset()
    found: set[str] = set()
    if not _removed_defs(base_tree.body, head_tree.body, found):
        return frozenset()
    return frozenset(found)


def dynamic_lookup(text: str) -> bool:
    """Does the code use a name that can reach a function without naming it? True if the text
    doesn't parse."""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError):
        return True
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in DYNAMIC_LOOKUPS:
            return True
        if isinstance(node, ast.Attribute) and node.attr in DYNAMIC_LOOKUPS:
            return True
    return False


@dataclass(frozen=True)
class FixLineCoverage:
    """Per test set, which of the fix's executable lines its run on head executed."""

    lines: Mapping[str, frozenset[int]]  # executable fixed lines, per changed source file
    covered: Mapping[str, Mapping[str, frozenset[int]]]  # test set -> file -> lines it ran
    runs: tuple[tuple[str, RunResult], ...]
    notes: tuple[str, ...] = ()

    def summary(self, test_set: str) -> tuple[int, int]:
        """(lines run, executable fixed lines) for one test set."""
        total = sum(len(lines) for lines in self.lines.values())
        ran = sum(
            len(lines & self.lines.get(path, frozenset()))
            for path, lines in self.covered.get(test_set, {}).items()
        )
        return ran, total


def fix_line_coverage(ws: Workspace, scope: DiffScope, repro: ReproResult) -> FixLineCoverage:
    """Run the reproduction test (if it reproduced) and the PR's test files on head with line
    tracing, and report which executable fix lines each set runs. Report only: never a verdict.
    Raises TamperingDetected like any watched run."""
    sources, notes = source_files(ws, scope)
    lines = {s.path: executable_lines(s.head, s.path) & s.fixed for s in sources}
    lines = {path: found for path, found in lines.items() if found}
    sets: list[tuple[str, list[str], dict[str, str]]] = []
    if repro.status is ReproStatus.REPRODUCED and repro.test_code is not None:
        sets.append(("repro", [repro.test_path], {repro.test_path: repro.test_code}))
    pr_files = list(pr_test_candidates(scope, ws.head))
    if pr_files:
        sets.append(("pr_test", pr_files, {}))
    covered: dict[str, dict[str, frozenset[int]]] = {}
    runs: list[tuple[str, RunResult]] = []
    if not lines:
        return FixLineCoverage(lines, covered, (), (*notes, "the fix has no executable lines"))
    problem = ws.settings.python.hypothesis_problem()  # the tracer ships in the runtime
    if problem is not None and sets:
        return FixLineCoverage(lines, covered, (), (*notes, f"not measured: {problem}"))
    for name, targets, placed in sets:
        run, found, note = _traced_run(ws, targets, placed, sorted(lines))
        runs.append((name, run))
        covered[name] = found
        if note:
            notes.append(f"{name}: {note}")
    return FixLineCoverage(lines, covered, tuple(runs), tuple(notes))


def _traced_run(
    ws: Workspace, targets: Sequence[str], placed: Mapping[str, str], files: Sequence[str]
) -> tuple[RunResult, dict[str, frozenset[int]], str]:
    module = f"tracefix_rt_{secrets.token_hex(4)}"
    probe = Probe(
        runtime_modules(module),
        (module,),
        {"TRACEFIX_TRACE": json.dumps(list(files))},
    )
    written = []
    try:
        for rel, code in placed.items():
            target = ws.head / rel
            if target.exists():
                raise TamperingDetected([f"refusing to overwrite {rel} in the copy under test"])
            target.write_text(code, encoding="utf-8", newline="\n")
            written.append(target)
        timeout = REPRO_TIMEOUT_S if placed else ws.settings.suite_timeout_s
        run = run_checked(
            ws,
            ws.head,
            list(targets),
            placed=list(placed),
            timeout_s=timeout,
            reruns=0,
            probe=probe,
        )
    finally:
        for target in written:
            target.unlink(missing_ok=True)
    events, _ = read_events(run.first.out)
    coverage = next((e for e in events if e.get("event") == "coverage"), None)
    if coverage is None:
        return run, {}, "the run reported no coverage"
    found: dict[str, frozenset[int]] = {}
    for path, numbers in (coverage.get("files") or {}).items():
        if path in files and isinstance(numbers, list):
            found[path] = frozenset(n for n in numbers if isinstance(n, int))
    note = "" if coverage.get("traced") else f"tracing was not available ({coverage.get('reason')})"
    return run, found, note
