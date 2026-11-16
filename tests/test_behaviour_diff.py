"""M7: the behaviour diff stage (behaviour_diff.py), end to end on small repos and fixtures.

Everything is real: copies, watched pytest runs, the in-run harness on both sides. Each test pins
one rule of SPEC 2.5 (Decided in M7).
"""

from pathlib import Path

import make_fixtures
import pytest
from conftest import make_repo

from tracefix import behaviour_diff as bd
from tracefix.behaviour_diff import BehaviourResult, BehaviourStatus, behaviour_diff
from tracefix.behaviour_rules import Kind
from tracefix.diffscope import compute_scope
from tracefix.guard import GuardResult, GuardStatus, Mutant, MutantResult, MutantStatus
from tracefix.llm import FakeProvider, LLMClient
from tracefix.repro import AttemptResult, ReproResult, ReproStatus, Verdict, forbidden_names
from tracefix.runner import Attempt, FailureInfo, Outcome, RunResult
from tracefix.workspace import Workspace

PYPROJECT = '[tool.pytest.ini_options]\npythonpath = ["."]\ntestpaths = ["tests"]\n'
TESTS = "def test_ok() -> None:\n    assert True\n"
FIXTURE = ("base", "head")

CALC = '''\
"""Small arithmetic."""


def double(n: int) -> int:
    """Twice n."""
    return n + n


def sign(x: int) -> int:
    """-1, 0 or 1."""
    if x < 0:
        return -1
    return 1 if x else 0
'''


def repo(tmp_path: Path, head: str, base: str = CALC, **more: str | None) -> Path:
    first = {"pyproject.toml": PYPROJECT, "tests/test_calc.py": TESTS, "calc.py": base}
    return make_repo(tmp_path / "repo", [first, {"calc.py": head, **more}])


def run(
    path: Path,
    issue: str = "",
    repro: ReproResult | None = None,
    refs: tuple[str, str] = ("c0", "c1"),
    guard: GuardResult | None = None,
) -> tuple[BehaviourResult, FakeProvider]:
    provider = FakeProvider([])
    with Workspace(path, *refs) as ws:
        scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
        result = behaviour_diff(ws, scope, repro, issue, LLMClient(provider), guard)
        assert ws.copies == [ws.base, ws.head]  # nothing left behind (the variant copy too)
    return result, provider


def summary(result: BehaviourResult) -> str:
    lines = [f"{result.status}: {result.reason}", f"  checks {result.checks}"]
    for t in result.targets:
        lines.append(f"  target {t.function} {t.reason!r} {t.comparison}")
    for g in result.groups:
        lines.append(f"  group {g.key} {len(g.changes)} explained={g.explained}")
    lines += [f"  note {n}" for n in result.notes]
    lines += [f"  run {label}: {r.outcome}" for label, r in result.runs]
    return "\n".join(lines)


def repro_of(
    code: str, failed: tuple[str, ...] = ("test_zero",), line: int | None = None
) -> ReproResult:
    """A reproduction that reproduced, whose tests `failed` failed before the fix (at `line` of
    the repro file, if given; else at a site outside it)."""
    ids = tuple(f"tests.test_tracefix_repro::{name}" for name in failed)
    where = f"tests/test_tracefix_repro.py:{line}" if line else "calc.py:1"
    failures = tuple(FailureInfo(i, "failure", "AssertionError", where) for i in ids)
    base = RunResult(Outcome.FAILED, (), (Attempt(1, 0.1, ids, "", 1, 0, failures),))
    attempt = AttemptResult(1, Verdict.REPRODUCED, "", code, base, None)
    path = "tests/test_tracefix_repro.py"
    return ReproResult(ReproStatus.REPRODUCED, "", path, code, (attempt,), ())


def test_a_refactor_changes_nothing_and_needs_no_judge(tmp_path: Path) -> None:
    result, provider = run(repo(tmp_path, CALC.replace("return n + n", "return 2 * n")))
    assert result.status is BehaviourStatus.COMPARED, summary(result)
    assert result.changes == 0
    [target] = result.targets
    assert target.function == "calc.double" and target.finished
    assert target.comparison is not None and target.comparison.compared >= 50
    assert result.checks.allowed and result.l3.allowed, summary(result)
    assert not provider.requests  # no change: nothing for the Judge


ASYNC_CALC = CALC.replace("def double(", "async def double(")


def test_m11_an_async_refactor_is_compared_and_changes_nothing(tmp_path: Path) -> None:
    # Until M11 (early) an async function or method closed the L3 gate ("not called yet").
    head = ASYNC_CALC.replace("return n + n", "return 2 * n")
    result, _ = run(repo(tmp_path, head, ASYNC_CALC))
    assert result.status is BehaviourStatus.COMPARED, summary(result)
    assert result.changes == 0
    [target] = result.targets
    assert target.function == "calc.double" and target.finished
    assert target.comparison is not None and target.comparison.compared >= 50
    assert result.checks.allowed and result.l3.allowed, summary(result)


def test_m11_an_async_change_is_seen_in_the_awaited_values(tmp_path: Path) -> None:
    head = ASYNC_CALC.replace("return n + n", "return n + n + (1 if n == 3 else 0)")
    result, _ = run(repo(tmp_path, head, ASYNC_CALC))
    [group] = result.groups
    assert group.key == ("t1", "returns int", "returns int", ""), summary(result)
    assert [dict(c.args) for c in group.changes] == [{"n": "3"}]
    assert not result.l3.allowed


@pytest.mark.parametrize("sides", ["sync_to_async", "async_to_sync"])
def test_m11_a_fix_that_makes_a_function_async_or_not_blocks_l3(tmp_path: Path, sides: str) -> None:
    # Both calls are awaited, so equal values would hide that callers now get a coroutine.
    base, head = (CALC, ASYNC_CALC) if sides == "sync_to_async" else (ASYNC_CALC, CALC)
    result, _ = run(repo(tmp_path, head, base))
    was = "a plain function" if sides == "sync_to_async" else "async"
    assert f"double: before the fix it was {was}" in result.checks.reasons, summary(result)
    assert not result.checks.allowed and not result.l3.allowed


def test_a_change_the_reproduction_test_calls_is_explained(tmp_path: Path) -> None:
    head = CALC.replace("return 1 if x else 0", "return 1 if x >= 0 else 0")
    repro = repro_of("from calc import sign\n\n\ndef test_zero():\n    assert sign(0) == 1\n")
    result, _ = run(repo(tmp_path, head), repro=repro)
    assert result.status is BehaviourStatus.COMPARED, summary(result)
    [group] = result.groups
    assert group.key == ("t1", "returns int", "returns int", "")
    assert [dict(c.args) for c in group.changes] == [{"x": "0"}]  # only zero changed
    assert group.explained == ("the reproduction test calls this input",)
    assert result.checks.allowed, summary(result)
    assert not result.l3.allowed  # a change, and no Judge label yet


def test_a_new_kind_of_change_nothing_explains_blocks_l3(tmp_path: Path) -> None:
    head = CALC.replace(
        '    """Twice n."""\n',
        '    """Twice n."""\n    if n < 0:\n        raise ValueError("no")\n',
    )
    result, _ = run(repo(tmp_path, head))
    [group] = result.groups
    assert group.key == ("t1", "returns int", "raises ValueError", "")
    assert group.kind is Kind.NEW_RAISE
    assert all(int(dict(c.args)["n"]) < 0 for c in group.changes)
    assert not result.checks.allowed and "nothing explains it" in result.checks.reasons[0]
    shown = group.shown[0]
    assert shown.after.outcome is not None and shown.after.outcome["where"] == "repo"


def test_wrong_but_green_breaks_its_docstring_example(built: dict[str, Path]) -> None:
    issue = (make_fixtures.FIXTURES_DIR / "wrong_but_green" / "ISSUE.md").read_text("utf-8")
    result, _ = run(built["wrong_but_green"], issue, refs=FIXTURE)
    assert result.status is BehaviourStatus.COMPARED, summary(result)
    [group] = result.groups
    first = group.shown[0]
    assert dict(first.args) == {"value": "-5", "width": "10"}
    assert first.before.outcome and first.before.outcome["text"] == "0"
    assert first.after.outcome and first.after.outcome["text"] == "-10"
    assert "it breaks the docstring example `bucket_of(-5, 10) == 0`" in result.checks.reasons
    assert group.explained == ("the issue names this call",)  # the large value: what it fixed


def test_a_parameter_only_the_fix_added_is_never_dropped_on_base(tmp_path: Path) -> None:
    head = CALC.replace("def double(n: int) -> int:", "def double(n: int, k: int = 2) -> int:")
    head = head.replace("return n + n", "return n * k")
    result, _ = run(repo(tmp_path, head))
    [target] = result.targets
    assert target.comparison is not None
    lost = target.comparison.lost.get("does not fit the signature before the fix", 0)
    assert lost > 0  # every input naming k
    assert result.changes == 0  # k left at its default behaves the same
    # Too few inputs are left to vouch for the function: the floor or the lost share says so.
    assert not result.checks.allowed
    assert result.checks.reasons[0].startswith("double: "), result.checks.reasons


def test_a_function_the_fix_added_has_nothing_to_compare(tmp_path: Path) -> None:
    head = CALC + '\n\ndef triple(n: int) -> int:\n    """Three times n."""\n    return 3 * n\n'
    result, _ = run(repo(tmp_path, head))
    assert result.status is BehaviourStatus.SKIPPED
    assert [(s.function, s.reason) for s in result.skipped] == [
        ("triple", "new with the fix: nothing to compare")
    ]
    assert not result.l3.allowed


# --- methods (M7.5) -------------------------------------------------------------------------------


def test_a_changed_method_is_compared_and_its_unexplained_change_keeps_l3_out_of_reach(
    tmp_path: Path,
) -> None:
    base = CALC + "\n\nclass Box:\n    def size(self, n: int) -> int:\n        return n\n"
    head = base.replace("        return n\n", "        return n + 1\n")
    result, _ = run(repo(tmp_path, head, base))
    [target] = result.targets
    assert target.function == "calc.Box.size" and target.finished, summary(result)
    [group] = result.groups
    assert group.key[:3] == ("t1", "returns int", "returns int")
    assert dict(group.changes[0].args)["self"] == "'Box()'"  # the object is part of the input
    assert not result.checks.allowed and "nothing explains it" in result.checks.reasons[0]


def test_a_changed_special_method_is_not_compared_and_keeps_l3_out_of_reach(
    tmp_path: Path,
) -> None:
    box = "\n\nclass Box:\n    def __eq__(self, other: object) -> bool:\n        return False\n"
    head = (CALC + box).replace("return False", "return other is self")
    result, _ = run(repo(tmp_path, head.replace("return n + n", "return 2 * n"), CALC + box))
    assert result.status is BehaviourStatus.PARTIAL, summary(result)
    assert any("Box.__eq__: not compared" in r for r in result.checks.reasons)


STACK = '''\
class Stack:
    def __init__(self, limit: int = 10) -> None:
        if limit < 0:
            raise ValueError("limit")
        self.limit = limit
        self.items: list[int] = []

    def push(self, x: int) -> int:
        """Add x on top; return the new size."""
        self.items.append(x)
        return len(self.items)
'''


def stack_repo(tmp_path: Path, head: str, base: str = STACK) -> Path:
    first = {"pyproject.toml": PYPROJECT, "tests/test_calc.py": TESTS, "stack.py": base}
    return make_repo(tmp_path / "repo", [first, {"stack.py": head}])


def test_a_refactored_method_reaches_the_checks_and_unbuildable_objects_are_no_loss(
    tmp_path: Path,
) -> None:
    head = STACK.replace("self.items.append(x)", "self.items += [x]")
    result, provider = run(stack_repo(tmp_path, head))
    assert result.changes == 0, summary(result)
    [target] = result.targets
    assert target.comparison is not None and target.comparison.compared >= 50
    # A negative limit fails to build on both sides alike: not an input, so nothing is lost.
    assert not target.comparison.lost, summary(result)
    assert result.checks.allowed and result.l3.allowed, summary(result)
    assert not provider.requests


def test_what_a_method_leaves_in_its_object_is_compared(tmp_path: Path) -> None:
    head = STACK.replace("self.items.append(x)", "self.items.append(abs(x))")
    result, _ = run(stack_repo(tmp_path, head))
    [group] = result.groups  # the same size returned, a different object left behind
    assert group.kind is Kind.ARGUMENTS, summary(result)
    assert all(int(dict(c.args)["x"]) < 0 for c in group.changes)
    assert not result.checks.allowed


NAMES = '''\
class Names:
    seen: dict[str, int] = {}

    def __init__(self, prefix: str = "") -> None:
        self.prefix = prefix

    def tag(self, name: str) -> str:
        """The name with the prefix (each name is counted)."""
        Names.seen[name] = Names.seen.get(name, 0) + 1
        return self.prefix + name
'''


def test_data_kept_on_the_class_is_compared(tmp_path: Path) -> None:
    head = NAMES.replace("Names.seen[name] = Names.seen.get(name, 0)",
                         "Names.seen[name.upper()] = Names.seen.get(name.upper(), 0)")  # fmt: skip
    result, _ = run(stack_repo(tmp_path, head, NAMES))
    assert {g.kind for g in result.groups} == {Kind.STATE}, summary(result)
    assert not result.checks.allowed  # nothing explains it


FRESH_STACK = '''\
class Stack:
    def __init__(self) -> None:
        self.items: list[int] = []

    def push(self, x: int) -> None:
        self.items.append(x)

    def top(self) -> int:
        """The top item, or -1 when empty."""
        if not self.items:
            return -1
        return self.items[-1]
'''


def test_one_buildable_object_is_not_every_input(tmp_path: Path) -> None:
    # Verifier round 1, B1: `Stack()` is the only object the run can build, but `push` gives it
    # other states; a change on two or more items must not pass on one compared input.
    head = FRESH_STACK.replace("return self.items[-1]", "return self.items[0]")
    result, _ = run(stack_repo(tmp_path, head, FRESH_STACK))
    [target] = result.targets
    assert target.comparison is not None and not target.comparison.exhausted, summary(result)
    assert any("at least 50 needed" in r for r in result.checks.reasons), summary(result)
    assert not result.checks.allowed and not result.l3.allowed


def test_a_method_the_fix_added_has_nothing_to_compare(tmp_path: Path) -> None:
    head = STACK + "\n    def peek(self) -> int:\n        return self.items[-1]\n"
    result, _ = run(stack_repo(tmp_path, head))
    assert [(s.function, s.reason) for s in result.skipped] == [
        ("Stack.peek", "new with the fix: nothing to compare")
    ], summary(result)
    assert not result.l3.allowed


def test_a_method_base_inherited_is_not_new(tmp_path: Path) -> None:
    base = (
        "class Base:\n    def size(self, n: int) -> int:\n        return n\n\n\n"
        "class Box(Base):\n    pass\n"
    )
    head = base.replace("    pass\n", "    def size(self, n: int) -> int:\n        return n + 1\n")
    result, _ = run(stack_repo(tmp_path, head, base))
    assert not result.skipped, summary(result)
    reasons = [r for r in result.checks.reasons if r.startswith("Box.size:")]
    assert reasons == ["Box.size: before the fix it was not a method defined in class Box"]
    assert not result.l3.allowed


def test_a_methods_changed_default_is_not_module_level_code(tmp_path: Path) -> None:
    base = STACK.replace("def push(self, x: int)", "def push(self, x: int, note: str = '')")
    head = base.replace("note: str = ''", "note: str = '-'")
    result, _ = run(stack_repo(tmp_path, head, base))
    assert not any("module-level code" in r for r in result.checks.reasons), summary(result)
    assert result.changes == 0 and result.checks.allowed, summary(result)


LISTENER = '''\
class Listener:
    def __init__(self, default_port: int = 8080) -> None:
        self.default_port = default_port

    def port(self, raw: str) -> int:
        """The port in raw; a blank value gives the listener's default port."""
        if not raw.strip():
            return 8080
        return int(raw)
'''


@pytest.mark.parametrize(
    "check",
    [
        "    assert Listener(9000).port('') == 9000\n",
        "    listener = Listener(9000)\n    assert listener.port(\n        ''\n    ) == 9000\n",
    ],
)
def test_the_reproduction_tests_method_call_explains_a_change(tmp_path: Path, check: str) -> None:
    head = LISTENER.replace("return 8080", "return self.default_port")
    code = f"from stack import Listener\n\n\ndef test_zero():\n{check}"
    result, provider = run(stack_repo(tmp_path, head, LISTENER), repro=repro_of(code))
    [group] = result.groups
    assert group.explained == ("the reproduction test calls this input",), summary(result)
    assert result.checks.allowed, summary(result)
    # The Judge reads the change as a call on the object, beside the class it belongs to.
    request = provider.requests[0].messages[0].content
    assert "Listener(9000).port(raw='')" in request or ".port(raw='')" in request
    assert "Its class (header, docstring and constructor):" in request


def test_base_that_does_not_import_is_not_compared(tmp_path: Path) -> None:
    base = "import no_such_module_here\n\n" + CALC
    result, _ = run(repo(tmp_path, CALC.replace("return n + n", "return 2 * n"), base))
    assert result.status is BehaviourStatus.INCONCLUSIVE, summary(result)
    [target] = result.targets
    assert "could not be loaded before the fix" in target.reason


def test_a_call_that_hangs_on_one_side_is_a_change_and_the_run_goes_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bd, "DIFF_TIMEOUT_S", 40)  # room for startup under load
    head = CALC.replace(
        '    """Twice n."""\n', '    """Twice n."""\n    while n == 13:\n        pass\n'
    )
    result, _ = run(repo(tmp_path, head), issue="`double(13)` is slow")
    [target] = result.targets
    assert target.finished and target.hangs, summary(result)
    [group] = result.groups
    assert group.kind is Kind.HANG and [dict(c.args) for c in group.changes] == [{"n": "13"}]
    assert group.explained == ("the issue names this call",)
    assert any("resumed" in label for label, _ in result.runs)


def test_a_call_that_plants_code_in_the_copy_makes_the_stage_invalid(tmp_path: Path) -> None:
    head = CALC.replace(
        "    return n + n\n",
        '    open("planted.py", "w").write("x = 1\\n")\n    return n + n\n',
    )
    result, _ = run(repo(tmp_path, head))
    # The copy under test is writable at both isolation levels; a new code file in it is
    # tampering either way, never a verdict.
    assert result.status is BehaviourStatus.INVALID, summary(result)
    assert not result.l3.allowed and result.checks.reasons == ("tampering detected",)


def survivor(number: int, path: str, text: str, origin: str = "rule") -> MutantResult:
    mutant = Mutant(number, path, 7, "", "", "", "", text, frozenset({7}), origin)  # type: ignore[arg-type]
    return MutantResult(mutant, MutantStatus.SURVIVED, (), (), False, "", ())


def test_surviving_mutants_are_checked_against_the_fix_report_only(tmp_path: Path) -> None:
    head = CALC.replace("return n + n", "return 2 * n")
    differs = head.replace("return 2 * n", "return 2 * n if n != 0 else 1")
    same = head.replace("return 2 * n", "return n * 2")
    killed = MutantResult(survivor(4, "calc.py", same).mutant, MutantStatus.KILLED, (), (),
                          False, "", ())  # fmt: skip
    guard = GuardResult(
        GuardStatus.NOT_GUARDED,
        "",
        mutants=(survivor(1, "calc.py", differs, "model"), killed),
        rule_mutants=(survivor(2, "calc.py", same), survivor(3, "other.py", "x = 1\n")),
    )
    path = repo(tmp_path, head)
    alone, _ = run(path)
    result, _ = run(path, guard=guard)
    checks = {s.number: s for s in result.survivors}
    assert sorted(checks) == [1, 2, 3], summary(result)  # the killed mutant is not checked
    assert checks[1].status == "differs" and checks[1].origin == "model"
    assert ("double(n=0)", "returns 0", "returns 1") in checks[1].examples
    assert checks[2].status == "no_difference_found" and checks[2].compared >= 50
    assert checks[3].status == "not_checked"
    # Report only: the diff's own result is the same with or without them.
    assert (result.status, result.checks, result.l3) == (alone.status, alone.checks, alone.l3)


# --- verifier round 1 -----------------------------------------------------------------------------


def test_only_checked_calls_in_tests_that_reproduced_explain_a_change(tmp_path: Path) -> None:
    # S3: a call in another test of the repro file (here: no assert, passing on both sides) is
    # no evidence that the change it lands in is what the fix is for.
    head = CALC.replace("    if x < 0:\n", "    if x < -100:\n        return -2\n    if x < 0:\n")
    code = (
        "from calc import sign\n\n\ndef test_zero():\n    assert sign(5) == 1\n\n\n"
        "def test_other():\n    sign(-500)\n"
    )
    result, _ = run(repo(tmp_path, head), repro=repro_of(code))
    [group] = result.groups
    assert all(int(dict(c.args)["x"]) < -100 for c in group.changes)
    assert group.explained == (), summary(result)
    assert not result.checks.allowed
    checked = code.replace("    sign(-500)", "    assert sign(-500) == -2")
    both = repro_of(checked, ("test_zero", "test_other"))
    proven, _ = run(repo(tmp_path / "again", head), repro=both)
    assert proven.groups[0].explained == ("the reproduction test calls this input",)


def test_changed_functions_past_the_cap_keep_l3_out_of_reach(tmp_path: Path) -> None:
    # B1: the seventh changed function is never compared, so nothing can vouch for it.
    funcs = [f"def f{i}(n: int) -> int:\n    return n + {i}\n" for i in range(1, 8)]
    base = "\n\n".join(funcs)
    head = base.replace("return n + 7", "return -1 if n < 0 else n + 7")
    head = "\n\n".join(f.replace(f"return n + {i}", f"return {i} + n") if i < 7 else f
                       for i, f in enumerate(head.split("\n\n"), 1))  # fmt: skip
    result, _ = run(repo(tmp_path, head, base))
    assert result.changes == 0  # f1-f6 are refactors
    assert any("f7: not compared (past the cap of 6 functions)" in r for r in result.checks.reasons)
    assert not result.l3.allowed


def test_changes_the_diff_cannot_compare_keep_l3_out_of_reach(tmp_path: Path) -> None:
    # S1: a removed public function, and a module-level constant the code uses.
    base = "LIMIT = 10\n\n\n" + CALC + "\n\ndef old(n: int) -> int:\n    return n\n"
    head = "LIMIT = 5\n\n\n" + CALC.replace("return n + n", "return 2 * n")
    result, _ = run(repo(tmp_path, head, base))
    reasons = " | ".join(result.checks.reasons)
    assert "old: removed by the fix" in reasons, reasons
    assert "calc.py: module-level code that computes a value changed (line 1)" in reasons
    assert not result.l3.allowed


def test_a_function_base_bound_another_way_is_not_new(tmp_path: Path) -> None:
    # S1: `parse = _impl` in base, a def in head: it existed, it just can't be compared.
    base = "def _impl(n: int) -> int:\n    return n\n\n\nparse = _impl\n"
    head = "def _impl(n: int) -> int:\n    return n\n\n\ndef parse(n: int) -> int:\n    return -n\n"
    result, _ = run(repo(tmp_path, head, base))
    assert not result.skipped or all("new with the fix" not in s.reason for s in result.skipped)
    assert any("parse: before the fix it was not a plain module-level function" in r
               for r in result.checks.reasons), summary(result)  # fmt: skip


def test_a_changed_update_of_an_argument_in_place_is_a_change(tmp_path: Path) -> None:
    # S2: the same return value, but the list is left different.
    base = "def push(items: list[int], n: int) -> None:\n    items.append(n)\n"
    result, _ = run(repo(tmp_path, base.replace("append(n)", "append(n + 1)"), base))
    [group] = result.groups
    assert group.kind is Kind.ARGUMENTS and group.key[3] == "arguments", summary(result)
    assert not result.checks.allowed  # nothing explains it


def test_tampering_during_the_survivor_runs_makes_the_stage_invalid(tmp_path: Path) -> None:
    head = CALC.replace("return n + n", "return 2 * n").replace(
        "1 if x else 0", "1 if x >= 0 else 0"
    )
    planting = head.replace(
        "    return 2 * n\n", '    open("planted.py", "w").write("x = 1\\n")\n    return 2 * n\n'
    )
    guard = GuardResult(GuardStatus.GUARDED, "", rule_mutants=(survivor(1, "calc.py", planting),))
    result, provider = run(repo(tmp_path, head), guard=guard)
    assert result.status is BehaviourStatus.INVALID, summary(result)
    assert "surviving mutant 1" in result.reason
    assert not provider.requests  # survivors run before the Judge: no answer paid for (N5)


def test_an_error_in_the_survivor_step_keeps_the_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*args: object, **kwargs: object) -> None:
        raise OSError("no space left")

    monkeypatch.setattr(bd, "variant_copy", broken)
    head = CALC.replace("return 1 if x else 0", "return 1 if x >= 0 else 0")
    guard = GuardResult(GuardStatus.GUARDED, "", rule_mutants=(survivor(1, "calc.py", head),))
    result, _ = run(repo(tmp_path, head), guard=guard)
    assert result.groups and result.status is BehaviourStatus.COMPARED, summary(result)
    assert any("the survivor check stopped: OSError" in n for n in result.notes)


def test_a_finished_line_from_a_run_that_did_not_pass_is_not_trusted(tmp_path: Path) -> None:
    # Code in the run writes "done" itself and exits: nothing in that run counts as finished.
    forge = (
        "    if n == 13:\n        import os\n"
        '        open(os.environ["TRACEFIX_OUT"], "a").write(\'{"event": "done"}\\n\')\n'
        "        os._exit(0)\n"
    )
    head = CALC.replace('    """Twice n."""\n', '    """Twice n."""\n' + forge)
    result, _ = run(repo(tmp_path, head), issue="`double(13)`")
    assert any("reported it finished but ended" in n for n in result.notes), summary(result)
    assert not result.checks.allowed and not result.targets[0].finished


def test_a_target_that_keeps_hanging_is_given_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bd, "DIFF_TIMEOUT_S", 40)  # room for startup under load
    monkeypatch.setattr(bd, "MAX_RESUMES", 0)
    head = CALC.replace(
        '    """Twice n."""\n', '    """Twice n."""\n    while n == 13:\n        pass\n'
    )
    result, _ = run(repo(tmp_path, head), issue="`double(13)`")
    [target] = result.targets
    assert not target.finished and any("gave up" in h for h in target.hangs), summary(result)
    assert not result.checks.allowed


def test_a_hang_while_making_inputs_is_blamed_on_its_own_function(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # S6: f finishes; g's inputs can't be made (its argument's class never finishes building).
    monkeypatch.setattr(bd, "DIFF_TIMEOUT_S", 40)  # room for startup under load
    base = (
        "class Slow:\n    def __init__(self, n: int) -> None:\n        while True:\n"
        "            pass\n\n\ndef f(n: int) -> int:\n    return n\n\n\n"
        "def g(s: Slow) -> int:\n    return 1\n"
    )
    head = base.replace("return n\n", "return 0 + n\n").replace("return 1\n", "return 2 - 1\n")
    result, _ = run(repo(tmp_path, head, base))
    f, g = result.targets
    assert f.finished and not f.hangs, summary(result)
    assert not g.finished and "hung before this function's calls" in g.hangs[0]


# --- verifier round 2 -----------------------------------------------------------------------------


def test_a_function_base_defined_inside_try_is_changed_not_new(tmp_path: Path) -> None:
    # X1: only diffscope makes a function new; this one existed (under `except`) and changed.
    base = (
        "try:\n    from fastcalc import sign\nexcept ImportError:\n"
        "    def sign(x: int) -> int:\n        return -1 if x < 0 else 1\n"
    )
    head = "def sign(x: int) -> int:\n    return -7 if x < 0 else 1\n"
    result, _ = run(repo(tmp_path, head, base))
    assert not any("new with the fix" in s.reason for s in result.skipped), summary(result)
    assert any("sign: before the fix it was not a plain module-level function" in r
               for r in result.checks.reasons)  # fmt: skip


def test_a_later_check_base_never_reached_explains_nothing(tmp_path: Path) -> None:
    # X2: base stops at the first failing assert (line 6); the pytest.raises after it never ran
    # before the fix, so a model could have written it to fit head.
    head = CALC.replace("return 1 if x else 0", "return 1 if x >= 0 else 0").replace(
        '    """Twice n."""\n',
        '    """Twice n."""\n    if n < 0:\n        raise ValueError("no")\n',
    )
    code = (
        "import pytest\nfrom calc import double, sign\n\n\ndef test_zero():\n"
        "    assert sign(0) == 1\n    with pytest.raises(ValueError):\n        double(-3)\n"
    )
    result, _ = run(repo(tmp_path, head), repro=repro_of(code, line=6))
    groups = {g.key[1:3]: g for g in result.groups}
    assert groups[("returns int", "returns int")].explained, summary(result)  # sign(0): failed
    assert groups[("returns int", "raises ValueError")].explained == ()  # double(-3): never ran
    assert not result.checks.allowed


def test_a_new_helper_with_defaults_does_not_block_l3(tmp_path: Path) -> None:
    # S-a: its default and decorator lines belong to the new function, not to module-level code.
    head = CALC.replace("return n + n", "return _twice(n)") + (
        "\n\ndef _twice(n: int, k: int = 2) -> int:\n    return n * k\n"
    )
    result, _ = run(repo(tmp_path, head))
    assert result.changes == 0
    assert not any("module-level code" in r for r in result.checks.reasons), summary(result)
    assert result.checks.allowed and result.l3.allowed


def test_a_removed_dunder_and_a_rebinding_import_keep_l3_out_of_reach(tmp_path: Path) -> None:
    # S-b: `__eq__` is public behaviour; `floor as rnd` -> `ceil as rnd` changes what uses rnd.
    box = "\n\nclass Box:\n    def __eq__(self, other: object) -> bool:\n        return True\n"
    use = "\n\nclass Use:\n    def go(self, x: float) -> int:\n        return rnd(x)\n"
    base = "from math import floor as rnd\n\n\n" + CALC + box + use
    head = "from math import ceil as rnd\n\n\n" + CALC.replace("return n + n", "return 2 * n") + use
    result, _ = run(repo(tmp_path, head, base))
    reasons = " | ".join(result.checks.reasons)
    assert "Box.__eq__: removed by the fix" in reasons, reasons
    assert "a changed import rebinds rnd" in reasons
    added = base.replace("from math import floor as rnd\n", "from math import ceil, floor as rnd\n")
    calm, _ = run(repo(tmp_path / "again", added, base))
    assert not any("rebinds" in r for r in calm.checks.reasons)  # rnd still means floor


def test_the_models_other_attempts_never_seed_the_diff(tmp_path: Path) -> None:
    # S4: an input only a partly fixed (unproven) attempt names is not tried; the reproduction
    # test's own literals are.
    head = CALC.replace('    """Twice n."""\n', '    """Twice n."""\n'
                        '    if str(n).endswith("4747"):\n        return 0\n')  # fmt: skip
    partly = "from calc import double\n\n\ndef test_odd():\n    assert double(84747) == 169494\n"
    proven = "from calc import double\n\n\ndef test_zero():\n    assert double(1) == 2\n"
    repro = repro_of(proven)
    attempt = AttemptResult(2, Verdict.PARTLY_FIXED, "", partly, None, None)
    repro = ReproResult(repro.status, "", repro.test_path, proven, (attempt, *repro.attempts), ())
    unseeded, _ = run(repo(tmp_path, head), repro=repro)
    assert unseeded.changes == 0, summary(unseeded)
    seeded = repro_of(proven.replace("double(1) == 2", "double(84747) == 0"))
    found, _ = run(repo(tmp_path / "again", head), repro=seeded)
    assert found.changes == 1  # control: the same input from the proven test is tried


def test_a_survivor_whose_run_did_not_finish_is_not_called_equivalent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # N1: the mutant kills its own run at 13 (a hang there would be a real difference); a run
    # cut short says nothing about equivalence.
    head = CALC.replace("return n + n", "return 2 * n")
    dies = head.replace(
        "    return 2 * n\n",
        "    if n == 13:\n        import os\n        os._exit(0)\n    return 2 * n\n",
    )
    guard = GuardResult(GuardStatus.GUARDED, "", rule_mutants=(survivor(1, "calc.py", dies),))
    result, _ = run(repo(tmp_path, head), issue="`double(13)`", guard=guard)
    [check] = result.survivors
    assert check.status == "not_checked" and "did not finish" in check.reason, check


# --- verifier round 3 -----------------------------------------------------------------------------

SIGN_BODY = "    return -1 if x < 0 else (1 if x else 0)\n"


@pytest.mark.parametrize(
    "binding",
    [
        "try:\n    from fastcalc import sign\nexcept ImportError:\n    from slowcalc import sign\n",
        "import sys\n\nif sys.maxsize:\n    sign = _s\nelse:\n    sign = None\n",
        "sign, other = _s, _s\n",
        "try:\n    from slowcalc import *\nexcept ImportError:\n    pass\n",
    ],
    ids=["try-import", "if-assign", "tuple-assign", "star-import"],
)
def test_a_name_base_bound_any_other_way_is_not_new(tmp_path: Path, binding: str) -> None:
    # X1, round 3: diffscope only knows defs; any module-level binding of the name in base means
    # the function existed and changed.
    base = f"def _s(x: int) -> int:\n{SIGN_BODY}\n\n{binding}"
    head = f"def _s(x: int) -> int:\n{SIGN_BODY}\n\ndef sign(x: int) -> int:\n    return 5\n"
    result, _ = run(repo(tmp_path, head, base))
    assert not any("new with the fix" in s.reason for s in result.skipped), summary(result)
    assert any("sign: before the fix" in r for r in result.checks.reasons), summary(result)
    assert not result.l3.allowed


INV = '''\
def inv(x: float) -> float:
    """1 / x."""
    return 1 / x


def double(n: int) -> int:
    return n + n
'''
INV_HEAD = INV.replace("    return 1 / x\n", "    return 1 / x if x else 0.0\n").replace(
    "    return n + n\n", "    return 0 if n == -3 else n + n\n"
)


def test_a_check_after_a_crash_in_the_code_under_test_explains_nothing(tmp_path: Path) -> None:
    # X2a, round 3: base crashes inside inv(0) (outside the test file), so the assert after it
    # never ran before the fix; double(-3) changing is not what the reproduction showed.
    code = (
        "from calc import double, inv\n\n\ndef test_zero():\n    inv(0)\n"
        "    assert double(-3) == 0\n"
    )
    result, _ = run(repo(tmp_path, INV_HEAD, INV), repro=repro_of(code))
    double = next(g for g in result.groups if g.target == "t2")
    assert double.explained == (), summary(result)
    assert not result.checks.allowed


def test_a_call_a_short_circuit_skipped_on_base_explains_nothing(tmp_path: Path) -> None:
    # X2b, round 3: `and` stops at the failing sign(0) on base; double(-3) never ran there.
    head = CALC.replace("return 1 if x else 0", "return 1 if x >= 0 else 0").replace(
        "    return n + n\n", "    return 0 if n == -3 else n + n\n"
    )
    code = (
        "from calc import double, sign\n\n\ndef test_zero():\n"
        "    assert sign(0) == 1 and double(-3) == 0\n"
    )
    result, _ = run(repo(tmp_path, head), repro=repro_of(code))
    by_target = {g.target: g for g in result.groups}
    assert by_target["t2"].explained, summary(result)  # sign(0): it ran and failed on base
    assert by_target["t1"].explained == ()  # double(-3): never called before the fix


def test_a_call_that_crashed_in_the_code_under_test_still_explains(tmp_path: Path) -> None:
    # Should-fix 1, round 3: both asserts' calls ran on base (inv(0) raised inside calc.py);
    # the bug that raises is explained, as it should be.
    code = (
        "from calc import inv\n\n\ndef test_zero():\n    assert inv(2) == 0.5\n"
        "    assert inv(0) == 0.0\n"
    )
    head = INV.replace("    return 1 / x\n", "    return 1 / x if x else 0.0\n")
    result, _ = run(repo(tmp_path, head, INV), repro=repro_of(code))
    [group] = result.groups
    assert group.key[1:3] == ("raises ZeroDivisionError", "returns float")
    assert group.explained == ("the reproduction test calls this input",), summary(result)


def test_removing_a_nested_helper_or_importing_a_package_does_not_block(tmp_path: Path) -> None:
    # Should-fix 2 and nit 1, round 3.
    base = "import os.path\n\n\n" + CALC.replace(
        "    return n + n\n",
        "    def twice(m: int) -> int:\n        return m + m\n\n    return twice(n)\n",
    )
    head = "import os\nimport os.path\n\n\n" + CALC.replace("return n + n", "return 2 * n")
    result, _ = run(repo(tmp_path, head, base))
    assert result.changes == 0
    assert result.checks.allowed, summary(result)


# --- verifier round 4 -----------------------------------------------------------------------------

TWO_CHANGES = CALC.replace("return 1 if x else 0", "return 1 if x >= 0 else 0").replace(
    "    return n + n\n", "    return 0 if n == -3 else n + n\n"
)


def explained_targets(result: BehaviourResult) -> set[str]:
    return {g.target for g in result.groups if g.explained}


def test_a_check_that_held_before_the_fix_explains_nothing(tmp_path: Path) -> None:
    # B1: double(-3) ran on base, in a failing test, inside a check, but that check held there;
    # only the check that failed (sign(0)) shows what the fix is for.
    code = (
        "from calc import double, sign\n\n\ndef test_zero():\n"
        "    assert double(-3) is not None\n    assert sign(0) == 1\n"
    )
    result, _ = run(repo(tmp_path, TWO_CHANGES), repro=repro_of(code))
    assert explained_targets(result) == {"t2"}, summary(result)  # t2 = sign, t1 = double


def test_a_parametrized_case_that_passed_before_the_fix_explains_nothing(tmp_path: Path) -> None:
    # B2: both cases run the same check line; k=0 fails there on base (sign), k=1 calls
    # double(-3) there and passes. That its sibling failed proves nothing about k=1's call.
    code = (
        "import pytest\nfrom calc import double, sign\n\n\n"
        "@pytest.mark.parametrize('k', [0, 1])\ndef test_zero(k):\n"
        "    assert (sign(0) == 1) if k == 0 else (double(-3) in (0, -6))\n"
    )
    result, _ = run(repo(tmp_path, TWO_CHANGES), repro=repro_of(code))
    assert explained_targets(result) == {"t2"}, summary(result)


def test_a_forged_second_report_from_the_recorded_run_counts_for_nothing(tmp_path: Path) -> None:
    # S1: the test writes its own "calls" line (spelling the variable so no forbidden string
    # shows); two reports mean one is forged, and then nothing explains.
    forge = (
        "import json, os\nfrom calc import double, sign\n\n\ndef test_zero():\n"
        "    out = os.environ['TRACE' + 'FIX_OUT']\n"
        "    line = {'event': 'calls', 'calls': [], 'failed': {}}\n"
        "    open(out, 'a').write(json.dumps(line) + '\\n')\n"
        "    assert sign(0) == 1\n"
    )
    result, _ = run(repo(tmp_path, TWO_CHANGES), repro=repro_of(forge))
    assert explained_targets(result) == set(), summary(result)
    assert any("reported its calls more than once" in n for n in result.notes)


def test_a_repro_test_that_reaches_for_the_recorder_is_rejected() -> None:
    # S1: the reproducer refuses such a test before it ever runs.
    code = "import sys\n\n\ndef test_x():\n    sys.getprofile().__self__.seen.add(1)\n"
    assert "getprofile" in forbidden_names(code)


@pytest.mark.parametrize(
    "box",
    [
        "import sys\n\nif sys.maxsize:\n\n    class Box:\n        def gone(self) -> int:\n"
        "            return 1\n",
        "class Box:\n    class Inner:\n        def gone(self) -> int:\n            return 1\n",
    ],
    ids=["class-under-if", "nested-class"],
)
def test_a_public_method_removed_from_any_class_blocks(tmp_path: Path, box: str) -> None:
    # S2: only a function nested in another function is part of it; a method is reachable.
    base = CALC + "\n\n" + box
    kept = box.replace("        def gone(self) -> int:\n            return 1\n", "        pass\n")
    kept = kept.replace("    def gone(self) -> int:\n        return 1\n", "    pass\n")
    head = CALC.replace("return n + n", "return 2 * n") + "\n\n" + kept
    result, _ = run(repo(tmp_path, head, base))
    assert any("gone: removed by the fix" in r for r in result.checks.reasons), summary(result)


@pytest.mark.parametrize(
    "binding",
    [
        "def __getattr__(name: str) -> object:\n    return _s if name == 'sign' else None\n",
        "def _init() -> None:\n    global sign\n    sign = _s\n\n\n_init()\n",
    ],
    ids=["module-getattr", "global"],
)
def test_a_name_base_may_bind_dynamically_is_not_new(tmp_path: Path, binding: str) -> None:
    # S3: a module __getattr__ or a `global` statement can bind it: the function is not new.
    base = f"def _s(x: int) -> int:\n{SIGN_BODY}\n\n{binding}"
    head = f"def _s(x: int) -> int:\n{SIGN_BODY}\n\ndef sign(x: int) -> int:\n    return 5\n"
    result, _ = run(repo(tmp_path, head, base))
    assert any("sign: before the fix" in r for r in result.checks.reasons), summary(result)


def test_a_comprehension_variable_is_no_module_binding(tmp_path: Path) -> None:
    # N1: `[x for x in ...]` in base binds no module name `x`; a new `def x` is new.
    base = "NAMES = [x for x in ('a', 'b')]\n\n\n" + CALC
    head = (
        base.replace("return n + n", "return 2 * n") + "\n\ndef x(n: int) -> int:\n    return n\n"
    )
    result, _ = run(repo(tmp_path, head, base))
    assert ("x", "new with the fix: nothing to compare") in [
        (s.function, s.reason) for s in result.skipped
    ], summary(result)
    assert result.checks.allowed


def test_tampering_during_the_recorded_run_makes_the_stage_invalid(tmp_path: Path) -> None:
    # N4: the extra run on base is watched like every other.
    code = (
        "import os\nfrom calc import sign\n\n\ndef test_zero():\n"
        "    if 'TRACE' + 'FIX_CALLS' in os.environ:\n"
        "        open('planted.py', 'w').write('x = 1\\n')\n    assert sign(0) == 1\n"
    )
    result, _ = run(repo(tmp_path, TWO_CHANGES), repro=repro_of(code))
    assert result.status is BehaviourStatus.INVALID, summary(result)
    assert "with its calls recorded" in result.reason


# --- round 5 --------------------------------------------------------------------------------------

LOGGED = """\
import functools


def logged(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        return f(*args, **kwargs)

    return wrapper


@logged
def sign(x: int) -> int:
    return -1 if x < 0 else (1 if x > 0 else 0)
"""


def test_a_call_through_a_decorators_wrapper_still_explains(tmp_path: Path) -> None:
    # Round 5: the recorder looks through the wrapper to the call the test file wrote.
    head = LOGGED.replace("(1 if x > 0 else 0)", "1")
    code = "from calc import sign\n\n\ndef test_zero():\n    assert sign(0) == 1\n"
    result, _ = run(repo(tmp_path, head, LOGGED), repro=repro_of(code))
    [group] = result.groups
    assert group.explained == ("the reproduction test calls this input",), summary(result)


# --- round 6 --------------------------------------------------------------------------------------


def test_a_result_that_cannot_be_read_in_full_keeps_l3_out_of_reach(tmp_path: Path) -> None:
    # A factory returning a closure: base and head closures differ, but nothing can show it.
    base = "def make(n: int):\n    return lambda: n\n"
    head = "def make(n: int):\n    return lambda: n + 1\n"
    result, _ = run(repo(tmp_path, head, base))
    [target] = result.targets
    assert target.comparison is not None and target.comparison.compared == 0
    assert target.comparison.lost == {
        "its result can't be compared in full": target.comparison.inputs
    }
    assert not result.checks.allowed


def test_a_name_base_binds_only_at_run_time_is_not_new(tmp_path: Path) -> None:
    # S4: `globals()["parse"] = ...` in base; static reading can't see it, the base run can.
    base = CALC + '\n\nfor _name in ("parse",):\n    globals()[_name] = abs\n'
    head = base.replace("return n + n", "return 2 * n") + (
        "\n\ndef parse(n: int) -> int:\n    return -n\n"
    )
    result, _ = run(repo(tmp_path, head, base))
    assert any("parse: base binds this name when it runs" in r for r in result.checks.reasons), (
        summary(result)
    )


def test_a_project_module_named_monitoring_is_fine_but_sys_monitoring_is_not() -> None:
    assert forbidden_names("from app import monitoring\nmonitoring.start()\n") == []
    assert forbidden_names("import sys\nsys.monitoring.use_tool_id(3, 'x')\n") == ["sys.monitoring"]


def test_module_data_a_call_leaves_different_is_a_change(tmp_path: Path) -> None:
    # Round 6: same result, but the module's table is left different.
    base = (
        "import threading\n\n_LOCK = threading.Lock()\nSEEN: list[int] = []\nCALLS = [0]\n\n\n"
        "def note(n: int) -> int:\n    with _LOCK:\n        CALLS[0] += 1\n"
        "        SEEN.append(n)\n    return 0\n"
    )
    head = base.replace("SEEN.append(n)", "SEEN.append(-n)")
    result, _ = run(repo(tmp_path, head, base))
    [target] = result.targets
    assert target.comparison is not None and target.comparison.compared >= 50, summary(result)
    assert not target.comparison.lost  # the lock is skipped; the counter is not "unstable"
    kinds = {g.kind for g in result.groups}
    assert kinds == {Kind.STATE}, summary(result)
    assert not result.checks.allowed  # nothing explains it


# --- round 7: an allowlist snapshot, module data that follows the code, raw output ----------------

ROUND7 = {
    # name: (base, head, extra files in both, how it must show)
    "a C result (re.Match) is never the same": (
        "import re\n\n\ndef find(s: str):\n    return re.search('[0-9]+', s)\n",
        "import re\n\n\ndef find(s: str):\n    return re.search('[0-9]', s)\n",
        {}, "lost"),
    "a partial's arguments": (
        "import functools\n\n\ndef bind(n: int):\n    return functools.partial(pow, n)\n",
        "import functools\n\n\ndef bind(n: int):\n    return functools.partial(pow, n + 1)\n",
        {}, "changed"),
    "a deque's maxlen": (
        "import collections\n\n\ndef window(n: int) -> collections.deque:\n"
        "    return collections.deque([n], maxlen=3)\n",
        "import collections\n\n\ndef window(n: int) -> collections.deque:\n"
        "    return collections.deque([n])\n",
        {}, "changed"),
    "a class made at run time": (
        "import collections\n\n\ndef make(n: int):\n"
        "    return collections.namedtuple('Rec', ['a', 'b'][: 1 + (n > 0)])\n",
        "import collections\n\n\ndef make(n: int):\n"
        "    return collections.namedtuple('Rec', ['a'])\n",
        {}, "lost"),
    "a global rebound to a number": (
        "_COUNT = 0\n\n\ndef bump(n: int) -> int:\n    global _COUNT\n    _COUNT += 1\n"
        "    return n\n",
        "_COUNT = 0\n\n\ndef bump(n: int) -> int:\n    global _COUNT\n    return n\n",
        {}, "changed"),
    "data of another project module": (
        "import store\n\n\ndef add(n: int) -> int:\n    store.save(n)\n    return n\n",
        "import store\n\n\ndef add(n: int) -> int:\n    return n\n",
        {"store.py": "ITEMS = []\n\n\ndef save(n):\n    ITEMS.append(n)\n"}, "changed"),
    "a class attribute": (
        "class Registry:\n    items: list = []\n\n\ndef add(n: int) -> int:\n"
        "    Registry.items.append(n)\n    return n\n",
        "class Registry:\n    items: list = []\n\n\ndef add(n: int) -> int:\n    return n\n",
        {}, "changed"),
    "output through a stream kept from import time": (
        "import sys\n\n\ndef show(n: int, out=sys.stdout) -> None:\n    print(n, file=out)\n",
        "import sys\n\n\ndef show(n: int, out=sys.stdout) -> None:\n    print(-n, file=out)\n",
        {}, "changed"),
    "a str subclass with a mixin": (
        "class Mixin:\n    pass\n\n\nclass Tag(str, Mixin):\n    pass\n\n\n"
        "def tag(n: int) -> Tag:\n    return Tag(str(n))\n",
        "class Mixin:\n    pass\n\n\nclass Tag(str, Mixin):\n    pass\n\n\n"
        "def tag(n: int) -> Tag:\n    return Tag(str(n + 1))\n",
        {}, "changed"),
}  # fmt: skip


@pytest.mark.parametrize("name", list(ROUND7))
def test_a_change_the_snapshot_used_to_miss_never_reaches_l3(tmp_path: Path, name: str) -> None:
    # Verifier round 7, B2-B8: each of these reached L3 with no change reported.
    base, head, more = ROUND7[name][:3]
    shows = ROUND7[name][3]
    first = {"pyproject.toml": PYPROJECT, "tests/test_calc.py": TESTS, "calc.py": base, **more}
    result, _ = run(make_repo(tmp_path / "repo", [first, {"calc.py": head}]))
    assert not result.checks.allowed and not result.l3.allowed, summary(result)
    [target] = result.targets
    assert target.comparison is not None, summary(result)
    if shows == "changed":
        assert result.changes > 0, summary(result)
    else:
        assert any("compared in full" in r for r in target.comparison.lost), summary(result)


def test_a_dispatch_table_and_a_lock_are_read_so_a_refactor_compares(tmp_path: Path) -> None:
    # Round 7, S2: functions inside module data are written by name, locks by kind.
    base = (
        "import threading\n\n\ndef _a(n):\n    return n\n\n\nHANDLERS = {'a': _a}\n"
        "GUARD = {'lock': threading.Lock()}\n\n\n"
        "def go(n: int) -> int:\n    with GUARD['lock']:\n        return HANDLERS['a'](n)\n"
    )
    head = base.replace("return HANDLERS['a'](n)", "return HANDLERS['a'](n) + 0")
    result, _ = run(repo(tmp_path, head, base))
    [target] = result.targets
    assert target.comparison is not None and target.comparison.compared >= 50, summary(result)
    assert not target.comparison.lost and result.changes == 0, summary(result)
    assert result.checks.allowed, summary(result)


def test_module_data_too_large_to_read_has_its_own_reason(tmp_path: Path) -> None:
    # Round 7, S2: the input is lost because of the module data, not "its result".
    table = "_TABLE = {i: i * 2 for i in range(30000)}\n\n\n"
    base = table + "def look(n: int) -> int:\n    return _TABLE.get(n, 0)\n"
    head = base.replace("return _TABLE.get(n, 0)", "return _TABLE.get(n, 0) + 0")
    result, _ = run(repo(tmp_path, head, base))
    [target] = result.targets
    assert target.comparison is not None, summary(result)
    assert set(target.comparison.lost) == {"the module data it uses can't be compared in full"}
    assert not result.checks.allowed


def test_a_check_with_a_changed_call_and_a_refactored_one_is_not_blind(tmp_path: Path) -> None:
    # Round 7, S1: sign changed and double was only refactored; one failing assert holds both.
    head = CALC.replace("return 1 if x else 0", "return 1 if x >= 0 else 0").replace(
        "return n + n", "return 2 * n"
    )
    code = (
        "from calc import double, sign\n\n\n"
        "def test_zero():\n    assert (sign(0), double(2)) == (1, 4)\n"
    )
    result, _ = run(repo(tmp_path, head), repro=repro_of(code, line=5))
    assert not any("saw no difference" in r for r in result.checks.reasons), summary(result)


def test_a_function_that_writes_files_keeps_l3_out_of_reach(tmp_path: Path) -> None:
    # Developer, 8 Oct 2026: what a function writes is not compared, so writing anything keeps
    # L3 out of reach (here through a log the project's conftest opened before Tracefix loaded).
    calc = '''\
LOG = None


def note(n: int) -> int:
    """n, noted."""
    LOG.write(f"{n}\\n")
    LOG.flush()
    return n
'''
    conftest = 'import calc\n\ncalc.LOG = open("conf.log", "a", encoding="utf-8")\n'
    first = {"pyproject.toml": PYPROJECT, "tests/test_calc.py": TESTS, "calc.py": calc,
             "tests/conftest.py": conftest}  # fmt: skip
    head = calc.replace("return n\n", "return +n\n")
    result, _ = run(make_repo(tmp_path / "repo", [first, {"calc.py": head}]))
    [target] = result.targets
    wrote = "it changed files in the copy (conf.log): what it writes is not compared"
    assert wrote in target.reason, summary(result)
    assert not result.checks.allowed, summary(result)


def test_a_run_that_runs_out_of_time_is_unfinished_not_hung(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Round 11, B2: a run killed by the time limit was resumed mid-way on its own, so the two
    # sides' module data no longer matched. Now the input that was running runs alone once: it
    # returns, so nothing hangs, and the function is unfinished (no change, no L3).
    monkeypatch.setattr(bd, "DIFF_TIMEOUT_S", 40)  # room for startup under load
    slow = CALC.replace('    """Twice n."""\n', '    """Twice n."""\n    time.sleep(0.15)\n')
    slow = "import time\n" + slow
    result, _ = run(repo(tmp_path, slow.replace("return n + n", "return 2 * n"), slow))
    target = next(t for t in result.targets if t.function == "calc.double")
    assert not target.finished and not target.hangs, summary(result)
    assert not [g for g in result.groups if g.key[0] == "t1"], summary(result)
    assert any("ran out of time" in n for n in result.notes), summary(result)
    assert any("alone" in label for label, _ in result.runs), summary(result)
    assert not result.checks.allowed


def test_s6_the_diff_compares_the_tricky_strings_too(tmp_path: Path) -> None:
    # isdecimal() and isdigit() disagree on a superscript two and on no older string boundary.
    base = (
        'def is_number(s: str) -> bool:\n    """Whether s is digits."""\n    return s.isdecimal()\n'
    )
    result, _ = run(repo(tmp_path, base.replace("isdecimal", "isdigit"), base))
    changed = {dict(c.args)["s"] for g in result.groups for c in g.changes}
    assert "'\u00b2'" in changed, summary(result)
