"""The behaviour diff: the same inputs on the code before and after the fix (SPEC 2.5, Decided
in M7).

In order:
1. targets: the changed functions (attack_inputs.select_targets, functions without parameters
   too); one that is new with the fix has nothing to compare;
2. inputs, from text and code only (no model): docstring examples of base and head, literal
   calls in tests and in the issue, the fix's grid and evidence values; inside the run also type
   boundaries and Hypothesis draws;
3. a run on head generates the inputs once and calls each twice; a run on base replays the same
   literals; a run that hangs is resumed past the hung input;
4. behaviour_rules compares, tags and groups the changes and picks what the Judge sees;
5. the Judge labels the shown changes (advisory: it can only keep L3 out of reach);
6. survivor evidence: Guard's surviving mutants run on the same inputs (report only).

Every run is watched; tampering makes the stage invalid, never a verdict. Model output decides
nothing here: the inputs come from our own code, the comparison from digests our runtime computed,
and the L3 checks (`checks_gate`) read no label at all.
"""

import ast
import json
import re
import secrets
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum
from pathlib import Path
from typing import Any

from tracefix.attack_inputs import (
    Args,
    AttackTarget,
    Imports,
    Skipped,
    bind_call,
    calls_target,
    doc_examples,
    fixed_by_file,
    imports_of,
    literal_calls,
    method_args,
    refers_to,
    seeds_for,
    select_targets,
    survivors_in,
    target_params,
    test_functions,
    witness_calls,
)
from tracefix.attack_methods import (
    Definition,
    Located,
    accessor,
    bodies,
    class_defs,
    fresh_uses,
    locate,
    uses,
)
from tracefix.attack_rules import (
    STDLIB_MODULES,
    read_events,
    receiver_of,
    receiver_spec,
    shadowed_stdlib,
)
from tracefix.behaviour_rules import (
    UNOBSERVED,
    ChangeGroup,
    Comparison,
    DiffEvents,
    DocInfo,
    Evidence,
    Gate,
    Look,
    Seen,
    blind_spots,
    call_text,
    checks_gate,
    choose_shown,
    compare_target,
    describe,
    group_changes,
    l3_gate,
    read_diff_events,
)
from tracefix.diffscope import ChangeKind, DiffScope
from tracefix.guard import GuardResult, MutantStatus
from tracefix.harness import run_file, run_harness, runtime_modules
from tracefix.integrity import matches, module_of
from tracefix.isolation import TamperingDetected
from tracefix.judge import JudgeResult, JudgeStatus, label_changes
from tracefix.linetrace import import_time_value_lines
from tracefix.llm import LLMClient
from tracefix.repro import ReproResult, ReproStatus, sanitize
from tracefix.runner import Outcome, Probe, RunResult
from tracefix.sandbox import BASIC_WARNING, Level, sandbox_level
from tracefix.variant import swapped, variant_copy
from tracefix.workspace import Workspace, WorkspaceError, blob_text

DIFF_TIMEOUT_S = 120  # a safety net only: limits are counts (a normal diff run takes seconds)
DRAWS = 200  # Hypothesis draws per target (SPEC 2.5's N)
MAX_EXPLICIT = 200  # explicit inputs per target (docstring examples and test calls on top)
MAX_RESUMES = 2  # restarts after a hang, per target and side
MAX_SURVIVOR_RUNS = 20  # surviving mutants checked (report only)
RECORDED_TIMEOUT_S = 300  # the reproduction test on base with the call recorder on
CLOSED = Gate(False)
NOT_JUDGED = JudgeResult(JudgeStatus.NOT_NEEDED)


class BehaviourStatus(StrEnum):
    COMPARED = "compared"  # every target compared to the end (changes or not)
    PARTIAL = "partial"  # some compared; something was left out or did not finish
    INCONCLUSIVE = "inconclusive"  # nothing could be compared
    SKIPPED = "skipped"  # no changed function to compare
    INVALID = "invalid"  # tampering detected: no verdict at all


@dataclass(frozen=True)
class DiffTarget:
    id: str
    function: str  # dotted: module.name
    path: str
    comparison: Comparison | None = None
    finished: bool = False  # both sides' runs got through every input
    reason: str = ""  # why it was not (fully) compared
    reached: tuple[tuple[str, tuple[int, ...]], ...] = ()  # fix lines head's calls ran (report)
    hangs: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class SurvivorCheck:
    """Does a mutant that survived Guard really behave differently from the fix? Report only:
    `differs` shows inputs no test checks; `no_difference_found` hints at an equivalent mutant
    (testing can't prove that)."""

    number: int
    origin: str  # model | rule
    path: str
    line: int
    status: str  # differs | no_difference_found | not_checked
    reason: str = ""
    compared: int = 0
    examples: tuple[tuple[str, str, str], ...] = ()  # (call, the fix gives, the mutant gives)


@dataclass(frozen=True)
class BehaviourResult:
    status: BehaviourStatus
    reason: str
    groups: tuple[ChangeGroup, ...] = ()
    targets: tuple[DiffTarget, ...] = ()
    skipped: tuple[Skipped, ...] = ()
    checks: Gate = CLOSED  # L3 by deterministic checks alone
    l3: Gate = CLOSED  # the checks plus the Judge's veto: what L3 needs (with L2)
    runs: tuple[tuple[str, RunResult], ...] = ()
    isolation: Level = "basic"
    warnings: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    judge: JudgeResult = NOT_JUDGED
    survivors: tuple["SurvivorCheck", ...] = ()  # report only: never part of any verdict
    unobserved: tuple[str, ...] = UNOBSERVED  # what L3 doesn't claim: the receipt's `unchecked`

    @property
    def changes(self) -> int:
        return sum(len(g.changes) for g in self.groups)


@dataclass
class _Stage:
    ws: Workspace
    targets: list[AttackTarget]
    phase: str = "the start"
    runs: list[tuple[str, RunResult]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    hangs: dict[str, list[str]] = field(default_factory=dict)

    @property
    def by_id(self) -> dict[str, AttackTarget]:
        return {t.id: t for t in self.targets}


# --- targets and inputs ---------------------------------------------------------------------------


def _base_path(scope: DiffScope, path: str) -> str:
    renamed = {f.path: f.old_path for f in scope.files if f.old_path}
    return renamed.get(path, path)


def _base_node(ws: Workspace, scope: DiffScope, target: AttackTarget) -> ast.stmt | None:
    """The target's definition in base's file (the last one, the binding it exports), or None if
    base has no module-level definition of that name. For a method: the method its class
    exposes, if it is the same kind (else the class, which is no function: not comparable)."""
    text = blob_text(ws.repo, ws.base_sha, _base_path(scope, target.path))
    if text is None:
        return None
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError):
        return None
    found = [n for n in tree.body if (target.owner or target.name) in _bound_by(n)]
    if not found or not target.owner:
        return found[-1] if found else None
    owner = found[-1]
    if not isinstance(owner, ast.ClassDef):
        return owner
    defs = class_defs(owner, target.name)
    if not defs:
        return None if target.name not in _module_names(owner.body) else owner
    getters = [
        d
        for d in defs
        if not isinstance(d, ast.ClassDef) and accessor(d) not in ("setter", "deleter")
    ]
    exposed = len(defs) - 1 if target.kind != "property" or not getters else defs.index(getters[-1])
    located = locate(tree, target.qualname, exposed)
    if isinstance(located, Located) and located.kind == target.kind:
        return located.node
    return owner


def _inherits(owner: ast.ClassDef) -> bool:
    """The class may get a name from elsewhere: a base other than `object`, a metaclass or other
    class keyword, or attribute hooks."""
    bases = [b for b in owner.bases if not (isinstance(b, ast.Name) and b.id == "object")]
    hooks = {"__getattr__", "__getattribute__"} & _module_names(owner.body)
    return bool(bases or owner.keywords or hooks)


_STAR = "*"
_OWN_SCOPE = (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


def _binds(ws: Workspace, scope: DiffScope, target: AttackTarget) -> bool:
    """Whether base binds the target's name anywhere at module scope, in any way: inside `if`,
    `try`, `with` or `for` too, by tuple or starred assignment, a loop or `with` target, a walrus,
    or possibly through `from x import *` (verifier round 3). Then the function is not new."""
    text = blob_text(ws.repo, ws.base_sha, _base_path(scope, target.path))
    if text is None:
        return False
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError):
        return True  # can't tell: not "new"
    names = _module_names(tree.body)
    # `global name` in any function binds a module name; a module `__getattr__` (PEP 562) may
    # answer any name, like a star import (verifier round 4).
    names |= {n for node in ast.walk(tree) if isinstance(node, ast.Global) for n in node.names}
    if _STAR in names or "__getattr__" in names:
        return True
    if not target.owner:
        return target.name in names
    # A method (M7.5 plan, D7): new only if base's class never binds the name and has nothing
    # to inherit it from (a class the fix adds whole binds nothing either).
    owner = [n for n in tree.body if target.owner in _bound_by(n)]
    if not owner:
        return target.owner in names
    found = owner[-1]
    return (
        not isinstance(found, ast.ClassDef)
        or _inherits(found)
        or target.name in _module_names(found.body)
    )


def _module_names(body: Sequence[ast.stmt]) -> set[str]:
    """Every name module-level code binds, looking into compound statements but not into
    function or class bodies; "*" for a star import."""
    names: set[str] = set()
    stack: list[ast.AST] = list(body)
    while stack:
        node = stack.pop()
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.add(node.name)
            # Their bodies are not module scope; decorators, defaults and bases are.
            stack.extend(node.decorator_list)
            if isinstance(node, ast.ClassDef):
                stack.extend([*node.bases, *(k.value for k in node.keywords)])
            else:
                stack.extend([*node.args.defaults, *(d for d in node.args.kw_defaults if d)])
            continue
        if isinstance(node, _OWN_SCOPE):
            # Their own scope: a loop variable there binds no module name; a walrus inside a
            # comprehension does (PEP 572).
            names |= {n.target.id for n in ast.walk(node) if isinstance(n, ast.NamedExpr)}
            continue
        if isinstance(node, ast.Import | ast.ImportFrom):
            names |= {_STAR if a.name == "*" else (a.asname or a.name).split(".")[0]
                      for a in node.names}  # fmt: skip
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
        stack.extend(ast.iter_child_nodes(node))
    return names


def _bound_by(node: ast.stmt) -> set[str]:
    """The module-level names a statement binds: a def or class, an assignment (`parse = _impl`)
    or an import. A name base bound any other way than `def` is not new with the fix (verifier
    S1): it existed, it just can't be compared."""
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
        return {node.name}
    if isinstance(node, ast.Assign):
        return {t.id for t in node.targets if isinstance(t, ast.Name)}
    if isinstance(node, ast.AnnAssign | ast.AugAssign) and isinstance(node.target, ast.Name):
        return {node.target.id}
    if isinstance(node, ast.Import | ast.ImportFrom):
        return {(a.asname or a.name).split(".")[0] for a in node.names}
    return set()


def _finite(annotation: ast.expr) -> bool:
    if isinstance(annotation, ast.Constant):
        return annotation.value is None
    if isinstance(annotation, ast.Name):
        return annotation.id in ("bool", "None")
    if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
        return _finite(annotation.left) and _finite(annotation.right)
    if isinstance(annotation, ast.Subscript):
        name = annotation.value
        kind = name.attr if isinstance(name, ast.Attribute) else getattr(name, "id", "")
        if kind == "Literal":
            return True
        if kind in ("Optional", "Union"):
            inner = annotation.slice
            parts = inner.elts if isinstance(inner, ast.Tuple) else [inner]
            return all(_finite(p) for p in parts)
    return False


def finite_annotations(target: AttackTarget) -> bool:
    """Every parameter is annotated, in head's source, with a type whose values can all be
    listed (bool, None, Literal and unions of them). Our own check of the run's "exhausted"
    claim, which waives the input floor; an Enum can't be told from the text, so it doesn't.
    A method called on an object never counts: its object's state comes from other methods
    too (`push` before `top`), and only the constructor's inputs could be listed (developer,
    12 Oct 2026, verifier round 1 B1; replaces plan D7's constructor rule)."""
    if target.has_receiver:
        return False
    for param in target.params:
        try:
            node = ast.parse(param.annotation, mode="eval").body if param.annotation else None
        except (SyntaxError, ValueError, RecursionError):
            return False
        if node is None or not _finite(node):
            return False
    return True


def canonical(args: Args, target: AttackTarget) -> Args:
    """Arguments in the target's parameter order (a base-side example may name them in base's
    order); names the target doesn't have go last, sorted."""
    given = dict(args)
    order = list(target.arg_names)
    return (
        *((n, given[n]) for n in order if n in given),
        *sorted((n, v) for n, v in given.items() if n not in order),
    )


def _docs(target: AttackTarget, base: Definition) -> list[DocInfo]:
    """The docstring examples of head and of base, each once: "both" if the PR left it alone,
    "base" if it removed or changed it, "head" if it added it."""
    params = target_params(base, target.kind)
    base_target = replace(target, docstring=ast.get_docstring(base) or "", params=params)
    head = {(canonical(e.args, target), e.expected, e.compare): e for e in doc_examples(target)}
    old = {(canonical(e.args, target), e.expected, e.compare): e for e in doc_examples(base_target)}
    out = []
    for n, key in enumerate(dict.fromkeys([*old, *head]), 1):
        origin = "both" if key in head and key in old else "base" if key in old else "head"
        example = head.get(key) or old[key]
        quote = f"`{' '.join(example.quote.split())[:200]}`"
        out.append(DocInfo(f"{target.id}.doc{n}", target.id, key[0], origin, quote,
                           example.expected, example.compare))  # fmt: skip
    return out


def _checks(node: ast.AST) -> list[ast.stmt]:
    """The check statements of a test: each `assert`, and each `with pytest.raises(...)`, not
    looking into nested functions or classes (code that may never run)."""
    found: list[ast.stmt] = []
    stack = list(ast.iter_child_nodes(node))
    while stack:
        sub = stack.pop()
        if isinstance(sub, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda | ast.ClassDef):
            continue
        raises = isinstance(sub, ast.With) and any(
            isinstance(i.context_expr, ast.Call)
            and isinstance(i.context_expr.func, ast.Attribute)
            and i.context_expr.func.attr == "raises"
            for i in sub.items
        )
        if isinstance(sub, ast.Assert | ast.With) and (isinstance(sub, ast.Assert) or raises):
            found.append(sub)
        stack.extend(ast.iter_child_nodes(sub))
    return sorted(found, key=lambda c: c.lineno)


@dataclass(frozen=True)
class Ran:
    """What the recorded base run of the reproduction test saw: each call to a target made from
    the repro file (test node id, function, line, end line, column, end column), and for each test
    case that failed, the line of its own function where it failed."""

    calls: frozenset[tuple[str, str, int, int, int, int]] = frozenset()
    failed: tuple[tuple[str, int], ...] = ()


def _ran_on_base(stage: _Stage, prepared: "_Prepared", repro: ReproResult | None) -> Ran:
    """Run the reproduction test (if it reproduced) once more on base, watched, with the call
    recorder on. Static reading of the test can't know which calls base made or which check
    failed (verifier rounds 3 and 4); this run can. A failure counts only if base's JUnit report
    also says that test failed; a second report from the run is forged, and then nothing counts."""
    if repro is None or repro.status is not ReproStatus.REPRODUCED or not repro.test_code:
        return Ran()
    python = stage.ws.settings.python
    if python.version < (3, 11):  # code objects have no column positions before 3.11
        stage.notes.append(
            f"the reproduction test's calls are not proven on Python {python.label}: the call "
            "recorder places calls by line and column, which Python gives from 3.11 on, so none "
            "of them counts as compared"
        )
        return Ran()
    module = f"tracefix_rt_{secrets.token_hex(4)}"
    spec = {"file": repro.test_path,
            "targets": [{"path": prepared.base_paths[t.id], "name": t.qualname}
                        for t in prepared.targets]}  # fmt: skip
    probe = Probe(runtime_modules(module), (module,), {"TRACEFIX_CALLS": json.dumps(spec)})
    label = "the reproduction test before the fix, with its calls recorded"
    stage.phase = label
    # The recorder slows call-heavy tests down several times: more room than a plain repro run.
    run = run_file(stage.ws, stage.ws.base, repro.test_path, repro.test_code, RECORDED_TIMEOUT_S,
                   0, probe)  # fmt: skip
    stage.runs.append((label, run))
    events, _ = read_events(run.first.out)
    reports = [e for e in events if e.get("event") == "calls"]
    if len(reports) != 1:
        if reports:
            stage.notes.append("the recorded run reported its calls more than once: none counted")
        return Ran()
    test_module = module_of(stage.ws.base, repro.test_path)
    failed = []
    raw = reports[0].get("failed")
    for node, line in raw.items() if isinstance(raw, dict) else []:
        qualname = _qualname(str(node))
        junit = any(matches(i, test_module, qualname) for i in run.first.failed)
        if isinstance(line, int) and junit:
            failed.append((str(node), line))
    calls = set()
    for entry in reports[0].get("calls") or []:
        places = entry[2:] if isinstance(entry, list) and len(entry) == 6 else None
        if places is not None and all(isinstance(n, int) for n in places):
            calls.add((str(entry[0]), str(entry[1]), *entry[2:]))
    return Ran(frozenset(calls), tuple(sorted(failed)))


_PARAMS = re.compile(r"\[.*\]$")


def _qualname(node: str) -> str:
    """`tests/x.py::TestA::test_b[1-2]` -> `TestA.test_b`."""
    return _PARAMS.sub("", node.partition("::")[2]).replace("::", ".")


def _proven_calls(
    repro: ReproResult | None, targets: Sequence[AttackTarget], ran: Ran
) -> frozenset[frozenset[tuple[str, Args]]]:
    """The reproduction test's calls the runs vouch for: a literal call inside the check (assert,
    pytest.raises) on the line where a test case failed on base, that the recorder saw made at
    exactly that place in that same case. It ran before the fix, its check failed there, and
    head passing says the check holds after it (verifier rounds 3 and 4). Grouped by check:
    the calls of one failing assert together (round 7, S1)."""
    if not ran.failed or repro is None or not repro.test_code:
        return frozenset()
    try:
        tree = ast.parse(repro.test_code)
    except (SyntaxError, ValueError, RecursionError):
        return frozenset()
    imports = imports_of(tree)
    tests = dict(test_functions(tree))  # a name defined twice: the last one is what runs
    found = set()
    for node_id, line in ran.failed:
        in_check: set[tuple[str, Args]] = set()
        test = tests.get(_qualname(node_id))
        check = next(
            (c for c in _checks(test) if c.lineno <= line <= (c.end_lineno or c.lineno)), None
        ) if test is not None else None  # fmt: skip
        if check is None or test is None:
            continue
        for t in targets:
            for node, args in _calls_in_check(check, test, t, imports):
                place = (node.lineno, node.end_lineno, node.col_offset, node.end_col_offset)
                if (node_id, t.qualname, *place) in ran.calls:
                    in_check.add((t.id, canonical(args, t)))
        if in_check:
            found.add(frozenset(in_check))
    return frozenset(found)


def _calls_in_check(
    check: ast.stmt, test: ast.AST, target: AttackTarget, imports: Imports
) -> list[tuple[ast.expr, Args]]:
    """The literal calls of `target` inside one check, each with the node the call recorder
    places it at: the call, or for a property the attribute read. A method's object must be
    built right there or be a fresh name the test built for it (attack_methods.fresh_uses)."""
    if not target.owner:
        calls = (n for n in ast.walk(check) if isinstance(n, ast.Call))
        bound = (
            (c, bind_call(c, target.params)) for c in calls if calls_target(c, target, imports)
        )
        return [(c, args) for c, args in bound if args is not None]

    def is_owner(node: ast.expr) -> bool:
        return refers_to(node, target.owner, target, imports)

    fresh: dict[int, ast.Call] = {}
    for body in bodies(test):
        fresh.update(fresh_uses(body, is_owner))
    found = []
    for use, on in uses(check, target.name, target.kind):
        args = method_args(use, on, target, is_owner, fresh)
        if args is not None:
            found.append((use, args))
    return found


def _unseen(ws: Workspace, scope: DiffScope) -> list[str]:
    """Changes the diff cannot compare at all (verifier rounds 1 and 2), each a reason L3 is out
    of reach: a public function (dunders included) the fix removed; module-level code that
    computes a value outside top-level functions (calls use it without "running" it); a changed
    import that rebinds a name base already had; a file that doesn't parse on one side."""
    reasons = [
        f"{f.qualname}: removed by the fix (nothing can be compared)"
        for f in scope.source_functions
        if f.change is ChangeKind.REMOVED
        and _public(f.qualname.rpartition(".")[2])
        and _api_level(ws, scope, f.path, f.qualname)
    ]
    for path, lines in sorted(fixed_by_file(ws, scope).items()):
        text = blob_text(ws.repo, ws.head_sha, path)
        if text is None:
            continue
        changed = sorted((import_time_value_lines(text) & lines) - _function_lines(text))
        if changed:
            shown = ", ".join(map(str, changed[:5]))
            reasons.append(
                f"{path}: module-level code that computes a value changed (line {shown}); what "
                "uses it is not compared"
            )
        old = blob_text(ws.repo, ws.base_sha, _base_path(scope, path))
        rebound = _rebound_imports(text, old, lines)
        if rebound:
            names = ", ".join(rebound)
            reasons.append(
                f"{path}: a changed import rebinds {names}; what uses it is not compared"
            )
    reasons += [f"{path}: does not parse on one side, so it is not compared"
                for path in scope.unparseable]  # fmt: skip
    return reasons


def _api_level(ws: Workspace, scope: DiffScope, path: str, qualname: str) -> bool:
    """A top-level function, or a method of a top-level class: something callers can reach. A
    function nested in another one is part of it (its removal shows in the outer function's
    comparison: verifier round 3)."""
    parts = qualname.split(".")
    if len(parts) == 1:
        return True
    text = blob_text(ws.repo, ws.base_sha, _base_path(scope, path))
    try:
        tree = ast.parse(text or "")
    except (SyntaxError, ValueError, RecursionError):
        return True
    # Walk the qualname down from module scope (also through if/try/with); it is nested in a
    # function as soon as one of its enclosing parts is a function (verifier round 4).
    scope_nodes: list[ast.AST] = [tree]
    for part in parts[:-1]:
        found = [d for root in scope_nodes for d in _definitions(root) if d.name == part]
        if any(isinstance(d, ast.FunctionDef | ast.AsyncFunctionDef) for d in found):
            return False
        if not found:
            return True  # can't place it: report it
        scope_nodes = list(found)
    return True


def _definitions(root: ast.AST) -> list[ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef]:
    """The functions and classes defined directly in `root`'s scope, also inside if/try/with."""
    found: list[ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef] = []
    stack = list(ast.iter_child_nodes(root))
    while stack:
        node = stack.pop()
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            found.append(node)
        elif isinstance(node, ast.stmt):
            stack.extend(ast.iter_child_nodes(node))
    return found


def _public(name: str) -> bool:
    """Not private: a dunder method (`__eq__`) is public behaviour (verifier round 2)."""
    return not name.startswith("_") or (name.startswith("__") and name.endswith("__"))


def _function_lines(text: str) -> set[int]:
    """Lines of top-level functions and of the methods of top-level classes (decorators to the
    last line). Their defaults and decorators belong to the function: it is compared, new with
    the fix, or a changed function the diff already lists as not compared (verifier round 2: a
    new helper's defaults blocked L3; M7.5 plan, D7: the same for methods). Other lines of a
    class body stay module-level code."""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError):
        return set()
    lines: set[int] = set()
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)]
    for owner in (n for n in tree.body if isinstance(n, ast.ClassDef)):
        nodes += _methods(owner)
    for node in nodes:
        first = min([node.lineno, *(d.lineno for d in node.decorator_list)])
        lines |= set(range(first, (node.end_lineno or node.lineno) + 1))
    return lines


def _methods(owner: ast.ClassDef) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Every function the class body defines (also inside an `if` or `try` there), not looking
    into nested classes or functions."""
    found: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    stack: list[ast.AST] = list(owner.body)
    while stack:
        node = stack.pop()
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            found.append(node)
        elif not isinstance(node, ast.ClassDef):
            stack.extend(ast.iter_child_nodes(node))
    return found


def _rebound_imports(head: str, base: str | None, fixed: frozenset[int]) -> list[str]:
    """Names a fixed top-level import binds that base already bound (`floor as rnd` becoming
    `ceil as rnd`): code that uses them changes without changing (verifier round 2)."""
    try:
        new_tree, old_tree = ast.parse(head), ast.parse(base or "")
    except (SyntaxError, ValueError, RecursionError):
        return []
    before: dict[str, str] = {}
    for node in old_tree.body:
        before |= _what_binds(node)
    found = []
    for node in new_tree.body:
        if isinstance(node, ast.Import | ast.ImportFrom) and node.lineno in fixed:
            found += sorted(n for n, what in _what_binds(node).items()
                            if n in before and before[n] != what)  # fmt: skip
    return found


def _what_binds(node: ast.stmt) -> dict[str, str]:
    """Each name a top-level statement binds, with what it binds it to (an import's source, or
    the statement's own text for anything else)."""
    if isinstance(node, ast.Import):
        # `import a.b` binds `a`, the same module `import a` binds (verifier round 3).
        found = {}
        for a in node.names:
            module = a.name if a.asname else a.name.split(".")[0]
            found[a.asname or module] = f"import {module}"
        return found
    if isinstance(node, ast.ImportFrom):
        source = f"from {'.' * node.level}{node.module or ''}"
        return {(a.asname or a.name): f"{source} import {a.name}" for a in node.names}
    return dict.fromkeys(_bound_by(node), ast.dump(node))


@dataclass(frozen=True)
class _Prepared:
    targets: list[AttackTarget]
    base_paths: dict[str, str]
    specs: dict[str, dict[str, Any]]  # the head run's target spec, per target
    evidence: Evidence
    blockers: list[str]  # changed functions the diff cannot examine: L3 is out of reach
    new: list[Skipped]  # functions the fix added: nothing to compare
    new_targets: list[AttackTarget]  # the same, to check base doesn't bind them at run time


def _prepare(
    ws: Workspace,
    scope: DiffScope,
    targets: Sequence[AttackTarget],
    repro: ReproResult | None,
    issue: str,
    guard: GuardResult | None,
) -> _Prepared:
    fixed = fixed_by_file(ws, scope)
    kept: list[AttackTarget] = []
    blockers: list[str] = []
    new: list[Skipped] = []
    docs: dict[str, list[DocInfo]] = {}
    added = {(f.path, f.qualname) for f in scope.source_functions if f.change is ChangeKind.ADDED}
    for t in targets:
        node = _base_node(ws, scope, t)
        if isinstance(node, Definition) and isinstance(node, ast.AsyncFunctionDef) == t.is_async:
            kept.append(t)
            docs[t.id] = _docs(t, node)
        elif isinstance(node, Definition):
            # Both sides' calls are awaited, so the values alone would hide the change callers
            # see: a coroutine where there was a value, or the reverse (M11 early).
            was = "a plain function" if t.is_async else "async"
            blockers.append(f"{t.qualname}: before the fix it was {was}")
        elif (
            node is None
            and (t.path, t.qualname) in added
            and not t.via
            and not _binds(ws, scope, t)
        ):
            # Only diffscope's word makes a function new (verifier round 2, X1): a def inside
            # `try:` or `if:` in base is a changed function, not a new one.
            new.append(Skipped(t.path, t.qualname, "new with the fix: nothing to compare"))
        elif t.owner:
            blockers.append(
                f"{t.qualname}: before the fix it was not a {t.kind} defined in class {t.owner}"
            )
        else:
            blockers.append(f"{t.name}: before the fix it was not a plain module-level function")
    by_id = {t.id: t for t in kept}
    calls = witness_calls(ws, scope, kept, repro)
    issue_calls = {t.id: literal_calls(issue, t) for t in kept}
    # Only seeds our own code vouches for (verifier rounds 1 and 5): our rule mutants, not the
    # model's; nothing from the reproduction test or its attempts.
    rule_guard = replace(guard, mutants=()) if guard is not None else None
    stdlib = frozenset(STDLIB_MODULES) - shadowed_stdlib(ws.pristine[ws.head])
    specs: dict[str, dict[str, Any]] = {}
    for t in kept:
        head = blob_text(ws.repo, ws.head_sha, t.path) or ""
        # No seeds from the reproduction test: its values are a model's (round 5, S5).
        seeds = seeds_for(t, head, fixed, issue, None, survivors_in(rule_guard, t.path))
        candidates: dict[str, list[dict[str, object]]] = {}
        for seed in seeds.seeds:
            candidates.setdefault(seed.param, []).append(
                {"value": seed.value, "compared": seed.compared}
            )
        # A method's typical objects: the ones its tests, docstrings and the issue build (none
        # of the model's, as for any input here: M7.5 plan, D7).
        inputs = [*(c.args for c in calls if c.target == t.id),
                  *(d.args for d in docs[t.id]), *issue_calls[t.id]]  # fmt: skip
        objects = list(dict.fromkeys(o for a in inputs if (o := receiver_of(a, t)) is not None))
        method = receiver_spec(t, objects, stdlib)
        if t.has_receiver:
            method["vouched"] = objects
        specs[t.id] = {
            **method,
            "id": t.id,
            "path": t.path,
            "name": t.name,
            "async": t.is_async,
            "module_candidates": list(t.module_candidates),
            "docs": [
                {
                    "id": d.id,
                    "args": dict(d.args),
                    "example_expected": d.expected,
                    "compare": d.compare,
                }
                for d in docs[t.id]
            ],
            "witnesses": [
                {"id": c.id, "args": dict(c.args), "advisory": c.advisory, "repro": c.repro}
                for c in calls
                if c.target == t.id
            ],
            "examples": [
                *({"phase": e.phase, "args": dict(e.args)} for e in seeds.examples),
                *({"phase": "evidence", "args": dict(a)} for a in issue_calls[t.id]),
            ],
            "candidates": candidates,
        }

    def called(kind: str) -> frozenset[tuple[str, Args]]:
        return frozenset(
            (c.target, canonical(c.args, by_id[c.target]))
            for c in calls
            if (kind == "pr" and c.advisory)
            or (kind == "untouched" and not c.repro and not c.advisory)
        )

    evidence = Evidence(
        repro=frozenset(),  # filled in by our own run: _ran_on_base
        issue=frozenset(
            (tid, canonical(a, by_id[tid])) for tid, found in issue_calls.items() for a in found
        ),
        witnesses=called("untouched"),
        pr_tests=called("pr"),
        docs={d.id: d for found in docs.values() for d in found},
    )
    base_paths = {t.id: _base_path(scope, t.path) for t in kept}
    new_names = {(n.path, n.function) for n in new}
    new_targets = [t for t in targets if (t.path, t.qualname) in new_names]
    return _Prepared(kept, base_paths, specs, evidence, blockers, new, new_targets)


# --- the runs -------------------------------------------------------------------------------------


@dataclass
class _Side:
    """One side's runs: what they reported, the inputs that hung, the targets left unfinished."""

    events: DiffEvents = field(default_factory=DiffEvents)
    hung: dict[str, set[int]] = field(default_factory=dict)
    unfinished: set[str] = field(default_factory=set)

    def answers(self, tid: str) -> dict[int, Seen]:
        seen = dict(self.events.seen.get(tid, {}))
        for index in self.hung.get(tid, ()):
            seen.setdefault(index, Seen(hung=True))
        return seen


def _harness(
    stage: _Stage, tree: Path, plan: Mapping[str, Any], label: str, swapped_in: Sequence[str]
) -> tuple[list[dict[str, Any]], RunResult]:
    stage.phase = label
    events, bad, run = run_harness(stage.ws, tree, "diff", plan, DIFF_TIMEOUT_S, swapped_in)
    stage.runs.append((label, run))
    if bad:
        stage.notes.append(f"{label}: {bad} unreadable lines in the run's report were ignored")
    return events, run


def _int(value: object) -> int:
    return value if isinstance(value, int) and value >= 0 else 0


def _run_side(
    stage: _Stage,
    tree: Path,
    plan: dict[str, Any],
    label: str,
    side: _Side,
    swapped_in: Sequence[str] = (),
    max_resumes: int | None = None,
) -> None:
    """Every target's inputs on one side, into `side`, resumed past a hung input (each target at
    most MAX_RESUMES times; then it is given up and stays unfinished). What a run reported before
    an error stays in `side`. `swapped_in`: files Tracefix put into this copy (a mutant)."""
    resumes: dict[str, int] = {}
    allowed = MAX_RESUMES if max_resumes is None else max_resumes
    current: dict[str, Any] | None = plan
    for attempt in range((MAX_RESUMES + 1) * len(plan["targets"]) + 1):
        if current is None or not current["targets"]:
            return
        name = label if attempt == 0 else f"{label} (resumed {attempt})"
        events, run = _harness(stage, tree, current, name, swapped_in)
        read_diff_events(events, stage.by_id, side.events)
        done = sum(e.get("event") == "done" for e in events)
        if done and (done > 1 or run.outcome is not Outcome.PASSED):
            # A finished run ends with one "done" and a passing test; anything else means code in
            # the run wrote the line itself (as in Break My Fix): nothing in it counts as done.
            stage.notes.append(f"{name} reported it finished but ended {run.outcome}: not trusted")
            side.unfinished.update(t["id"] for t in current["targets"])
            return
        if done:
            return
        if run.outcome is not Outcome.TIMEOUT:
            tail = sanitize(run.first.output, stage.ws).strip()[-300:]
            stage.notes.append(f"{name} ended {run.outcome} before it finished: {tail}")
            side.unfinished.update(t["id"] for t in current["targets"])
            return
        current = _resumed(stage, tree, current, events, side, resumes, allowed, name, swapped_in)
    if current is not None:
        side.unfinished.update(t["id"] for t in current["targets"])


def _resumed(
    stage: _Stage,
    tree: Path,
    plan: dict[str, Any],
    events: Sequence[Mapping[str, Any]],
    side: _Side,
    resumes: dict[str, int],
    allowed: int,
    name: str,
    swapped_in: Sequence[str],
) -> dict[str, Any] | None:
    """After a run the time limit killed: the plan for the rest of it. Finished targets are
    dropped. The input that was running is run once more on its own: killed again, it hangs (a
    change), and its target is replayed from the next input (on head from the inputs it already
    listed, so they are generated only once); if it returns, the run only ran out of time, and its
    target stays unfinished, with nothing called hung (verifier round 11: resuming mid-way left
    the two sides with different module data). None if there is nothing to point at."""
    calling = [e for e in events if e.get("event") == "calling" and e.get("target") in stage.by_id]
    last = calling[-1] if calling else None
    if last is None or str(last["target"]) in side.events.ended:
        # It hung outside any call (loading a module, generating inputs): blame the first target
        # that never ended, give it up, and go on with the others (verifier S6).
        done = side.events.ended | set(side.events.errors)
        left = [t["id"] for t in plan["targets"] if t["id"] not in done]
        if not left:
            return None
        side.unfinished.add(left[0])
        stage.hangs.setdefault(left[0], []).append(
            "the run hung before this function's calls (loading it or making its inputs)"
        )
        rest = [t for t in plan["targets"] if t["id"] in left[1:]]
        return {**plan, "targets": rest}
    tid, index = str(last["target"]), _int(last.get("index"))
    alone = _replay(plan, side, tid, index, stage, only=True)
    if alone is None:
        side.unfinished.add(tid)
        return _replay(plan, side, tid, None, stage)
    _, run = _harness(stage, tree, alone, f"{name} (input {index} of {tid} alone)", swapped_in)
    if run.outcome is not Outcome.TIMEOUT:
        side.unfinished.add(tid)
        stage.notes.append(
            f"{tid}: the run ran out of time at input {index}; it returns when run alone, so "
            "nothing hangs, but the comparison did not finish"
        )
        return _replay(plan, side, tid, None, stage)
    side.hung.setdefault(tid, set()).add(index)
    resumes[tid] = resumes.get(tid, 0) + 1
    shown = str(last.get("input", ""))[:200]
    stage.hangs.setdefault(tid, []).append(f"the call with {shown} did not return")
    if resumes[tid] > allowed:
        side.unfinished.add(tid)
        stage.hangs[tid].append(f"gave up after {resumes[tid] - 1} resumes")
        return _replay(plan, side, tid, None, stage)
    return _replay(plan, side, tid, index + 1, stage)


def _replay(
    plan: dict[str, Any],
    side: _Side,
    tid: str,
    start: int | None,
    stage: _Stage,
    only: bool = False,
) -> dict[str, Any] | None:
    """The plan for the rest of a killed run: `tid` from input `start` (None: left out), the
    targets not yet finished as they were; with `only`, just `tid`'s input `start`. None if
    `tid`'s inputs can't be replayed (head listed fewer than it said)."""
    targets = []
    starts = dict(plan.get("start", {}))
    for spec in plan["targets"]:
        t = spec["id"]
        if t in side.events.ended or t in side.events.errors or (only and t != tid):
            continue
        if t != tid:
            targets.append(spec)
            continue
        if start is None:
            continue
        listed = side.events.inputs.get(t, [])
        if "inputs" not in spec and len(listed) != side.events.stats.get(t, {}).get("count"):
            if not only:
                side.unfinished.add(t)
            stage.hangs.setdefault(t, []).append("its inputs were not all listed: not replayed")
            if only:
                return None
            continue
        inputs = spec.get("inputs") or [{"phase": i.phase, "args": dict(i.args)} for i in listed]
        targets.append({**spec, "inputs": inputs})
        starts[t] = start
    stops = {tid: start + 1} if only and start is not None else {}
    return {**plan, "targets": targets, "start": starts, "stop": stops}


# --- the stage ------------------------------------------------------------------------------------


def _blocking(skipped: Sequence[Skipped]) -> list[str]:
    """Changed functions the diff can't call: L3 can't vouch for code it never compared."""
    return [f"{s.function}: not compared ({s.reason})" for s in skipped]


def _target_reports(
    stage: _Stage,
    prepared: _Prepared,
    head: _Side,
    base: _Side,
) -> tuple[list[DiffTarget], list[tuple[str, Comparison]], list[Any], list[str]]:
    reports: list[DiffTarget] = []
    comparisons: list[tuple[str, Comparison]] = []
    changes: list[Any] = []
    incomplete: list[str] = []
    looks: dict[str, Look] = {}
    for t in prepared.targets:
        module = head.events.modules.get(t.id, t.module_candidates[0])
        function = f"{module}.{t.qualname}"
        listed = head.events.inputs.get(t.id, [])
        stats = head.events.stats.get(t.id, {})
        reason = ""
        if t.id in head.events.errors:
            reason = f"it could not be loaded after the fix: {head.events.errors[t.id]}"
        elif t.id in base.events.errors:
            reason = f"it could not be loaded before the fix: {base.events.errors[t.id]}"
        elif _int(stats.get("count")) != len(listed):
            reason = "the run's list of inputs was cut short"
        finished = (
            not reason
            and t.id in head.events.ended
            and t.id in base.events.ended
            and t.id not in head.unfinished | base.unfinished
        )
        if not reason and not finished:
            reason = "the comparison did not finish"
        wrote = head.events.wrote.get(t.id) or base.events.wrote.get(t.id)
        if not reason and wrote:
            # What a function writes to files is not compared (developer, 8 Oct 2026, after
            # verifier round 11): that it wrote anything keeps L3 out of reach for it.
            reason = f"it changed files in the copy ({wrote}): what it writes is not compared"
        comparison = None
        if listed and t.id not in head.events.errors:
            comparison, found = compare_target(
                t.id,
                listed,
                head.answers(t.id),
                base.answers(t.id),
                prepared.evidence,
                dropped=_int(stats.get("dropped")),
                # The run's claim, and our own reading of the annotations (verifier round 2, N-a).
                exhausted=stats.get("exhausted") is True and finite_annotations(t),
            )
            comparisons.append((t.qualname, comparison))
            changes += found
            looks[t.id] = (listed, head.answers(t.id), base.answers(t.id))
        if reason:
            incomplete.append(f"{t.qualname}: {reason}")
        reached = tuple(
            (p, tuple(sorted(ns))) for p, ns in sorted(head.events.reached.get(t.id, {}).items())
        )
        notes = (*head.events.notes.get(t.id, ()), *base.events.notes.get(t.id, ()))
        reports.append(DiffTarget(t.id, function, t.path, comparison, finished, reason, reached,
                                  tuple(stage.hangs.get(t.id, ())), notes))  # fmt: skip
    by_id = {t.id: t for t in prepared.targets}
    for tid, args in blind_spots(prepared.evidence.checks, looks):
        incomplete.append(
            f"{by_id[tid].qualname}: the reproduction test shows {call_text(by_id[tid], args)} "
            "changed with the fix, but the comparison saw no difference in that check"
        )
    return reports, comparisons, changes, incomplete


def _status(
    comparisons: Sequence[tuple[str, Comparison]], incomplete: Sequence[str], changed: int
) -> tuple[BehaviourStatus, str]:
    compared = sum(c.compared for _, c in comparisons)
    if not compared:
        why = incomplete[0] if incomplete else "no input could be compared"
        return BehaviourStatus.INCONCLUSIVE, f"nothing was compared: {why}"
    summary = (
        f"{compared} input(s) compared on {len(comparisons)} function(s): {changed} changed "
        "with the fix"
    )
    if incomplete:
        return BehaviourStatus.PARTIAL, f"{summary}; not complete: {incomplete[0]}"
    return BehaviourStatus.COMPARED, summary


def _compare_sides(
    stage: _Stage, ws: Workspace, scope: DiffScope, prepared: _Prepared, head: _Side, base: _Side
) -> None:
    """The head run (inputs generated once), then the base run replaying them."""
    head_plan = {
        "mode": "diff",
        "generate": True,
        "draws": DRAWS,
        "max_explicit": MAX_EXPLICIT,
        "fixed": {p: sorted(n) for p, n in fixed_by_file(ws, scope).items()},
        "targets": [prepared.specs[t.id] for t in prepared.targets],
    }
    _run_side(stage, ws.head, head_plan, "the behaviour diff on the fixed code", head)
    base_targets = [
        {
            **prepared.specs[t.id],
            "path": prepared.base_paths[t.id],
            "inputs": [
                {"phase": i.phase, "args": dict(i.args)} for i in head.events.inputs.get(t.id, [])
            ],
        }
        for t in prepared.targets
        if head.events.inputs.get(t.id)
    ]
    absent = [
        {"path": _base_path(scope, t.path), "name": t.name, "owner": t.owner,
         "module_candidates": list(t.module_candidates)}
        for t in prepared.new_targets
    ]  # fmt: skip
    base_plan = {"mode": "diff", "fixed": {}, "targets": base_targets, "absent": absent}
    _run_side(stage, ws.base, base_plan, "the behaviour diff before the fix", base)


def _survivors(
    stage: _Stage, prepared: _Prepared, head: _Side, guard: GuardResult
) -> list[SurvivorCheck]:
    """Guard's surviving mutants (model and rule), each run on head's inputs in one extra copy of
    head with the mutant's file swapped in, compared with what the fix itself gave."""
    survivors = [
        r.mutant for r in (*guard.mutants, *guard.rule_mutants) if r.status is MutantStatus.SURVIVED
    ]
    out: list[SurvivorCheck] = []
    if not survivors:
        return out
    with variant_copy(stage.ws, stage.ws.head_sha, "head") as tree:
        for m in survivors[:MAX_SURVIVOR_RUNS]:
            mine = [
                t for t in prepared.targets if t.path == m.path and head.events.inputs.get(t.id)
            ]
            if not mine:
                out.append(SurvivorCheck(m.number, m.origin, m.path, m.line, "not_checked",
                                         "no compared function in its file"))  # fmt: skip
                continue
            plan = {"mode": "diff", "fixed": {}, "targets": [
                {**prepared.specs[t.id], "inputs": [{"phase": i.phase, "args": dict(i.args)}
                                                    for i in head.events.inputs[t.id]]}
                for t in mine]}  # fmt: skip
            side = _Side()
            with swapped(tree, {m.path: m.text.encode("utf-8")}):
                label = f"the behaviour diff on surviving mutant {m.number}"
                # No resumes: report-only time stays bounded (verifier round 2, N-c).
                _run_side(stage, tree, plan, label, side, swapped_in=[m.path], max_resumes=0)
            out.append(_survivor_check(m.number, m.origin, m.path, m.line, mine, head, side))
    if len(survivors) > MAX_SURVIVOR_RUNS:
        stage.notes.append(
            f"only {MAX_SURVIVOR_RUNS} of {len(survivors)} surviving mutants checked"
        )
    return out


def _survivor_check(
    number: int,
    origin: str,
    path: str,
    line: int,
    targets: Sequence[AttackTarget],
    head: _Side,
    mutant: _Side,
) -> SurvivorCheck:
    compared = 0
    examples: list[tuple[str, str, str]] = []
    for t in targets:
        found, changes = compare_target(
            t.id, head.events.inputs[t.id], mutant.answers(t.id), head.answers(t.id), Evidence()
        )
        compared += found.compared
        for c in changes[: 3 - len(examples)]:
            examples.append((call_text(t, c.args), describe(c.before), describe(c.after)))
    if examples:
        status, reason = "differs", "it behaves differently, and no test noticed"
    elif any(t.id in mutant.unfinished or t.id not in mutant.events.ended for t in targets):
        # A run that crashed or hung part way says nothing about equivalence (verifier N1).
        status, reason = "not_checked", "the run on the mutant did not finish"
    elif compared:
        status, reason = "no_difference_found", f"no difference in {compared} inputs"
    else:
        status, reason = (
            "not_checked",
            next(
                (mutant.events.errors[t.id] for t in targets if t.id in mutant.events.errors),
                "no input could be compared",
            ),
        )
    return SurvivorCheck(number, origin, path, line, status, reason, compared, tuple(examples))


def behaviour_diff(
    ws: Workspace,
    scope: DiffScope,
    repro: ReproResult | None,
    issue: str,
    client: LLMClient,
    guard: GuardResult | None = None,
) -> BehaviourResult:
    """Compare the changed functions on base and on head (SPEC 2.5). Runs whatever the earlier
    stages found; never raises for problems in the repo. `client` is for the Judge."""
    level = sandbox_level()
    warnings = ((BASIC_WARNING,) if level == "basic" else ()) + tuple(ws.notes)
    issue = issue.replace("\r\n", "\n").strip()
    targets, skipped, notes = select_targets(ws, scope, allow_no_params=True, cut_is_skipped=True)
    problem = ws.settings.python.hypothesis_problem()
    if targets and problem is not None:  # its inputs come from Hypothesis, inside the run
        gate = Gate(False, ("the behaviour diff could not run",))
        return BehaviourResult(BehaviourStatus.INCONCLUSIVE,
                               f"the behaviour diff can't run in the project's Python: {problem}",
                               skipped=tuple(skipped), checks=gate, l3=gate, isolation=level,
                               warnings=warnings, notes=tuple(notes))  # fmt: skip
    prepared = _prepare(ws, scope, targets, repro, issue, guard)
    skipped_all = (*skipped, *prepared.new)
    blockers = [*_blocking(skipped), *prepared.blockers, *_unseen(ws, scope)]
    if not prepared.targets:
        reason = "the fix changes no function the behaviour diff can call"
        if skipped_all:
            reason += f" ({'; '.join(f'{s.function}: {s.reason}' for s in skipped_all[:3])})"
        gate = Gate(False, (*blockers, "no changed function was compared"))
        return BehaviourResult(BehaviourStatus.SKIPPED, reason, skipped=skipped_all, checks=gate,
                               l3=gate, isolation=level, warnings=warnings,
                               notes=tuple(notes))  # fmt: skip
    stage = _Stage(ws, prepared.targets, notes=list(notes))
    head, base = _Side(), _Side()

    def invalid(exc: TamperingDetected) -> BehaviourResult:
        # Never a verdict: the stage is invalid, whatever the runs said (Decided in M3.5).
        gate = Gate(False, ("tampering detected",))
        return BehaviourResult(BehaviourStatus.INVALID, f"during {stage.phase}: {exc}",
                               skipped=skipped_all, checks=gate, l3=gate, runs=tuple(stage.runs),
                               isolation=level, warnings=warnings,
                               notes=tuple(stage.notes))  # fmt: skip

    try:
        ran = _ran_on_base(stage, prepared, repro)
        proven = _proven_calls(repro, prepared.targets, ran)
        evidence = replace(prepared.evidence, repro=frozenset().union(*proven), checks=proven)
        prepared = replace(prepared, evidence=evidence)
        _compare_sides(stage, ws, scope, prepared, head, base)
    except TamperingDetected as exc:
        return invalid(exc)
    except (OSError, WorkspaceError, RecursionError) as exc:
        # What the runs reported before the error is kept: a change found stays found.
        stage.notes.append(
            f"the behaviour diff could not finish {stage.phase}: {type(exc).__name__}: {exc}"
        )
        head.unfinished.update(t.id for t in prepared.targets)
    reports, comparisons, changes, incomplete = _target_reports(stage, prepared, head, base)
    incomplete = [*blockers, *incomplete]
    incomplete += [
        f"{t.qualname}: base binds this name when it runs, so it is not new with the fix"
        for t in prepared.new_targets
        for path, name in sorted(base.events.bound)
        if name == t.name and path == _base_path(scope, t.path)
    ]
    groups, all_shown = choose_shown(group_changes(changes))
    checks = checks_gate(incomplete, comparisons, groups, all_shown)
    survivors: list[SurvivorCheck] = []
    if guard is not None:  # before the Judge: tampering found here would waste its answer
        try:
            survivors = _survivors(stage, prepared, head, guard)
        except TamperingDetected as exc:  # report only, but tampering is never shrugged off
            return invalid(exc)
        except (OSError, WorkspaceError, RecursionError) as exc:  # report only: a note
            stage.notes.append(f"the survivor check stopped: {type(exc).__name__}: {exc}")
    judge = label_changes(ws, scope, issue, prepared.targets, groups, client)
    l3 = l3_gate(checks, groups, judge.by_id)
    status, reason = _status(comparisons, incomplete, len(changes))
    return BehaviourResult(
        status,
        reason,
        tuple(groups),
        tuple(reports),
        skipped_all,
        checks,
        l3,
        tuple(stage.runs),
        level,
        warnings,
        tuple(stage.notes),
        judge,
        tuple(survivors),
    )
