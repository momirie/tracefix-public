"""Integrity candidate rules (SPEC 2.7, Decided in M5): pure, deterministic, no runs.

Reads the base and head text of what a fix changed and lists *candidates*: places where the PR may
have weakened its tests or hard-coded the reported example. A candidate is never a verdict by
itself; integrity.py runs the old tests (or the code without the hard-coded branch) and only a
confirmed candidate becomes a flag (Decided in M5 by the developer).

- Test files: deleted tests, removed or weakened checks, changed expected values (report only),
  new skips, broadened `pytest.raises`, changed test collection (report only).
- Source files: equality tests on a new literal that also appears in the evidence (repro test,
  PR tests, issue text), on the fix's changed lines: special-casing.
- Both: newly added `# pragma: no cover / no mutate / no branch` markers (report only).
"""

import ast
import configparser
import re
import tomllib
from collections import Counter
from collections.abc import Callable, Iterable, Iterator, Sequence, Set
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal, TypeVar

from tracefix.repro import called_name

CandidateKind = Literal[
    "deleted_test", "removed_assert", "weakened_assert", "changed_expectation", "added_skip",
    "broadened_raises", "collection_changed", "special_case", "added_pragma",
]  # fmt: skip
Value = int | float | complex | str | bytes

# Kinds the "old tests, new code" run can confirm (a confirmed one becomes a flag).
CONFIRMABLE: frozenset[CandidateKind] = frozenset(
    {"deleted_test", "removed_assert", "weakened_assert", "added_skip", "broadened_raises"}
)
# Equality-like checks: anything else replacing one of these is weaker.
STRONG_OPS = frozenset({
    "Eq", "Is", "assertEqual", "assertIs", "assertListEqual", "assertTupleEqual",
    "assertDictEqual", "assertSetEqual", "assertSequenceEqual", "assertMultiLineEqual",
    "assertCountEqual", "assertAlmostEqual",
})  # fmt: skip
EQUALITY_OPS = (ast.Eq, ast.NotEq, ast.Is, ast.IsNot, ast.In, ast.NotIn)
RAISES_NAMES = frozenset({"raises", "warns", "assertRaises", "assertRaisesRegex", "assertWarns",
                          "assertWarnsRegex"})  # fmt: skip
SKIP_MARKS = frozenset({"skip", "skipif", "xfail", "skipIf", "skipUnless", "expectedFailure"})
SKIP_CALLS = frozenset({"skip", "xfail", "importorskip", "skipTest"})
BROAD_EXCEPTIONS = frozenset({"Exception", "BaseException"})
COLLECTION_NAMES = frozenset({"collect_ignore", "collect_ignore_glob"})
COLLECTION_HOOKS = frozenset({"pytest_ignore_collect", "pytest_collection_modifyitems",
                              "pytest_deselected", "pytest_collect_file"})  # fmt: skip
COLLECTION_OPTIONS = ("testpaths", "norecursedirs", "python_files", "python_classes",
                      "python_functions")  # fmt: skip
HIDING_ADDOPTS = re.compile(r"(?:^|\s)(?:--deselect|--ignore(?:-glob)?|-k|-p\s*no:)")
PRAGMA = re.compile(r"#\s*pragma:\s*no\s+(?:cover|mutate|branch)\b", re.IGNORECASE)
TRIVIAL: frozenset[object] = frozenset({0, 1, -1, "", b""})  # also 0.0, 1.0, -1.0 (same hash)
MIN_STRING = 2


@dataclass(frozen=True)
class Candidate:
    kind: CandidateKind
    file: str
    line: int  # first line, in the file named by `side`
    detail: str  # the code involved, as written
    side: Literal["base", "head"] = "head"
    end_line: int | None = None  # last line of the code involved (same side)
    test: str | None = None  # qualname of the test it is in ("TestX.test_y"); None: whole file
    literal: Value | None = None  # special_case: the hard-coded value
    hard_coded: bool = False  # special_case: the branch returns a literal (it may be confirmed)
    branch: tuple[int, int] | None = None  # special_case: (line, col) of the branch, head side
    # Only a failure located on line..end_line of the base file confirms it (the check itself
    # failed); otherwise any failure of the test does (a deleted test, a skip, a broader raises).
    pinned: bool = False


@dataclass(frozen=True)
class SourceText:
    """One changed Python file: head text (None if deleted), base text (None if added), and the
    head lines the fix added or changed."""

    path: str
    head: str | None
    base: str | None
    fixed: frozenset[int] = frozenset()


def parse(text: str | None) -> ast.Module | None:
    if text is None:
        return None
    try:
        return ast.parse(text)
    except (SyntaxError, ValueError, RecursionError):
        return None


def _dump(node: ast.AST) -> str:
    return ast.dump(node, include_attributes=False)


def _segment(text: str, node: ast.AST) -> str:
    return ast.get_source_segment(text, node) or ast.unparse(node)


def _end(node: ast.AST) -> int:
    end = getattr(node, "end_lineno", None)
    return end if isinstance(end, int) else int(getattr(node, "lineno", 0))


# --- tests in a file (pytest's default naming) ----------------------------------------------


@dataclass(frozen=True)
class _Test:
    qualname: str
    node: ast.FunctionDef | ast.AsyncFunctionDef
    classes: tuple[ast.ClassDef, ...]  # enclosing Test* classes, outermost first


def _test_class(node: ast.ClassDef) -> bool:
    """pytest collects `Test*` classes, and unittest.TestCase subclasses whatever their name."""
    bases = {b.attr if isinstance(b, ast.Attribute) else getattr(b, "id", "") for b in node.bases}
    return node.name.startswith("Test") or any(b.endswith("TestCase") for b in bases)


def _tests(tree: ast.Module) -> dict[str, _Test]:
    """Test functions as pytest collects them by default: `test*` functions at module level and
    `test*` methods of test classes (nested classes too)."""
    found: dict[str, _Test] = {}

    def visit(body: Sequence[ast.stmt], prefix: str, classes: tuple[ast.ClassDef, ...]) -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("test"):
                    found.setdefault(prefix + node.name, _Test(prefix + node.name, node, classes))
            elif isinstance(node, ast.ClassDef) and _test_class(node):
                visit(node.body, f"{prefix}{node.name}.", (*classes, node))

    visit(tree.body, "", ())
    return found


def _body_key(test: _Test) -> str:
    return "|".join(_dump(s) for s in test.node.body)


# --- the checks inside one test --------------------------------------------------------------


@dataclass(frozen=True)
class _Check:
    key: str  # identity in the multiset: the check and where it sits, positions ignored
    code: str  # the check alone (a check moved under `if False:` keeps its code, not its key)
    subject: str | None  # what it checks (the dumped left-hand side); None: nothing to pair on
    op: str  # "Eq", "truthy", "assertEqual", "raises", ...
    node: ast.AST
    text: str
    named: bool = False  # the subject is a bare name (`result`): it says nothing about the test


def _assert_parts(node: ast.Assert) -> tuple[ast.AST, str]:
    test = node.test
    if isinstance(test, ast.Compare) and len(test.ops) == 1:
        return test.left, type(test.ops[0]).__name__
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        return test.operand, "falsy"
    return test, "chain" if isinstance(test, ast.Compare) else "truthy"


def _check_of(node: ast.AST, text: str, context: str) -> _Check | None:
    about: ast.AST | None
    if isinstance(node, ast.Assert):
        about, op = _assert_parts(node)
    elif (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
          and isinstance(node.value.func, ast.Attribute)
          and node.value.func.attr.startswith(("assert", "fail"))):  # fmt: skip
        about, op = (node.value.args[0] if node.value.args else None), node.value.func.attr
    elif isinstance(node, ast.Call) and called_name(node) in RAISES_NAMES:
        code = _dump(node)
        return _Check(f"{context}|{code}", code, "raises", "raises", node, _segment(text, node))
    else:
        return None
    code, subject = _dump(node), (None if about is None else _dump(about))
    return _Check(f"{context}|{code}", code, subject, op, node, _segment(text, node),
                  isinstance(about, ast.Name))  # fmt: skip


# Statements after which the rest of a block never runs. (A new skip call is an added_skip of
# its own, so it does not also mark the checks after it.)
_ENDS_BLOCK = (ast.Return, ast.Raise, ast.Continue, ast.Break)


def _checks(test: _Test, text: str) -> list[_Check]:
    """Every assert statement, unittest `self.assert*(...)` call and `with pytest.raises(...)`
    (or warns / assertRaises) item in the test body, nested blocks included. Each check's key
    records where it sits: the conditions, `with` items and `try` blocks around it, and whether
    it comes after a `return` (or raise, skip, ...) in its block, so `with suppress(...)`,
    `if False:` or an early return around an old check changes its key."""
    found: list[_Check] = []

    def visit(body: Sequence[ast.stmt], context: str) -> None:
        ended = False
        for stmt in body:
            here = context + ("/after-exit" if ended else "")
            check = _check_of(stmt, text, here)
            if check is not None:
                found.append(check)
            elif isinstance(stmt, (ast.With, ast.AsyncWith)):
                raising = [c for i in stmt.items if (c := _check_of(i.context_expr, text, here))]
                found.extend(raising)
                others = [i.context_expr for i in stmt.items
                          if not any(c.node is i.context_expr for c in raising)]  # fmt: skip
                visit(stmt.body, f"{here}/with({','.join(_dump(o) for o in others)})")
            elif isinstance(stmt, (ast.If, ast.While)):
                visit(stmt.body, f"{here}/if({_dump(stmt.test)})")
                visit(stmt.orelse, f"{here}/else({_dump(stmt.test)})")
            elif isinstance(stmt, (ast.For, ast.AsyncFor)):
                visit(stmt.body, f"{here}/for({_dump(stmt.iter)})")
                visit(stmt.orelse, f"{here}/for-else")
            elif isinstance(stmt, (ast.Try, ast.TryStar)):
                handlers = ",".join(_dump(h.type) if h.type else "*" for h in stmt.handlers)
                visit(stmt.body, f"{here}/try({handlers})")
                for handler in stmt.handlers:
                    visit(handler.body, f"{here}/except")
                visit(stmt.orelse, f"{here}/try-else")
                visit(stmt.finalbody, f"{here}/finally")
            elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visit(stmt.body, f"{here}/def({stmt.name})")
            elif isinstance(stmt, ast.Match):
                for case in stmt.cases:
                    visit(case.body, f"{here}/case({_dump(case.pattern)})")
            ended = ended or isinstance(stmt, _ENDS_BLOCK)

    visit(test.node.body, "")
    found.sort(key=lambda c: (getattr(c.node, "lineno", 0), getattr(c.node, "col_offset", 0)))
    return found


def _numbers(call: ast.Call, name: str) -> float | None:
    for kw in call.keywords:
        if kw.arg == name and isinstance(kw.value, ast.Constant):
            value = kw.value.value
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
    return None


def _approx(node: ast.AST) -> ast.Call | None:
    if isinstance(node, ast.Assert) and isinstance(node.test, ast.Compare):
        for side in (node.test.left, *node.test.comparators):
            if isinstance(side, ast.Call) and called_name(side) == "approx":
                return side
    return None


def _looser_approx(old: ast.AST, new: ast.AST) -> bool:
    """`pytest.approx` lost a tolerance or got a bigger one (missing = pytest's default)."""
    before, after = _approx(old), _approx(new)
    if before is None or after is None:
        return False
    for name in ("rel", "abs"):
        a, b = _numbers(before, name), _numbers(after, name)
        if (a is not None and (b is None or b > a)) or (a is None and b is not None):
            return True
    return False


def _exceptions(call: ast.Call) -> set[str] | None:
    if not call.args:
        return None
    first = call.args[0]
    items = first.elts if isinstance(first, ast.Tuple) else [first]
    return {ast.unparse(e) for e in items}


def _has_match(call: ast.Call) -> bool:
    return any(kw.arg == "match" for kw in call.keywords) or called_name(call) in (
        "assertRaisesRegex", "assertWarnsRegex")  # fmt: skip


def _raises_kind(old: ast.AST, new: ast.AST) -> CandidateKind:
    if not (isinstance(old, ast.Call) and isinstance(new, ast.Call)):
        return "changed_expectation"
    before, after = _exceptions(old), _exceptions(new)
    if before is not None and after is not None:
        broad_now = bool(after & BROAD_EXCEPTIONS) and not before & BROAD_EXCEPTIONS
        if broad_now or (before < after):
            return "broadened_raises"
    if _has_match(old) and not _has_match(new):
        return "broadened_raises"
    return "changed_expectation"


def _pair_kind(old: _Check, new: _Check) -> CandidateKind:
    if old.code == new.code:  # the same check, now under another condition, with or try
        return "weakened_assert"
    if old.op == "raises":
        return _raises_kind(old.node, new.node)
    if old.op in STRONG_OPS and new.op != old.op:
        return "weakened_assert"
    if new.op == old.op and _looser_approx(old.node, new.node):
        return "weakened_assert"
    return "changed_expectation"


# --- skips -------------------------------------------------------------------------------------


def _decorator_name(node: ast.expr) -> str | None:
    target = node.func if isinstance(node, ast.Call) else node
    if isinstance(target, ast.Attribute):
        return target.attr
    if isinstance(target, ast.Name):
        return target.id
    return None


def _skip_aliases(tree: ast.Module) -> frozenset[str]:
    """Module-level names bound to a skip mark (`later = pytest.mark.skip`), usable as `@later`."""
    names = set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and _decorator_name(node.value) in SKIP_MARKS:
            names |= {t.id for t in node.targets if isinstance(t, ast.Name)}
    return frozenset(names - {"pytestmark"})


def _is_skip(node: ast.expr, aliases: frozenset[str]) -> bool:
    name = _decorator_name(node)
    return name in SKIP_MARKS or name in aliases


def _marks(test: _Test) -> list[ast.expr]:
    """The decorators on a test and on every class around it."""
    return [*test.node.decorator_list, *(d for c in test.classes for d in c.decorator_list)]


def _skipped(tree: ast.Module, tests: dict[str, _Test]) -> set[str]:
    """Tests that never run their checks: a skip or xfail mark on them, their class or the module,
    or a skip call at the top of their body."""
    aliases = _skip_aliases(tree)
    if any(_is_skip(m, aliases) for m in _pytestmark(tree)):
        return set(tests)
    found = set()
    for name, test in tests.items():
        first = test.node.body[0] if test.node.body else None
        skips_at_once = (isinstance(first, ast.Expr) and isinstance(first.value, ast.Call)
                         and called_name(first.value) in SKIP_CALLS)  # fmt: skip
        if any(_is_skip(m, aliases) for m in _marks(test)) or skips_at_once:
            found.add(name)
    return found


def _skip_calls(test: _Test) -> list[ast.Call]:
    """Skip / xfail calls in the body (not the decorators, which are marks)."""
    return [n for stmt in test.node.body for n in ast.walk(stmt)
            if isinstance(n, ast.Call) and called_name(n) in SKIP_CALLS]  # fmt: skip


def _pytestmark(tree: ast.Module) -> list[ast.expr]:
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets
        ):
            value = node.value
            return list(value.elts) if isinstance(value, (ast.List, ast.Tuple)) else [value]
    return []


T = TypeVar("T")


def _unmatched(items: Iterable[T], others: Iterable[str], key: Callable[[T], str]) -> list[T]:
    """The items (in order) left once each is matched with an equal key in `others`, counting
    duplicates: two equal items need two equal keys."""
    left = Counter(others)
    found = []
    for item in items:
        if left[key(item)] > 0:
            left[key(item)] -= 1
        else:
            found.append(item)
    return found


def _check_key(check: _Check) -> str:
    return check.key


# --- test files ----------------------------------------------------------------------------

Checks = dict[str, list[_Check]]  # test qualname -> its checks


def candidates_in_tests(file: SourceText) -> list[Candidate]:
    """Candidates in one changed test file (base vs head). A deleted file deletes its tests."""
    base_tree = parse(file.base)
    if base_tree is None or file.base is None:
        return []  # added, or unreadable at base: nothing there to weaken
    head_tree = parse(file.head) if file.head is not None else ast.Module([], [])
    if head_tree is None:
        return []  # head doesn't parse: pytest reports it on its own
    base_text, head_text = file.base, file.head or ""
    base_tests, head_tests = _tests(base_tree), _tests(head_tree)
    base_checks = {n: _checks(t, base_text) for n, t in base_tests.items()}
    head_checks = {n: _checks(t, head_text) for n, t in head_tests.items()}
    deleted, renamed = _deleted_tests(file.path, base_text, base_tests, head_tests, base_checks,
                                      head_checks)  # fmt: skip
    pairs = [(n, n) for n in sorted(base_tests.keys() & head_tests.keys())] + renamed
    skipped = _skipped(head_tree, head_tests)
    found: list[Candidate] = list(deleted)
    found += _removed_checks(file.path, base_checks, head_checks, pairs, skipped)
    found += _added_skips(file.path, head_text, base_tree, head_tree, base_tests, head_tests)
    found += _removed_cases(file.path, base_text, base_tests, head_tests)
    return sorted(found, key=lambda c: (c.line, c.kind, c.detail))


def _subjects(checks: Sequence[_Check]) -> set[str]:
    """What a test's checks are about, for spotting a renamed test: calls, attributes and
    subscripts only. A bare name (`result`) says nothing: every test may have one."""
    return {c.subject for c in checks if c.subject not in (None, "raises") and not c.named}


Renamed = list[tuple[str, str]]  # (base name, head name)


def _deleted_tests(path: str, base_text: str, base: dict[str, _Test], head: dict[str, _Test],
                   base_checks: Checks, head_checks: Checks
                   ) -> tuple[list[Candidate], Renamed]:  # fmt: skip
    """Tests gone from the file, and (old, new) name pairs for tests renamed on the way: the same
    body, or at least half of the old test's checks on the same subjects (a rename that also
    corrects an expected value is compared check by check, like an unrenamed test)."""
    new = {n: (_body_key(t), _subjects(head_checks[n])) for n, t in head.items() if n not in base}
    found, renamed = [], []
    for name, test in base.items():
        if name in head:
            continue
        body, old = _body_key(test), _subjects(base_checks[name])
        same = next((n for n, (b, _) in new.items() if b == body), None)
        if same is None and old:
            same = next((n for n, (_, s) in new.items() if 2 * len(old & s) >= len(old)), None)
        if same is not None:
            renamed.append((name, same))
            del new[same]
            continue
        header = base_text.split("\n")[test.node.lineno - 1].strip()
        found.append(Candidate("deleted_test", path, test.node.lineno, header, "base",
                               _end(test.node), name))  # fmt: skip
    return found, renamed


Pairs = Sequence[tuple[str, str]]  # (base name, head name) of the same test


def _removed_checks(path: str, base_checks: Checks, head_checks: Checks, pairs: Pairs,
                    skipped: Set[str]) -> list[Candidate]:  # fmt: skip
    """Checks missing from the head version of a test (pairs: base name, head name). A check that
    only moved to another, running test in the same file is not removed."""
    file_left = Counter(c.key for n, cs in head_checks.items() if n not in skipped for c in cs)
    file_left.subtract(c.key for cs in base_checks.values() for c in cs)
    found = []
    for name, head_name in pairs:
        before, after = base_checks[name], head_checks[head_name]
        removed = _unmatched(before, (c.key for c in after), _check_key)
        added = _unmatched(after, (c.key for c in before), _check_key)  # new in this test
        for check in removed:
            partner = next((a for a in added if a.subject is not None
                            and a.subject == check.subject), None)  # fmt: skip
            if partner is not None:
                added.remove(partner)
                kind = _pair_kind(check, partner)
            elif file_left[check.key] >= 0:
                continue
            else:
                file_left[check.key] += 1
                kind = "removed_assert"
            node = check.node
            moved = partner is not None and partner.code == check.code
            detail = f"{check.text} (now inside other code)" if moved else check.text
            found.append(Candidate(kind, path, getattr(node, "lineno", 0), detail, "base",
                                   _end(node), name,
                                   pinned=kind != "broadened_raises"))  # fmt: skip
    return found


def _added_skips(path: str, head_text: str, base_tree: ast.Module, head_tree: ast.Module,
                 base: dict[str, _Test], head: dict[str, _Test]) -> list[Candidate]:  # fmt: skip
    """New skip / xfail marks (on the module, a test or its class, aliases included) and new skip
    calls in a test's body."""
    old_aliases, new_aliases = _skip_aliases(base_tree), _skip_aliases(head_tree)

    def skip_marks(nodes: Iterable[ast.expr], aliases: frozenset[str]) -> list[ast.expr]:
        return [n for n in nodes if _is_skip(n, aliases)]

    def candidate(node: ast.expr, test: str | None = None) -> Candidate:
        return Candidate("added_skip", path, node.lineno, _segment(head_text, node),
                         end_line=_end(node), test=test)  # fmt: skip

    old_module = map(_dump, skip_marks(_pytestmark(base_tree), old_aliases))
    found = [candidate(m) for m in _unmatched(skip_marks(_pytestmark(head_tree), new_aliases),
                                              old_module, _dump)]  # fmt: skip
    for name in sorted(base.keys() & head.keys()):
        old, new = base[name], head[name]
        old_marks = map(_dump, skip_marks(_marks(old), old_aliases))
        found += [candidate(n, name) for n in _unmatched(skip_marks(_marks(new), new_aliases),
                                                         old_marks, _dump)]  # fmt: skip
        old_calls = map(_dump, _skip_calls(old))
        found += [candidate(c, name) for c in _unmatched(_skip_calls(new), old_calls, _dump)]
    return found


def _case_inputs(case: ast.expr) -> str | None:
    """A parametrize case's inputs: all its values but the last (by convention the expected
    one), for tuples and `pytest.param(...)`; None for single-value cases."""
    parts = case.args if isinstance(case, ast.Call) else getattr(case, "elts", None)
    if not isinstance(case, (ast.Tuple, ast.List, ast.Call)) or not parts or len(parts) < 2:
        return None
    return f"{len(parts)}|" + "|".join(_dump(p) for p in parts[:-1])


def _removed_cases(path: str, text: str, base: dict[str, _Test],
                   head: dict[str, _Test]) -> list[Candidate]:  # fmt: skip
    """`@pytest.mark.parametrize` cases dropped from a test that is still there. A dropped case
    whose inputs come back with another expected value is a changed expectation."""
    found = []
    for name in sorted(base.keys() & head.keys()):
        old, new = _case_nodes(base[name]), _case_nodes(head[name])
        gone = _unmatched(old, map(_dump, new), _dump)
        added = _unmatched(new, map(_dump, old), _dump)
        # inputs of the cases the PR added
        new_inputs = Counter(i for i in map(_case_inputs, added) if i is not None)
        for value in gone:
            inputs = _case_inputs(value)
            if inputs is not None and new_inputs[inputs] > 0:
                new_inputs[inputs] -= 1
                kind: CandidateKind = "changed_expectation"
                detail = f"parametrize case {_segment(text, value)} changed"
            else:
                kind, detail = "removed_assert", f"parametrize case {_segment(text, value)} removed"
            found.append(Candidate(kind, path, value.lineno, detail, "base", _end(value), name))
    return found


def _case_nodes(test: _Test) -> list[ast.expr]:
    nodes: list[ast.expr] = []
    for deco in test.node.decorator_list:
        if isinstance(deco, ast.Call) and _decorator_name(deco) == "parametrize":
            values = deco.args[1] if len(deco.args) > 1 else None
            if isinstance(values, (ast.List, ast.Tuple)):
                nodes += values.elts
    return nodes


# --- test collection (conftest and pytest config): report only -------------------------------


def _collection_names(tree: ast.Module) -> set[str]:
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
            node.name in COLLECTION_HOOKS
        ):
            names.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names |= {t.id for t in targets if isinstance(t, ast.Name)} & COLLECTION_NAMES
    return names


def conftest_candidates(file: SourceText) -> list[Candidate]:
    """A conftest.py that starts ignoring files or changing what gets collected (or changes how
    it already does)."""
    head = parse(file.head)
    if head is None:
        return []
    base = parse(file.base)
    found = []
    for node in head.body:
        names = _collection_names(ast.Module([node], []))
        if not names or (base is not None and any(_dump(node) == _dump(b) for b in base.body)):
            continue
        found.append(Candidate("collection_changed", file.path, node.lineno,
                               f"{', '.join(sorted(names))} added or changed in conftest.py",
                               end_line=_end(node)))  # fmt: skip
    return found


def pytest_options(name: str, text: str | None) -> dict[str, str] | None:
    """pytest's ini options from a config file's text (pyproject.toml, pytest.ini, setup.cfg,
    tox.ini); None if it has no pytest section or can't be read. Only parsed, never run."""
    if text is None:
        return None
    try:
        if name == "pyproject.toml":
            tool = tomllib.loads(text).get("tool", {})
            table = tool.get("pytest") if isinstance(tool, dict) else None
            if not isinstance(table, dict):
                return None
            options = table.get("ini_options", table)
            if not isinstance(options, dict):
                return None
            return {k: " ".join(v) if isinstance(v, list) else str(v) for k, v in options.items()}
        parser = configparser.ConfigParser(interpolation=None)
        parser.read_string(text)
        section = "tool:pytest" if name == "setup.cfg" else "pytest"
        return dict(parser.items(section)) if parser.has_section(section) else None
    except (tomllib.TOMLDecodeError, configparser.Error, UnicodeDecodeError):
        return None


def config_candidates(file: SourceText) -> list[Candidate]:
    """A pytest config whose test selection changed: new hiding options in addopts, or changed
    testpaths / norecursedirs / python_* patterns."""
    name = PurePosixPath(file.path).name
    before = pytest_options(name, file.base) or {}
    after = pytest_options(name, file.head)
    if after is None:
        return []
    changed = [k for k in COLLECTION_OPTIONS if after.get(k) != before.get(k)]
    old_hiding = set(HIDING_ADDOPTS.findall(before.get("addopts", "")))
    if set(HIDING_ADDOPTS.findall(after.get("addopts", ""))) - old_hiding:
        changed.append("addopts")
    return [Candidate("collection_changed", file.path, 1, f"pytest option {k} changed")
            for k in changed]  # fmt: skip


# --- special-casing (source files) ------------------------------------------------------------


def _value(node: ast.AST) -> tuple[bool, object]:
    """(True, value) for a literal constant or a negated number; (False, None) otherwise."""
    if isinstance(node, ast.Constant):
        return True, node.value
    if (isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub)
            and isinstance(node.operand, ast.Constant)
            and isinstance(node.operand.value, (int, float, complex))
            and not isinstance(node.operand.value, bool)):  # fmt: skip
        return True, -node.operand.value
    return False, None


def _literals(node: ast.AST) -> Iterator[ast.AST]:
    """The literal operands of equality / identity / membership tests inside a condition."""
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Compare) or not all(isinstance(op, EQUALITY_OPS)
                                                       for op in sub.ops):  # fmt: skip
            continue
        for side in (sub.left, *sub.comparators):
            items = side.elts if isinstance(side, (ast.Tuple, ast.List, ast.Set)) else [side]
            yield from (item for item in items if _value(item)[0])


def _trivial(value: object) -> bool:
    if value is None or isinstance(value, bool) or value is Ellipsis:
        return True
    try:
        return value in TRIVIAL
    except TypeError:
        return False


def _constants(tree: ast.Module | None) -> set[tuple[type, object]]:
    if tree is None:
        return set()
    found: set[tuple[type, object]] = set()
    for node in ast.walk(tree):
        ok, value = _value(node)
        if ok:
            found.add((type(value), value))
    return found


def _number_pattern(value: int | float | complex) -> re.Pattern[str]:
    return re.compile(rf"(?<![\w.]){re.escape(repr(value))}(?!\w)")


def in_evidence(value: Value, evidence: Sequence[str]) -> bool:
    """The literal is written in the evidence: numbers as a whole token, strings (2+ chars) and
    ASCII bytes as a substring."""
    if isinstance(value, bytes):
        try:
            value = value.decode("ascii")
        except UnicodeDecodeError:
            return False
    if isinstance(value, str):
        return len(value) >= MIN_STRING and any(value in text for text in evidence)
    pattern = _number_pattern(value)
    return any(pattern.search(text) for text in evidence)


def literal_result(node: ast.AST) -> bool:
    """A literal answer: constants (None included), negated numbers, and tuples / lists / sets /
    dicts made only of those."""
    if _value(node)[0]:
        return True
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return all(literal_result(e) for e in node.elts)
    if isinstance(node, ast.Dict):
        return all(k is not None and literal_result(k) for k in node.keys) and all(
            literal_result(v) for v in node.values)  # fmt: skip
    return False


def _returns_literal(body: Sequence[ast.stmt]) -> bool:
    return (len(body) == 1 and isinstance(body[0], ast.Return) and body[0].value is not None
            and literal_result(body[0].value))  # fmt: skip


def _at(node: ast.AST) -> tuple[int, int]:
    return getattr(node, "lineno", 0), getattr(node, "col_offset", 0)


@dataclass(frozen=True)
class _Condition:
    test: ast.AST  # what is compared (for a match case: its pattern)
    at: tuple[int, int]  # where the branch it controls starts (what `without_branch` cuts)
    hard_coded: bool
    pattern: bool = False  # a match case: its literals are the pattern's values


def _conditions(tree: ast.Module) -> Iterator[_Condition]:
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            yield _Condition(node.test, _at(node), _returns_literal(node.body))
        elif isinstance(node, ast.IfExp):
            yield _Condition(node.test, _at(node), literal_result(node.body))
        elif isinstance(node, ast.While):
            yield _Condition(node.test, _at(node), False)
        elif isinstance(node, ast.comprehension):
            for test in node.ifs:
                yield _Condition(test, _at(node), False)
        elif isinstance(node, ast.match_case):
            yield _Condition(node.pattern, _at(node.pattern), _returns_literal(node.body), True)


def _pattern_literals(pattern: ast.AST) -> Iterator[ast.AST]:
    for sub in ast.walk(pattern):
        if isinstance(sub, ast.MatchValue) and _value(sub.value)[0]:
            yield sub.value


def special_cases(file: SourceText, evidence: Sequence[str]) -> list[Candidate]:
    """Equality tests against a literal on the fix's changed lines, where the literal is
    non-trivial, new to this file, and written in the evidence (repro test, PR tests, issue)."""
    head = parse(file.head)
    if head is None or file.head is None or not file.fixed:
        return []
    known = _constants(parse(file.base))
    found = []
    for cond in _conditions(head):
        lines = set(range(getattr(cond.test, "lineno", 0), _end(cond.test) + 1))
        if not lines & file.fixed:
            continue
        literals = _pattern_literals(cond.test) if cond.pattern else _literals(cond.test)
        seen: set[tuple[type, object]] = set()
        for node in literals:
            value = _value(node)[1]
            key = (type(value), value)
            if not isinstance(value, Value) or _trivial(value) or key in known or key in seen:
                continue
            if not in_evidence(value, evidence):
                continue
            seen.add(key)
            found.append(Candidate("special_case", file.path, getattr(cond.test, "lineno", 0),
                                   _segment(file.head, cond.test), end_line=_end(cond.test),
                                   literal=value, hard_coded=cond.hard_coded,
                                   branch=cond.at))  # fmt: skip
    return found


class _CutBranch(ast.NodeTransformer):
    """Replaces the If / IfExp at (line, col) by its else part, or drops the match case whose
    pattern starts there."""

    def __init__(self, line: int, col: int) -> None:
        self.at = (line, col)
        self.done = False

    def _here(self, node: ast.AST) -> bool:
        return (getattr(node, "lineno", None), getattr(node, "col_offset", None)) == self.at

    def visit_If(self, node: ast.If) -> ast.AST | list[ast.stmt]:
        if self._here(node) and not self.done:
            self.done = True
            return node.orelse or ast.Pass()  # found: nothing below it needs visiting
        return self.generic_visit(node)

    def visit_IfExp(self, node: ast.IfExp) -> ast.AST:
        if self._here(node) and not self.done:
            self.done = True
            return node.orelse
        return self.generic_visit(node)

    def visit_Match(self, node: ast.Match) -> ast.AST:
        for case in node.cases:
            if self._here(case.pattern) and not self.done:
                self.done = True
                node.cases.remove(case)
                break
        self.generic_visit(node)
        return node if node.cases else ast.Pass()


def without_branch(text: str, line: int, col: int) -> str | None:
    """The module with the branch at (line, col) cut out, as code; None if there is no such
    branch. Comments and layout are lost (it is only run, never shown)."""
    tree = parse(text)
    if tree is None:
        return None
    cutter = _CutBranch(line, col)
    new = cutter.visit(tree)
    if not cutter.done:
        return None
    return ast.unparse(ast.fix_missing_locations(new))


# --- pragmas (report only) ----------------------------------------------------------------------


def _fixed(file: SourceText) -> list[tuple[int, str]]:
    """(number, text) of each head line the fix added or changed."""
    lines = (file.head or "").split("\n")
    return [(n, lines[n - 1]) for n in sorted(file.fixed) if 0 < n <= len(lines)]


def added_pragmas(file: SourceText) -> list[Candidate]:
    """`# pragma: no cover / no mutate / no branch` on a line the fix added or changed, when the
    file has more of them than before."""
    if file.head is None or len(PRAGMA.findall(file.head)) <= len(PRAGMA.findall(file.base or "")):
        return []
    return [Candidate("added_pragma", file.path, n, line.strip())
            for n, line in _fixed(file) if PRAGMA.search(line)]  # fmt: skip


def evidence_lines(file: SourceText) -> str:
    """The fixed (added or changed) lines of a file, as one text: the PR's own test edits."""
    return "\n".join(line for _, line in _fixed(file))
