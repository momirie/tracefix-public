"""M4: Guard. The revert and mutation checks decide from runs; the model only proposes mutants.

Pure rules are tested directly; the end-to-end tests run real pytest in real copies, watched,
with scripted mutator answers (FakeProvider). The recorded fixture cases are in
test_guard_recorded.py.
"""

import os
import re
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import make_fixtures
import pytest
from conftest import make_repo
from hypothesis import given
from hypothesis import strategies as st

import tracefix.guard as guard_module
from tracefix.diffscope import Hunk, compute_scope
from tracefix.guard import (
    DUPLICATE,
    MAX_MUTANTS,
    MAX_RULE_MUTANTS,
    GuardStatus,
    Mutant,
    MutantResult,
    MutantStatus,
    PrFileCheck,
    RevertCheck,
    SourceFile,
    _rule_step,
    caught_revert,
    certain_not_guarded,
    check_body,
    check_proposal,
    check_reraise,
    crash_only,
    decide,
    fixed_lines,
    guard,
    kill,
    mutator_context,
    pr_test_candidates,
    propose,
    rate,
    revert_files,
    rule_mutants,
    run_until_certain,
    source_files,
    usable_baseline,
)
from tracefix.isolation import TamperingDetected
from tracefix.llm import FakeProvider, LLMClient
from tracefix.mutation_rules import KINDS
from tracefix.prompts import mutator
from tracefix.prompts.mutator import Listing, MutantProposal, MutatorContext
from tracefix.repro import ReproResult, ReproStatus, repro_test_path
from tracefix.runner import Attempt, FailureInfo, Outcome, RunResult
from tracefix.sandbox import sandbox_level
from tracefix.snapshots import content_snapshot
from tracefix.variant import swapped as _swapped  # moved from guard.py in M5
from tracefix.workspace import Workspace, safe_relpath

LEVEL = sandbox_level()

# --- pure: hygiene rules -------------------------------------------------------------------------

HEAD = """\
def total(n, per):
    if per <= 0:
        raise ValueError("per")
    return (n + per - 1) // per
"""
BASE = HEAD.replace("(n + per - 1) // per", "n // per")
SOURCE = SourceFile("pkg/m.py", HEAD, BASE, frozenset({4}))


def proposal(line: int, original: str, replacement: str, path: str = "pkg/m.py") -> MutantProposal:
    return MutantProposal(path=path, line=line, original=original, replacement=replacement,
                          description="a bug")  # fmt: skip


def rejection(p: MutantProposal, source: SourceFile = SOURCE) -> str:
    with pytest.raises(ValueError) as caught:
        check_proposal(p, {source.path: source}, set())
    return str(caught.value)


def test_a_small_edit_on_a_fixed_line_is_accepted() -> None:
    text = check_proposal(proposal(4, "- 1", "+ 1"), {SOURCE.path: SOURCE}, set())
    assert "return (n + per + 1) // per" in text and text.count("\n") == HEAD.count("\n")


@pytest.mark.parametrize(
    ("p", "reason"),
    [
        (proposal(4, "- 1", "+ 1", path="other.py"), "not a Python source file the fix changed"),
        (proposal(2, "<=", "<"), "line 2 is not a line the fix added or changed"),
        (proposal(9, "x", "y"), "line 9 is not in the file"),
        (proposal(4, "- 2", "- 1"), "does not start on line 4"),
        (proposal(4, "per", "n"), "occurs more than once on line 4"),
        (proposal(4, "", "x"), "`original` is empty"),
        (proposal(4, "- 1", "- 1" + " " * 300), "longer than 5 lines or 300 characters"),
        (proposal(4, "- 1", "-\n1\n\n\n\n"), "longer than 5 lines"),
        (proposal(4, "- 1)", "- 1"), "does not compile"),
        (proposal(4, "(n + per - 1) // per", "(n+per-1)//per"), "changes no code"),
        (proposal(4, "// per", "// per  # floor"), "changes no code"),
        (proposal(4, "(n + per - 1) // per", "n // per"), "code from before the fix"),
        (proposal(4, "per - 1", "per - k"), "names not already in the file: k"),
        (proposal(4, "(n + per - 1)", "total(n + per - 1, per)"), "adds Call"),
        (proposal(4, "return (n + per - 1) // per", 'raise ValueError("per")'), "adds Call, Raise"),
        # M4 verifier review (S2): edits that crash or hang every call are easy kills.
        (proposal(4, "// per", "// 0"), "division by a constant 0"),
        (proposal(4, "// per", "// -0.0"), "division by a constant 0"),
        (proposal(4, "- 1", "- 10 ** 10 ** 10"), "adds Pow"),
        (proposal(4, "- 1", "- (1 << 99999)"), "LShift"),
        (proposal(4, "(n + per - 1)", "[n for n in (n, per)][0]"), "ListComp"),
        (proposal(4, "(n + per - 1)", "()[0]"), "indexing into an empty literal"),
    ],
)
def test_hygiene_rejects(p: MutantProposal, reason: str) -> None:
    assert reason in rejection(p)


def test_a_name_may_not_reuse_an_attribute_or_swap_the_callee() -> None:
    source = SourceFile("m.py", "def f(x):\n    return abs(x.real) + 1\n", None, frozenset({2}))
    assert "names not already in the file: real" in rejection(proposal(2, "x.real", "real",
                                                                      "m.py"), source)  # fmt: skip
    swapped = rejection(proposal(2, "abs(", "f(", "m.py"), source)
    assert "adds a call to f" in swapped  # same number of calls, another function called


def test_a_callee_is_its_name_so_an_off_by_one_in_its_receiver_is_still_a_mutant() -> None:
    # M4 verifier review, round 2 (S2): keying callees by their whole expression rejected these.
    code = "def g(self, n, k, a, b):\n    return self.items[n - 1].get(k), (a or b).strip()\n"
    source = SourceFile("m.py", code, None, frozenset({2}))
    for edit in (("[n - 1]", "[n]"), ("(a or b)", "(a and b)")):
        assert check_proposal(proposal(2, *edit, path="m.py"), {"m.py": source}, set())


@pytest.mark.parametrize(
    ("p", "reason"),
    [
        (proposal(4, "// per", "// None"), "arithmetic with None"),
        (proposal(4, "- 1", "- None"), "arithmetic with None"),
        (proposal(4, "// per", "/ False"), "division by a constant 0"),
    ],
)
def test_hygiene_rejects_arithmetic_that_fails_on_every_call(
    p: MutantProposal, reason: str
) -> None:
    # M4 verifier review, round 2 (S2). Others (`+ ""`, `"ab"[9]`) can't all be caught by rules;
    # their kills are reported as crash kills instead (see crash_only).
    assert reason in rejection(p)


def test_an_insertion_is_judged_by_its_neighbours() -> None:
    # M4 verifier review, round 2 (N9): inserting before line 1, which is fixed, is allowed.
    source = SourceFile("m.py", "_STEP = 1\n\n\ndef f():\n    return _STEP\n", None,
                        frozenset({1}))  # fmt: skip
    assert check_proposal(proposal(1, "_STEP = 1", "_STEP = 2\n_STEP = 1", "m.py"),
                          {"m.py": source}, set())  # fmt: skip


def test_an_edit_that_eats_a_newline_cannot_reach_an_unfixed_line() -> None:
    # M4 verifier review (S4): line 3 is fixed, line 4 is not; the edit joins them.
    source = SourceFile("pkg/m.py", HEAD, BASE, frozenset({3}))
    edit = proposal(
        3, '        raise ValueError("per")\n', '        raise ValueError("per")\n    if n:'
    )
    assert "line 4 is not a line the fix" in rejection(edit, source)


def test_an_edit_spanning_into_an_unfixed_line_is_rejected() -> None:
    source = SourceFile("pkg/m.py", HEAD, BASE, frozenset({3, 4}))
    edit = proposal(3, 'raise ValueError("per")\n    return', 'raise ValueError("p")\n    return')
    assert check_proposal(edit, {source.path: source}, set())  # lines 3-4 are both fixed
    with pytest.raises(ValueError, match="line 3 is not a line the fix"):
        check_proposal(edit, {SOURCE.path: SOURCE}, set())


def test_the_same_code_twice_counts_once() -> None:
    seen: set[str] = set()
    check_proposal(proposal(4, "- 1", "+ 1"), {SOURCE.path: SOURCE}, seen)
    with pytest.raises(ValueError, match=DUPLICATE):
        check_proposal(proposal(4, "- 1", "+  1"), {SOURCE.path: SOURCE}, seen)  # other spacing


def test_fixed_lines_include_both_sides_of_a_pure_deletion() -> None:
    from tracefix.diffscope import FileChange, FileKind

    change = FileChange("m.py", None, "M", FileKind.SOURCE, (Hunk(3, 2, 4, 3), Hunk(10, 2, 9, 0)))
    assert fixed_lines(change, 10) == {4, 5, 6, 9, 10}
    assert fixed_lines(change, 9) == {4, 5, 6, 9}  # never past the end of the file


# --- pure: kill and verdict rules ----------------------------------------------------------------


def run(
    outcome: Outcome, failed: tuple[str, ...] = (), passed: tuple[str, ...] = ("t::a", "t::b")
) -> RunResult:
    return RunResult(outcome, (), (Attempt(0, 0.5, failed, "", passed=passed),))


PASSED = run(Outcome.PASSED)


def collection_error(exit_code: int = 2, kind: Any = "error", report_ok: bool = True) -> RunResult:
    failure = FailureInfo("tests.test_x", kind, "ImportError", None, "collection failure")
    attempt = Attempt(exit_code, 0.5, ("tests.test_x",), "", 1, 0, (failure,), report_ok)
    return RunResult(Outcome.ERROR, (), (attempt,))


@pytest.mark.parametrize(
    ("result", "baseline", "expected"),
    [
        (run(Outcome.FAILED, ("t::a",)), PASSED, (True, False)),
        (run(Outcome.FAILED, ("t::a",)), run(Outcome.FAILED, ("t::a",), ("t::b",)), (False, False)),
        (
            run(Outcome.FAILED, ("t::a", "t::b")),
            run(Outcome.FAILED, ("t::a",), ("t::b",)),
            (True, False),
        ),
        (run(Outcome.FAILED, ("t::new",)), PASSED, (False, False)),  # never passed on head
        (run(Outcome.TIMEOUT), PASSED, (True, True)),
        (run(Outcome.FLAKY, ("t::a",)), PASSED, (False, False)),
        (run(Outcome.ERROR), PASSED, (False, False)),
        (run(Outcome.PASSED), PASSED, (False, False)),
        (run(Outcome.FAILED, ("t::a",)), run(Outcome.ERROR), (False, False)),
    ],
)
def test_kill_needs_a_stable_failure_of_a_test_that_passed_on_head_or_a_timeout(
    result: RunResult, baseline: RunResult, expected: tuple[bool, bool]
) -> None:
    assert kill(result, baseline) == expected


def test_a_pr_test_catches_the_revert_only_by_failing_or_by_no_longer_collecting() -> None:
    assert caught_revert(run(Outcome.FAILED, ("t::a",)), PASSED)
    assert caught_revert(collection_error(), PASSED)  # e.g. imports a name only the fix added
    for outcome in (Outcome.PASSED, Outcome.TIMEOUT, Outcome.FLAKY, Outcome.NO_TESTS):
        assert not caught_revert(run(outcome, ("t::a",)), PASSED)
    # M4 verifier review (S1): only a real collection error counts, and only after a clean pass.
    assert not caught_revert(collection_error(exit_code=3), PASSED)  # internal error
    assert not caught_revert(collection_error(report_ok=False), PASSED)  # no report
    assert not caught_revert(collection_error(kind="failure"), PASSED)  # report disagrees
    assert not caught_revert(collection_error(), run(Outcome.FAILED, ("t::a",)))
    assert not caught_revert(collection_error(), run(Outcome.ERROR))  # broken on head too


MUTANT = Mutant(1, "pkg/m.py", 4, "- 1", "+ 1", "a bug", "", "")


def result(status: MutantStatus, *killed_by: Any) -> MutantResult:
    return MutantResult(MUTANT, status, killed_by, (), False, "", ())


KILLED = result(MutantStatus.KILLED, "repro")
SURVIVED = result(MutantStatus.SURVIVED)
DISCARDED = result(MutantStatus.DISCARDED)


def revert(repro: Outcome = Outcome.FAILED, *caught: bool, usable: bool = True) -> RevertCheck:
    files = tuple(
        PrFileCheck(f"tests/test_{i}.py", PASSED, c, usable) for i, c in enumerate(caught)
    )
    repro_run = run(repro, ("r::x",) if repro is Outcome.FAILED else ())
    return RevertCheck(("pkg/m.py",), repro_run, repro is Outcome.FAILED, files)


def test_guarded_needs_80_percent_of_at_least_3_valid_mutants() -> None:
    assert decide(revert(), [KILLED] * 3)[0] is GuardStatus.GUARDED
    assert decide(revert(), [KILLED] * 4 + [SURVIVED])[0] is GuardStatus.GUARDED  # exactly 80%
    status, reason, findings = decide(revert(), [KILLED] * 3 + [SURVIVED])  # 75%
    assert status is GuardStatus.NOT_GUARDED and [f.kind for f in findings] == ["low_kill_rate"]
    assert "3 of 4" in reason


def test_fewer_than_3_valid_mutants_is_inconclusive_and_discarded_ones_dont_count() -> None:
    status, _, findings = decide(revert(), [KILLED, KILLED, DISCARDED, DISCARDED])
    assert status is GuardStatus.INCONCLUSIVE and findings[0].kind == "too_few_mutants"
    assert decide(revert(), [KILLED] * 3 + [DISCARDED] * 5)[0] is GuardStatus.GUARDED


def test_a_revert_finding_means_not_guarded_whatever_the_mutants_say() -> None:
    status, _, findings = decide(revert(Outcome.PASSED), [KILLED] * 5)
    assert status is GuardStatus.NOT_GUARDED
    assert [f.kind for f in findings] == ["repro_passes_on_revert"]
    status, _, findings = decide(revert(Outcome.FAILED, False, False), [KILLED] * 5)
    assert status is GuardStatus.NOT_GUARDED
    assert [(f.kind, f.file) for f in findings] == [
        ("pr_tests_pass_on_revert", "tests/test_0.py"),
        ("pr_tests_pass_on_revert", "tests/test_1.py"),
    ]
    assert decide(revert(Outcome.FAILED, False, True), [KILLED] * 5)[0] is GuardStatus.GUARDED
    status, _, findings = decide(revert(Outcome.PASSED), [])  # both problems are reported
    assert status is GuardStatus.NOT_GUARDED
    assert [f.kind for f in findings] == ["repro_passes_on_revert", "too_few_mutants"]


def test_what_could_not_be_judged_cleanly_is_inconclusive_never_guarded() -> None:
    # M4 verifier review (S1, S8).
    for outcome in (Outcome.ERROR, Outcome.TIMEOUT, Outcome.FLAKY, Outcome.NO_TESTS):
        status, reason, _ = decide(revert(outcome), [KILLED] * 5)
        assert status is GuardStatus.INCONCLUSIVE and "did not run cleanly" in reason
    status, reason, _ = decide(revert(Outcome.FAILED, False, usable=False), [KILLED] * 5)
    assert status is GuardStatus.INCONCLUSIVE and "none of the PR's test files" in reason
    status, reason, _ = decide(revert(), [KILLED] * 3 + [SURVIVED], ["existing suite"])
    assert status is GuardStatus.INCONCLUSIVE and "existing suite could not run" in reason
    assert decide(revert(), [KILLED] * 4, ["existing suite"])[0] is GuardStatus.GUARDED


def test_a_pr_test_file_that_ends_unclean_on_the_reverted_code_is_inconclusive() -> None:
    # M4 verifier review, round 2 (N1): a hang, a flaky run or an internal error on the old code
    # is neither "still passes" nor "caught".
    for outcome in (Outcome.TIMEOUT, Outcome.FLAKY, Outcome.ERROR):
        check = PrFileCheck("tests/test_0.py", run(outcome), False, True)
        reverted = RevertCheck(("pkg/m.py",), run(Outcome.FAILED, ("r::x",)), True, (check,))
        status, reason, _ = decide(reverted, [KILLED] * 5)
        assert status is GuardStatus.INCONCLUSIVE and "did not run cleanly" in reason, outcome


def test_a_test_set_is_usable_only_if_something_passed_on_head() -> None:
    # M4 verifier review, round 2 (N2): all skipped (a platform skipif) can judge nothing.
    assert usable_baseline(PASSED) and usable_baseline(run(Outcome.FAILED, ("t::a",), ("t::b",)))
    assert not usable_baseline(run(Outcome.PASSED, passed=()))  # every test skipped
    for outcome in (Outcome.ERROR, Outcome.TIMEOUT, Outcome.FLAKY, Outcome.NO_TESTS):
        assert not usable_baseline(run(outcome))


def test_a_kill_by_a_crash_in_the_mutated_line_is_told_apart() -> None:
    # M4 verifier review, round 2 (S2): reported separately, not dropped (the developer decides
    # whether such kills count).
    crash = FailureInfo("t::a", "failure", "TypeError", "src/pkg/m.py:4", "")
    elsewhere = FailureInfo("t::a", "failure", "TypeError", "src/pkg/other.py:4", "")
    assertion = FailureInfo("t::b", "failure", "AssertionError", "tests/test_m.py:9", "")
    assert crash_only([crash], "pkg/m.py", {4})
    assert not crash_only([crash], "pkg/m.py", {5})
    assert not crash_only([elsewhere], "pkg/m.py", {4})
    assert not crash_only([crash, assertion], "pkg/m.py", {4})
    assert not crash_only([], "pkg/m.py", {4})


def test_rates_are_per_test_set_over_valid_mutants() -> None:
    results = [result(MutantStatus.KILLED, "repro", "pr_test"), result(MutantStatus.KILLED,
               "suite"), SURVIVED, DISCARDED]  # fmt: skip
    assert rate(results) == round(2 / 3, 3)
    assert rate(results, "repro") == rate(results, "pr_test") == round(1 / 3, 3)
    assert rate([DISCARDED]) is None


# --- pure: proposals with a scripted model --------------------------------------------------------

CONTEXT = MutatorContext((Listing("pkg/m.py", "listing"),))


def answer(*edits: tuple[int, str, str], path: str = "pkg/m.py") -> dict[str, Any]:
    return {"mutants": [proposal(*e, path=path).model_dump() for e in edits]}


def test_rule_mutants_pass_hygiene_and_are_numbered_after_the_model_ones() -> None:
    mutants, notes = rule_mutants([SOURCE], first=5)
    assert [(m.number, m.line, m.replacement.strip(), m.origin, m.kind) for m in mutants] == [
        (5, 2, "return None", "rule", "body"),  # the body mutant comes first
        (6, 4, "return (n + per - 0) // per", "rule", "constant"),  # then the kinds take turns
        (7, 4, "return (n - per - 1) // per", "rule", "arithmetic"),
        (8, 4, "return (n + per - 2) // per", "rule", "constant"),
        (9, 4, "return (n + per + 1) // per", "rule", "arithmetic"),
        (10, 4, "return (n + per - 1) / per", "rule", "arithmetic"),
    ]
    assert mutants[0].description == "rule: body of `total` -> `return None`"
    assert mutants[0].text == "def total(n, per):\n    return None\n" and mutants[0].lines == {2}
    assert mutants[2].description == "rule: `+` -> `-`" and mutants[2].lines == {4}
    assert notes == []


def test_p11_a_mutant_id_names_the_edit_not_its_number() -> None:
    first, _ = rule_mutants([SOURCE], first=1)
    again, _ = rule_mutants([SOURCE], first=7)
    assert [m.id for m in first] == [m.id for m in again]  # numbers differ, ids don't
    assert len({m.id for m in first}) == len(first)
    assert all(re.fullmatch(r"m-[0-9a-f]{12}", m.id) for m in first)
    # Fixed for this edit in every run, on every machine and Python version.
    # M11 reordered the rule mutants and gave them kinds: this id is the one from before that.
    plus = next(m for m in first if m.replacement.strip() == "return (n - per - 1) // per")
    assert plus.id == "m-cd89f5d1a93b"
    moved = Mutant(1, "pkg/other.py", plus.line, plus.original, plus.replacement, "", "", "")
    assert moved.id != plus.id


def test_body_mutants_skip_line_rules_but_not_the_code_rules() -> None:
    # A body mutant spans lines the fix didn't change (line 2 here), which only our own code
    # may do; it must still compile, change the code and not be the code from before the fix.
    already = SourceFile("pkg/n.py", "def f(x):\n    return None\n", "", frozenset({2}))
    was_base = SourceFile("pkg/w.py", "def f(x):\n    if x:\n        return 1\n",
                          "def f(x):\n    return None\n", frozenset({3}))  # fmt: skip
    mutants, _ = rule_mutants([already, was_base], first=1)
    assert [m.description for m in mutants] == ["rule: `1` -> `0`", "rule: `1` -> `2`"]
    with pytest.raises(ValueError, match="changes no code"):
        check_body(proposal(2, "    return None", "    return None"), already, set())


def test_the_kinds_take_turns_under_the_cap_body_first() -> None:
    # M11: replaces "4 body mutants first, then the line edits, then the other bodies".
    head = "".join(f"def f{i}(x):\n    return x + 1\n\n\n" for i in range(6))
    fixed = frozenset(4 * i + 2 for i in range(6))
    mutants, notes = rule_mutants([SourceFile("pkg/m.py", head, None, fixed)], first=1)
    assert [m.kind for m in mutants] == ["body", "constant", "arithmetic"] * 3 + ["body"]
    # Per function: a body mutant, `+` -> `-`, `1` -> 0 and 2.
    assert notes == [f"only the first {MAX_RULE_MUTANTS} of 24 rule mutants were run"]
    assert [m.line for m in mutants if m.kind == "arithmetic"] == [2, 6, 10]  # in line order


ALL_KINDS = """\
def f(a, b, xs):
    n = a + a + a + a + a + a + a + a + a + a + a + 1
    try:
        g(a)
    except ValueError:
        h(a)
    if a < b and a in xs:
        for x in xs:
            if x:
                break
    return n
"""


def test_one_of_every_kind_fits_under_the_cap_whatever_comes_first_in_the_file() -> None:
    # The 11 `+` on line 2 would have filled the cap in line order (NOTES 24).
    assert len(KINDS) == MAX_RULE_MUTANTS
    source = SourceFile("pkg/m.py", ALL_KINDS, None, frozenset(range(2, 11)))
    mutants, notes = rule_mutants([source], first=1)
    assert [m.kind for m in mutants] == list(KINDS)
    assert notes and notes[0].startswith(f"only the first {MAX_RULE_MUTANTS} of ")
    by_kind = {m.kind: m.replacement.strip() for m in mutants}
    assert by_kind["drop_call"] == "pass"  # g(a)
    assert by_kind["reraise"] == "raise\n        h(a)"
    assert by_kind["membership"] == "if a < b and a not in xs:"
    assert all(compile(m.text, m.path, "exec") for m in mutants)


RERAISE_HEAD = "def f(x):\n    try:\n        return g(x)\n    except KeyError:\n        return 0\n"
RERAISE = SourceFile("pkg/m.py", RERAISE_HEAD, None, frozenset({5}))
ADD_RAISE = (5, "        return 0", "        raise\n        return 0")


def test_a_re_raise_may_add_one_bare_raise_on_the_rule_path_only() -> None:
    text = check_reraise(proposal(*ADD_RAISE), RERAISE, set())
    assert "    except KeyError:\n        raise\n        return 0\n" in text
    assert "adds Raise" in rejection(proposal(*ADD_RAISE), RERAISE)  # the model's path
    edit = answer(ADD_RAISE)
    mutants, rejected, _ = propose(LLMClient(FakeProvider([edit, answer()])), CONTEXT, [RERAISE])
    assert mutants == [] and "adds Raise" in rejected[0].reason


@pytest.mark.parametrize(
    ("edit", "reason"),
    [
        ((5, "        return 0", "        raise KeyError\n        return 0"), "a bare `raise`"),
        (
            (5, "        return 0", "        raise\n        raise\n        return 0"),
            "a bare `raise`",
        ),
        ((5, "        return 0", "        raise\n        return 1"), "a bare `raise`"),
        ((5, "return 0", "raise"), "a bare `raise`"),
        ((3, "        return g(x)", "        raise\n        return g(x)"), "not a line the fix"),
    ],
)
def test_the_rule_path_adds_one_bare_raise_and_nothing_else(
    edit: tuple[int, str, str], reason: str
) -> None:
    with pytest.raises(ValueError, match=re.escape(reason)):
        check_reraise(proposal(*edit), RERAISE, set())


def test_rule_mutants_that_break_hygiene_are_dropped_not_rejected() -> None:
    loop = SourceFile(
        "pkg/l.py", "def f(xs):\n    for x in xs:\n        pass\n", "", frozenset({2})
    )
    back = SourceFile("pkg/b.py", "def f(x):\n    return x < 3\n", "def f(x):\n    return x <= 3\n",
                      frozenset({2}))  # fmt: skip
    mutants, _ = rule_mutants([loop, back], first=1)
    # `for x not in xs` does not compile; `x <= 3` is the code from before the fix. Both bodies
    # become `return None`: the same code in different files, so not duplicates.
    assert [(m.path, m.replacement.strip()) for m in mutants] == [
        ("pkg/l.py", "return None"),
        ("pkg/b.py", "return x < 2"),
        ("pkg/b.py", "return None"),
        ("pkg/b.py", "return x < 4"),
    ]


def test_rule_mutants_are_capped_with_a_note() -> None:
    head = "def f():\n    return 1 + 2 + 3 + 4 + 5\n"
    mutants, notes = rule_mutants([SourceFile("pkg/c.py", head, None, frozenset({2}))], first=1)
    assert len(mutants) == MAX_RULE_MUTANTS
    assert notes == [f"only the first {MAX_RULE_MUTANTS} of 15 rule mutants were run"]


DEEP = "TABLE = (0\n" + " + 1\n" * 1500 + ")\n\n\ndef f(x):\n    return x + 1\n"


def test_a_deeply_nested_file_rejects_mutants_instead_of_stopping_guard() -> None:
    # Verifier S2: ast.dump of a 1,500-term chain recursed past the limit (RecursionError).
    deep = SourceFile("pkg/d.py", DEEP, None, frozenset({1507}))
    with pytest.raises(ValueError):
        check_proposal(proposal(1507, "x + 1", "x - 1", "pkg/d.py"), {deep.path: deep}, set())
    assert rule_mutants([deep], first=1) == ([], [])


def test_the_rule_step_turns_errors_into_a_note_but_lets_tampering_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(*_args: Any) -> Any:
        raise OSError("disk full")

    monkeypatch.setattr(guard_module, "rule_mutants", broken)
    results, notes = _rule_step(None, [], None, [], 1)  # type: ignore[arg-type]
    assert results == [] and notes == [
        "the rule mutants could not finish (OSError: disk full); "
        "they never count toward the verdict"
    ]

    def buggy(*_args: Any) -> Any:  # verifier B1: a bug in our own rules, not an expected error
        return [][0]

    monkeypatch.setattr(guard_module, "rule_mutants", buggy)
    results, notes = _rule_step(None, [], None, [], 1)  # type: ignore[arg-type]
    assert results == [] and notes[0].startswith("the rule mutants could not finish (IndexError")

    def tampered(*_args: Any) -> Any:
        raise TamperingDetected(["planted"])

    monkeypatch.setattr(guard_module, "rule_mutants", tampered)
    with pytest.raises(TamperingDetected):
        _rule_step(None, [], None, [], 1)  # type: ignore[arg-type]


def test_too_few_valid_mutants_get_one_follow_up_listing_the_rejections() -> None:
    provider = FakeProvider([
        answer((4, "- 1", "+ 1"), (2, "<=", "<")),
        answer((4, "- 1", "+ 1"), (4, "- 1", "- 2"), (4, "//", "/")),
    ])  # fmt: skip
    mutants, rejected, notes = propose(LLMClient(provider), CONTEXT, [SOURCE])
    assert [m.replacement for m in mutants] == ["+ 1", "- 2", "/"]  # the repeat counted once
    assert [m.number for m in mutants] == [1, 2, 3]
    assert [r.proposal.line for r in rejected] == [2] and notes == []
    feedback = provider.requests[1].messages[-1].content
    assert "Only 1 of your mutants" in feedback and "line 2 is not a line the fix" in feedback
    assert "+    return (n + per + 1) // per" in mutants[0].diff


SIX_VALID = ((4, "- 1", "+ 1"), (4, "- 1", "- 2"), (4, "//", "/"), (4, "- 1", "- 0"),
             (4, "n + per", "n - per"), (4, "- 1", "+ 2"))  # fmt: skip


def test_the_follow_up_fires_below_six_valid_mutants_not_below_three() -> None:
    # M11 (NOTES 24): 3-5 valid used to end the asking; now they get the one follow-up.
    provider = FakeProvider([answer(*SIX_VALID[:5]), answer(*SIX_VALID)])
    mutants, _, _ = propose(LLMClient(provider), CONTEXT, [SOURCE])
    assert len(provider.requests) == 2 and len(mutants) == 6
    feedback = provider.requests[1].messages[-1].content
    assert feedback.startswith("Only 5 of your mutants could be used; at least 6 are wanted.")
    provider = FakeProvider([answer(*SIX_VALID)])
    mutants, _, _ = propose(LLMClient(provider), CONTEXT, [SOURCE])
    assert len(provider.requests) == 1 and len(mutants) == 6


def test_the_mutator_is_asked_for_8_to_10_mutants() -> None:
    assert "Propose between 8 and 10 mutants, all different." in mutator.SYSTEM
    assert (guard_module.MIN_MUTANTS, guard_module.WANT_MUTANTS, guard_module.MAX_MUTANTS) == (
        3, 6, 10)  # fmt: skip


def test_certain_not_guarded_needs_3_valid_and_a_rate_no_remaining_kill_can_save() -> None:
    assert not certain_not_guarded(0, 2, 0)  # too few run: inconclusive, not settled
    assert certain_not_guarded(2, 3, 0)  # 67%, nothing left
    assert certain_not_guarded(0, 3, 7)  # 7 of 10 at most: 70%
    assert not certain_not_guarded(1, 3, 7)  # 8 of 10 still possible
    assert not certain_not_guarded(3, 4, 1)  # 4 of 5 is exactly 80%: guarded possible
    assert certain_not_guarded(2, 4, 1)  # 3 of 5 at most


OUTCOMES = st.sampled_from([MutantStatus.KILLED, MutantStatus.SURVIVED, MutantStatus.DISCARDED])


@given(outcomes=st.lists(OUTCOMES, max_size=MAX_MUTANTS), caught=st.booleans())
def test_stopping_early_never_changes_the_verdict(outcomes: list[MutantStatus],
                                                  caught: bool) -> None:  # fmt: skip
    mutants = [
        Mutant(i + 1, "pkg/m.py", 4, "- 1", f"+ {i}", "", "", "") for i in range(len(outcomes))
    ]
    by_number = {m.number: result(s, *(("repro",) if s is MutantStatus.KILLED else ()))
                 for m, s in zip(mutants, outcomes, strict=True)}  # fmt: skip
    ran, not_run = run_until_certain(mutants, lambda m: by_number[m.number])
    assert ran == [by_number[m.number] for m in mutants[: len(ran)]]
    assert list(not_run) == mutants[len(ran) :]
    full = [by_number[m.number] for m in mutants]
    for check in (revert(), revert(Outcome.FAILED, caught), revert(Outcome.PASSED)):
        assert decide(check, ran)[0] is decide(check, full)[0]
        assert decide(check, ran, ["existing suite"])[0] is decide(
            check, full, ["existing suite"])[0]  # fmt: skip
    if not_run:
        assert decide(revert(), full)[0] is not GuardStatus.GUARDED


def test_the_mutator_is_asked_at_most_twice() -> None:
    provider = FakeProvider([answer(), answer(), answer((4, "- 1", "+ 1"))])
    mutants, _, _ = propose(LLMClient(provider), CONTEXT, [SOURCE])
    assert mutants == [] and len(provider.requests) == 2


def test_a_budget_stop_leaves_a_note_not_a_crash() -> None:
    mutants, rejected, notes = propose(LLMClient(FakeProvider([]), max_calls=0), CONTEXT, [SOURCE])
    assert mutants == [] and rejected == [] and "stopped early" in notes[0]


# --- the fix as git sees it ----------------------------------------------------------------------

PYPROJECT = '[tool.pytest.ini_options]\npythonpath = ["src"]\n'


def test_revert_files_restore_every_non_test_change_and_keep_tests(tmp_path: Path) -> None:
    moved = "".join(f"def f{i}():\n    return {i}\n" for i in range(20))
    base = {"src/a.py": "x = 1\n", "src/gone.py": "y = 1\n", "src/old.py": moved,
            "README.md": "old\n", "tests/test_a.py": "def test_a():\n    pass\n",
            "tests/conftest.py": ""}  # fmt: skip
    head = {"src/a.py": "x = 2\n", "src/gone.py": None, "src/old.py": None, "src/moved.py": moved,
            "src/new.py": "z = 1\n", "README.md": "new\n",
            "tests/test_a.py": "def test_a():\n    assert True\n", "tests/conftest.py": "# c\n",
            "tests/helpers.py": "h = 1\n",
            "tests/test_new.py": "def test_n():\n    pass\n"}  # fmt: skip
    repo = make_repo(tmp_path / "repo", [base, head])
    with Workspace(repo, "c0", "c1") as ws:
        scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
        files, notes = revert_files(ws, scope)
        candidates = pr_test_candidates(scope, ws.head)
    assert files == {"src/a.py": b"x = 1\n", "src/gone.py": b"y = 1\n", "src/moved.py": None,
                     "src/old.py": moved.encode(), "src/new.py": None,
                     "README.md": b"old\n"}  # fmt: skip
    assert notes == []
    # pytest's default python_files: helpers.py and conftest.py are never run as PR tests.
    assert candidates == ("tests/test_a.py", "tests/test_new.py")


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        ({}, ["tests/test_x.py", "tests/x_test.py"]),
        (
            {"pyproject.toml": '[tool.pytest.ini_options]\npython_files = ["check_*.py"]\n'},
            ["tests/check_x.py"],
        ),
        (
            {"pytest.ini": "[pytest]\npython_files = check_*.py test_*.py\n"},
            ["tests/check_x.py", "tests/test_x.py"],
        ),
        ({"tests/tox.ini": "[pytest]\npython_files = *_test.py\n"}, ["tests/x_test.py"]),
    ],
)
def test_pr_test_files_follow_the_repos_python_files_setting(
    tmp_path: Path, config: dict[str, str], expected: list[str]
) -> None:
    # M4 verifier review, round 2 (N3): helpers are never imported as if they were tests.
    names = ["tests/test_x.py", "tests/x_test.py", "tests/check_x.py", "tests/util.py"]
    base = {"README.md": "r\n", **config}
    head = dict.fromkeys(names, "def test_a():\n    pass\n")
    repo = make_repo(tmp_path / "repo", [base, head])
    with Workspace(repo, "c0", "c1") as ws:
        scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
        assert list(pr_test_candidates(scope, ws.head)) == sorted(expected)


def crafted_repo(root: Path) -> Path:
    """A head commit with a tree entry `a/../../../evil.py`: git stores it and the export skips it
    (M4 verifier review, B1)."""
    repo = make_repo(root, [{"pkg/__init__.py": "", "pkg/m.py": "x = 1\n", "tests/t.py": ""}])

    def plumbing(*args: str, data: str = "") -> str:
        # Bytes, not text: text mode would turn "\n" into "\r\n" on Windows. The fixtures' git
        # environment: no user config, a fixed identity (CI machines have none of their own).
        done = subprocess.run(["git", *args], cwd=repo, input=data.encode(), capture_output=True,
                              env=make_fixtures.git_env(make_fixtures.BASE_DATE),
                              check=True)  # fmt: skip
        return done.stdout.decode().strip()

    tree = plumbing("hash-object", "-w", "--stdin", data="y = 1\n")
    tree = plumbing("mktree", data=f"100644 blob {tree}\tevil.py\n")
    for name in ("..", "..", "..", "a"):
        tree = plumbing("mktree", data=f"040000 tree {tree}\t{name}\n")
    entries = [*plumbing("ls-tree", "c0").splitlines(), plumbing("ls-tree", tree)]
    root_tree = plumbing("mktree", data="\n".join(entries) + "\n")
    commit = plumbing("commit-tree", root_tree, "-p", "c0", "-m", "c1")
    plumbing("tag", "c1", commit)
    return repo


def test_paths_from_the_diff_never_lead_outside_the_copies(tmp_path: Path) -> None:
    from dataclasses import replace

    from tracefix.diffscope import FileChange, FileKind
    from tracefix.workspace import WorkspaceError

    evil = "a/../../../evil.py"
    repo = crafted_repo(tmp_path / "repo")
    with Workspace(repo, "c0", "c1") as ws:
        assert any(evil in s for s in ws.skipped)  # the export never writes it
        with pytest.raises(WorkspaceError, match="outside repository"):
            compute_scope(ws.repo, ws.base_sha, ws.head_sha)  # today git diff refuses it too
        # Defence in depth: a scope that lists paths the export skipped (crafted names, or
        # names Windows can't write, e.g. aux.py) must never be written to.
        scope = compute_scope(ws.repo, ws.base_sha, ws.base_sha)
        listed = ((evil, "A"), ("pkg/aux.py", "A"), ("../up.py", "M"))
        unexported = [FileChange(p, None, s, FileKind.SOURCE, (Hunk(0, 0, 1, 1),))
                      for p, s in listed]  # fmt: skip
        scope = replace(scope, files=tuple(unexported))
        sources, notes = source_files(ws, scope)
        assert sources == [] and all("was not exported" in n for n in notes) and len(notes) == 3
        files, notes = revert_files(ws, scope)
        assert files == {} and notes == ["../up.py is not a safe path, so it is not put back"]
        assert repro_test_path(ws, "a/../../tests/t.py") == "tests/test_tracefix_repro.py"
        extra = ws.add_copy(ws.head_sha)
        with (
            pytest.raises(TamperingDetected, match="not a safe path"),
            _swapped(extra, {evil: b"x = 2\n"}),
        ):
            pass
    assert not (tmp_path / "evil.py").exists() and not (tmp_path.parent / "evil.py").exists()
    assert safe_relpath(evil) is None


# --- the variant copy ----------------------------------------------------------------------------


def test_swapped_files_go_back_exactly_with_modes_and_no_new_folders(tmp_path: Path) -> None:
    (tmp_path / "m.py").write_bytes(b"old\n")
    (tmp_path / "gone.py").write_bytes(b"g\n")
    if os.name == "posix":
        (tmp_path / "m.py").chmod(0o755)
    before = content_snapshot(tmp_path)
    with _swapped(tmp_path, {"m.py": b"new\n", "gone.py": None, "a/b/added.py": b"x\n"}):
        assert (tmp_path / "m.py").read_bytes() == b"new\n" and not (tmp_path / "gone.py").exists()
        assert (tmp_path / "a" / "b" / "added.py").exists()
    assert content_snapshot(tmp_path) == before and not (tmp_path / "a").exists()


@pytest.mark.skipif(os.name != "posix" or os.geteuid() == 0, reason="POSIX permissions, not root")
def test_a_restore_that_fails_is_tampering(tmp_path: Path) -> None:
    # M4 verifier review, round 2 (N6): folder modes aren't snapshotted, so a run can make a folder
    # read-only with every file unchanged; putting head's files back then fails.
    (tmp_path / "pkg").mkdir()
    with (
        pytest.raises(TamperingDetected, match=re.escape("could not put pkg/added.py back")),
        _swapped(tmp_path, {"pkg/added.py": b"x\n"}),
    ):
        (tmp_path / "pkg").chmod(0o555)
    (tmp_path / "pkg").chmod(0o755)


def test_the_variant_must_be_back_to_head_at_the_end(
    strong: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    # M4 verifier review, round 2 (N10): proves the final check can fire. A stand-in for a stage
    # that left something behind in the variant (no pytest run needed).
    def leaves_a_change(ws: Workspace, scope: Any, client: Any, variant: Any, *_: Any) -> Any:
        (variant.tree / PAGES).write_text("changed = True\n", encoding="utf-8")
        return guard_module.GuardResult(GuardStatus.GUARDED, "looked fine")

    monkeypatch.setattr(guard_module, "_check", leaves_a_change)
    result = run_guard(strong)
    assert result.status is GuardStatus.INVALID
    assert "not back to head" in result.reason and PAGES in result.reason
    assert strong.copies == [strong.base, strong.head]


def test_an_export_error_for_the_variant_is_inconclusive_not_a_crash(
    strong: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    # M4 verifier review, round 2 (N7).
    def full_disk(sha: str) -> Path:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(strong, "add_copy", full_disk)
    result = run_guard(strong)
    assert result.status is GuardStatus.INCONCLUSIVE and "No space left" in result.reason


def test_swapped_never_writes_through_a_link(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    tree = tmp_path / "tree"
    tree.mkdir()
    try:
        if sys.platform == "win32":
            import _winapi

            _winapi.CreateJunction(str(outside), str(tree / "pkg"))
        else:
            (tree / "pkg").symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"cannot make a link here: {exc}")
    with (
        pytest.raises(TamperingDetected, match="goes through a link"),
        _swapped(tree, {"pkg/m.py": b"x"}),
    ):
        pass
    assert list(outside.iterdir()) == []


def test_the_mutator_sees_neither_issue_nor_tests_nor_the_code_before_the_fix(
    tmp_path: Path,
) -> None:
    repo = pager_repo(tmp_path / "repo", PAGES_HEAD, STRONG_PR_TEST)
    with Workspace(repo, "c0", "c1") as ws:
        sources, _ = source_files(ws, compute_scope(ws.repo, ws.base_sha, ws.head_sha))
    text = mutator.render_request(mutator_context(sources))
    assert ">     5 |     return (n_items + per_page - 1) // per_page" in text
    assert "return n_items // per_page" not in text  # base code: a ready-made easy kill
    assert "def test_" not in text and "pytest" not in text and "issue" not in text.lower()


# --- end to end: real runs, scripted mutator ------------------------------------------------------

PAGES_BASE = '''\
def total_pages(n_items, per_page):
    """How many pages show n_items, per_page at a time."""
    if per_page <= 0:
        raise ValueError("per_page must be positive")
    return n_items // per_page
'''
PAGES_HEAD = PAGES_BASE.replace("n_items // per_page", "(n_items + per_page - 1) // per_page")
PAGES = "src/pager/pages.py"
IMPORT = "import pytest\nfrom pager.pages import total_pages\n\n\n"
SUITE = IMPORT + "def test_exact():\n    assert total_pages(20, 10) == 2\n"  # not touched by the PR
PR_FILE_BASE = IMPORT + (
    "def test_rejects_zero():\n    with pytest.raises(ValueError):\n        total_pages(1, 0)\n"
)
STRONG_PR_TEST = PR_FILE_BASE + "\n\ndef test_partial():\n    assert total_pages(10, 3) == 4\n"
WEAK_PR_TEST = PR_FILE_BASE + "\n\ndef test_partial():\n    assert total_pages(10, 3) >= 1\n"
REPRO = """\
from pager.pages import total_pages


def test_partial_last_page():
    assert total_pages(10, 3) == 4
    assert total_pages(1, 5) == 1
"""


def pager_repo(root: Path, head_source: str, pr_test: str, **extra: str | None) -> Path:
    base = {"pyproject.toml": PYPROJECT, "src/pager/__init__.py": "", PAGES: PAGES_BASE,
            "tests/test_exact.py": SUITE, "tests/test_pages.py": PR_FILE_BASE}  # fmt: skip
    head: dict[str, str | None] = {PAGES: head_source, "tests/test_pages.py": pr_test}
    return make_repo(root, [base, {**head, **extra}])


def reproduced(code: str = REPRO) -> ReproResult:
    return ReproResult(ReproStatus.REPRODUCED, "scripted", "tests/test_tracefix_repro.py", code,
                       (), ())  # fmt: skip


@pytest.fixture
def strong(tmp_path: Path) -> Iterator[Workspace]:
    with Workspace(pager_repo(tmp_path / "repo", PAGES_HEAD, STRONG_PR_TEST), "c0", "c1") as ws:
        yield ws


def run_guard(ws: Workspace, *answers: dict[str, Any], repro: ReproResult | None = None) -> Any:
    client = LLMClient(FakeProvider(list(answers)))
    scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
    return guard(ws, scope, repro or reproduced(), client)


def test_a_well_tested_fix_is_guarded_with_kills_attributed(strong: Workspace) -> None:
    edits = answer((5, "- 1", "+ 1"), (5, "- 1", "- 2"), (5, " - 1", ""), (5, " // ", " / "),
                   path=PAGES)  # fmt: skip
    result = run_guard(strong, edits, answer())  # 4 < 6: one follow-up, which adds none
    assert result.status is GuardStatus.GUARDED, result.reason
    assert result.revert.repro_fails and result.revert.files == (PAGES,)
    assert [c.caught for c in result.revert.pr_files] == [True]
    by = {r.mutant.replacement: (r.status, r.killed_by, r.not_run) for r in result.mutants}
    assert by["+ 1"] == (MutantStatus.KILLED, ("suite",), ())  # (10+3+1)//3 is still 4
    assert by["- 2"] == (MutantStatus.KILLED, ("repro", "pr_test"), ("suite",))
    assert by[""] == (MutantStatus.KILLED, ("suite",), ())
    assert by[" / "] == (MutantStatus.KILLED, ("suite",), ())  # 12 / 3 == 4.0 == 4
    assert result.kill_rate == 1.0 and result.repro_kill_rate == result.pr_kill_rate == 0.25
    # Report-only rule mutants ran too, numbered after the model's four.
    rules = {r.mutant.replacement.strip(): (r.mutant.number, r.status, r.killed_by)
             for r in result.rule_mutants}  # fmt: skip
    killed = MutantStatus.KILLED
    assert rules == {
        "return None": (5, killed, ("repro", "pr_test")),  # the body mutant
        "return (n_items + per_page - 0) // per_page": (6, killed, ("suite",)),
        "return (n_items - per_page - 1) // per_page": (7, killed, ("repro", "pr_test")),
        "return (n_items + per_page - 2) // per_page": (8, killed, ("repro", "pr_test")),
        "return (n_items + per_page + 1) // per_page": (9, killed, ("suite",)),  # 31 // 10
        "return (n_items + per_page - 1) / per_page": (10, killed, ("suite",)),  # 29 / 10
    }
    assert result.rule_kill_rate == 1.0
    assert result.isolation == LEVEL and all(r.isolation == LEVEL for r in result.baselines)
    # The variant was checked against head at the end (else: invalid) and then dropped.
    assert strong.copies == [strong.base, strong.head]


def test_a_kill_by_a_crash_on_the_mutated_line_is_flagged_and_counted(strong: Workspace) -> None:
    # Review of 2 Oct: crash_only was unit-tested, its wiring into the result was not.
    edits = answer((5, " - 1", ' - 1 + ""'), (5, "- 1", "- 2"), path=PAGES)  # int + str: TypeError
    result = run_guard(strong, edits, answer())  # 2 < 3 mutants: one follow-up, which adds none
    crash, wrong = (r for r in sorted(result.mutants, key=lambda r: r.mutant.number))
    assert crash.status is MutantStatus.KILLED and crash.crash_only
    assert "by crashing on the mutated line" in crash.reason
    assert wrong.status is MutantStatus.KILLED and not wrong.crash_only  # an assertion failed
    assert result.crash_kills == 1 and "1 of the kills were crashes" in " ".join(result.notes)


GUARDED_IF = "(n_items + per_page - 1) // per_page if n_items > 0 else 0"


def test_surviving_rule_mutants_never_change_the_verdict(tmp_path: Path) -> None:
    # `> 0` -> `>= 0` is an equivalent mutant (0 items give 0 pages either way), and no test
    # checks 0 items: rule mutants survive, yet the model's mutants alone decide (Decided 3 Oct).
    head = PAGES_BASE.replace("n_items // per_page", GUARDED_IF)
    repo = pager_repo(tmp_path / "repo", head, STRONG_PR_TEST)
    edits = answer((5, "- 1", "- 2"), (5, " - 1", ""), (5, " // ", " / "), path=PAGES)
    with Workspace(repo, "c0", "c1") as ws:
        result = run_guard(ws, edits, answer())  # 3 < 6: one follow-up, which adds none
    assert result.status is GuardStatus.GUARDED, result.reason
    assert result.kill_rate == 1.0 and all(r.mutant.origin == "model" for r in result.mutants)
    survivors = {r.mutant.replacement.strip() for r in result.rule_mutants
                 if r.status is MutantStatus.SURVIVED}  # fmt: skip
    assert f"return {GUARDED_IF.replace('> 0', '>= 0')}" in survivors
    assert result.rule_kill_rate is not None and result.rule_kill_rate < 0.8
    assert "rule" not in result.reason


HANDLED_HEAD = PAGES_BASE.replace(
    "    return n_items // per_page\n",
    "    try:\n        return (n_items + per_page - 1) // per_page\n"
    "    except TypeError:\n        print(n_items)\n        return 0\n",
)
HANDLED_PR_TEST = (
    STRONG_PR_TEST + "\n\ndef test_not_a_number():\n    assert total_pages('x', 3) == 0\n"
)


def test_a_dropped_call_and_a_re_raise_really_run_and_stay_report_only(tmp_path: Path) -> None:
    # Real pytest: the handler is tested (a re-raise fails that test), the print is not.
    repo = pager_repo(tmp_path / "repo", HANDLED_HEAD, HANDLED_PR_TEST)
    with Workspace(repo, "c0", "c1") as ws:
        result = run_guard(ws, answer(), answer())  # the model offers no mutants
    assert result.status is GuardStatus.INCONCLUSIVE, result.reason  # rule mutants don't count
    assert "only 0 valid mutants" in result.reason
    by_kind = {r.mutant.kind: r for r in result.rule_mutants}
    reraise, drop = by_kind["reraise"], by_kind["drop_call"]
    assert reraise.status is MutantStatus.KILLED and "pr_test" in reraise.killed_by
    assert drop.status is MutantStatus.SURVIVED and drop.mutant.replacement.strip() == "pass"
    assert drop.mutant.description == "rule: `print(n_items)` -> `pass`"


def test_model_mutants_stop_once_not_guarded_is_certain(tmp_path: Path) -> None:
    # M11 (NOTES 24): no test checks 0 or negative items, so the three edits of `> 0` survive;
    # with two left, at most 2 of 5 could be killed, under 80%: those two are never run.
    head = PAGES_BASE.replace("n_items // per_page", GUARDED_IF)
    repo = pager_repo(tmp_path / "repo", head, STRONG_PR_TEST)
    edits = answer((5, "> 0", ">= 0"), (5, "> 0", "> -1"), (5, "> 0", "!= 0"),
                   (5, "- 1", "- 2"), (5, " // ", " / "), path=PAGES)  # fmt: skip
    with Workspace(repo, "c0", "c1") as ws:
        result = run_guard(ws, edits, answer())  # 5 < 6: one follow-up, which adds none
    assert result.status is GuardStatus.NOT_GUARDED, result.reason
    assert [r.status for r in result.mutants] == [MutantStatus.SURVIVED] * 3
    assert [m.replacement for m in result.not_run] == ["- 2", " / "]
    assert "2 of the 5 mutants were not run" in " ".join(result.notes)
    assert "killed 0 of 3 mutants" in result.reason
    assert result.rule_mutants  # report-only rule mutants still run, numbered after all five
    assert min(r.mutant.number for r in result.rule_mutants) == 6


def test_a_pr_test_that_passes_without_the_fix_means_not_guarded(tmp_path: Path) -> None:
    repo = pager_repo(tmp_path / "repo", PAGES_HEAD, WEAK_PR_TEST)
    with Workspace(repo, "c0", "c1") as ws:
        result = run_guard(ws, answer(), answer())  # no mutants: the revert check decides
    assert result.status is GuardStatus.NOT_GUARDED
    assert result.revert.repro_fails
    assert [(f.kind, f.file) for f in result.findings] == [
        ("pr_tests_pass_on_revert", "tests/test_pages.py"),
        ("too_few_mutants", None),
    ]


def test_pr_tests_follow_python_files_and_files_without_tests_are_dropped(tmp_path: Path) -> None:
    # M4 verifier review (S6, round 2 N3): a repo's python_files may name test files any way it
    # likes; a matching file with no tests, or a helper that doesn't match, is never counted.
    pyproject = PYPROJECT + 'python_files = ["test_*.py", "check_*.py"]\n'
    repo = pager_repo(tmp_path / "repo", PAGES_HEAD, PR_FILE_BASE, **{
        "pyproject.toml": pyproject, "tests/check_pages.py": WEAK_PR_TEST,
        "tests/check_empty.py": "LIMIT = 1\n",
        "tests/helpers.py": "raise SystemExit('never imported')\n"})  # fmt: skip
    with Workspace(repo, "c0", "c1") as ws:
        result = run_guard(ws, answer(), answer())
    assert result.pr_test_files == ("tests/check_pages.py",)  # test_pages.py: unchanged
    notes = " ".join(result.notes)
    assert "tests/check_empty.py has no tests" in notes and "helpers" not in notes
    assert result.status is GuardStatus.NOT_GUARDED
    assert ("pr_tests_pass_on_revert", "tests/check_pages.py") in [
        (f.kind, f.file) for f in result.findings
    ]


LOOP_HEAD = '''\
_STEP = 1


def total_pages(n_items, per_page):
    """How many pages show n_items, per_page at a time."""
    if per_page <= 0:
        raise ValueError("per_page must be positive")
    pages = 0
    while pages * per_page < n_items:
        pages += _STEP
    return pages
'''


def test_a_hanging_mutant_is_killed_and_one_that_breaks_imports_is_discarded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(guard_module, "MIN_TIMEOUT_S", 6.0)
    monkeypatch.setattr(guard_module, "TIMEOUT_FACTOR", 2)
    repo = pager_repo(tmp_path / "repo", LOOP_HEAD, STRONG_PR_TEST)
    edits = answer((10, "pages += _STEP", "pages += 0"), (1, "_STEP = 1", "_STEP = _STEP"),
                   (9, "<", "<="), path=PAGES)  # fmt: skip
    with Workspace(repo, "c0", "c1") as ws:
        result = run_guard(ws, edits, answer())  # 3 < 6: one follow-up, which adds none
    by = {r.mutant.number: r for r in result.mutants}
    assert 1 in by, f"{result.status}: {result.reason}"
    assert by[1].status is MutantStatus.KILLED and by[1].timed_out
    assert [s for s, r in by[1].runs] == ["repro", "repro", "pr_test", "pr_test"]  # each twice
    assert all(r.outcome is Outcome.TIMEOUT for _, r in by[1].runs)
    assert by[2].status is MutantStatus.DISCARDED and "does not import" in by[2].reason
    assert by[3].status is MutantStatus.KILLED and by[3].killed_by == ("suite",)
    assert result.status is GuardStatus.INCONCLUSIVE  # 2 valid mutants are too few to judge
    assert "only 2 valid mutants" in result.reason


def test_a_fix_that_adds_deletes_and_renames_files_is_reverted_and_restored(
    tmp_path: Path,
) -> None:
    rounding = "def up(n, per):\n    return (n + per - 1) // per\n"
    uses_rounding = "    from pager.rounding import up\n\n    return up(n_items, per_page)"
    head = PAGES_BASE.replace("    return n_items // per_page", uses_rounding)
    base = {"pyproject.toml": PYPROJECT, "src/pager/__init__.py": "", PAGES: PAGES_BASE,
            "src/pager/old.py": "OLD = 1\n", "src/pager/legacy/keep.py": "K = 1\n",
            "tests/test_exact.py": SUITE}  # fmt: skip
    changes = {PAGES: head, "src/pager/old.py": None, "src/pager/rounding.py": rounding,
               "src/pager/legacy/keep.py": None, "src/pager/kept.py": "K = 1\n"}  # fmt: skip
    repo = make_repo(tmp_path / "repo", [base, changes])
    with Workspace(repo, "c0", "c1") as ws:
        assert not (ws.head / "src" / "pager" / "legacy").exists()  # precondition
        result = run_guard(ws, answer(), answer())
        assert ws.copies == [ws.base, ws.head]
    assert result.status is GuardStatus.INCONCLUSIVE, result.reason  # no mutants proposed
    assert result.revert.repro_fails
    reverted = {PAGES, "src/pager/old.py", "src/pager/rounding.py", "src/pager/legacy/keep.py",
                "src/pager/kept.py"}  # fmt: skip
    assert set(result.revert.files) == reverted  # keep.py -> kept.py is a rename


def test_nothing_to_guard_with_or_to_revert_is_skipped(strong: Workspace, tmp_path: Path) -> None:
    not_reproduced = ReproResult(ReproStatus.NOT_REPRODUCED, "", "t.py", None, (), ())
    assert run_guard(strong, repro=not_reproduced).status is GuardStatus.SKIPPED
    before = {"tests/test_a.py": "def test_a():\n    pass\n"}
    after = {"tests/test_a.py": "def test_a():\n    assert 1\n"}
    repo = make_repo(tmp_path / "tests-only", [before, after])
    with Workspace(repo, "c0", "c1") as ws:
        result = run_guard(ws)
    assert result.status is GuardStatus.SKIPPED and "no non-test file" in result.reason
    assert len(ws.copies) == 2  # no variant was made


def test_a_repro_test_that_edits_another_copy_is_caught_or_blocked(strong: Workspace) -> None:
    target = strong.head / "src" / "pager" / "pages.py"
    before = content_snapshot(strong.head)
    hostile = REPRO + (
        "\n\ndef test_attack():\n    import pytest\n    try:\n"
        f"        open({target.as_posix()!r}, 'a').write('# x')\n"
        "    except OSError as exc:\n"
        "        pytest.fail(f'WRITE BLOCKED errno={exc.errno}')\n"
    )
    result = run_guard(strong, repro=reproduced(hostile))
    if LEVEL == "strict":
        import errno

        assert result.status is GuardStatus.INCONCLUSIVE, result.reason
        assert f"WRITE BLOCKED errno={errno.ENOENT}" in result.baselines[0].first.output
        assert content_snapshot(strong.head) == before
    else:
        assert result.status is GuardStatus.INVALID
        assert "the other copy" in result.reason and "pages.py" in result.reason
        assert result.reason.startswith("during the run of the reproduction test on the fixed")


def test_tampering_during_the_revert_check_makes_the_stage_invalid(tmp_path: Path) -> None:
    # M4 verifier review (S9): a PR test that rewrites the code under test once it sees the old
    # code. The copy under test is writable at both isolation levels, so this is caught, not
    # blocked, everywhere.
    sneaky = STRONG_PR_TEST + (
        "\n\ndef test_sneaky():\n    import pathlib\n    import pager.pages as pages\n"
        "    path = pathlib.Path(pages.__file__)\n"
        "    if 'per_page - 1' not in path.read_text():\n"
        "        path.write_text(path.read_text() + '# x\\n')\n"
    )
    repo = pager_repo(tmp_path / "repo", PAGES_HEAD, sneaky)
    with Workspace(repo, "c0", "c1") as ws:
        result = run_guard(ws, answer(), answer())
        assert ws.copies == [ws.base, ws.head]  # dropped, so no later stage inherits it
    assert result.status is GuardStatus.INVALID
    assert result.reason.startswith("during the revert check") and "pages.py" in result.reason
