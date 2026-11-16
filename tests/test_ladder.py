"""The evidence ladder: invariants over every combination of facts, each strict L4 condition alone,
and the facts as read from stage results (plan P3, P4)."""

from dataclasses import replace

import pytest
from hypothesis import given
from hypothesis import strategies as st
from synthetic import (
    FIX_LINES,
    PATH,
    attack,
    behaviour,
    finding,
    flag,
    guard,
    integrity,
    l4_run,
    prop,
    regression,
    regressions,
    repro,
    run,
    stage,
    target,
)

from tracefix.attack import AttackStatus
from tracefix.attack_inputs import Skipped
from tracefix.behaviour_rules import Gate
from tracefix.guard import GuardStatus
from tracefix.integrity import IntegrityResult, IntegrityStatus
from tracefix.ladder import (
    L4_MIN_INPUTS,
    EvidenceLevel,
    Facts,
    climb,
    facts,
    l4_gate,
    level,
    previous_gate,
    rank,
)
from tracefix.previous import PreviousResult, PreviousStatus, Replay, Replayed
from tracefix.record import PREVIOUS, RunRecord, RunStatus, StageRecord
from tracefix.regressions import RegressionResult, RegressionStatus
from tracefix.repro import ReproStatus

GATES = ("reproduced", "guarded", "l3", "l4")
L = EvidenceLevel


def _gate(allowed: bool) -> Gate:
    return Gate(True) if allowed else Gate(False, ("closed for the test",))


facts_strategy = st.builds(
    Facts,
    stopped=st.none() | st.just("the base suite cannot run"),
    counterexamples=st.lists(st.sampled_from(["finding 1", "flag f1"]), max_size=2).map(tuple),
    tampering=st.lists(st.just("guard (a file changed)"), max_size=1).map(tuple),
    reproduced=st.booleans().map(_gate),
    guarded=st.booleans().map(_gate),
    l3=st.booleans().map(_gate),
    l4=st.booleans().map(_gate),
)


@given(facts_strategy)
def test_the_level_follows_the_ladder(f: Facts) -> None:
    rung = climb(f)
    assert rung.reasons
    if f.stopped is not None:
        assert rung.level is L.L0
    elif f.counterexamples:
        assert rung.level is L.COUNTEREXAMPLE
        assert rung.reasons == f.counterexamples
    elif f.tampering:
        assert rung.level is L.L0
    else:
        opened = 0
        for name in GATES:
            if not getattr(f, name).allowed:
                break
            opened += 1
        assert rung.level is [L.L0, L.L1, L.L2, L.L3, L.L4][opened]
        if rung.level is not L.L4:
            assert any(r.startswith(f"not L{opened + 1}: ") for r in rung.reasons)


@given(facts_strategy)
def test_a_stop_or_tampering_never_gives_l1_or_more(f: Facts) -> None:
    if f.stopped is not None or f.tampering:
        assert rank(climb(f).level) <= rank(L.L0)


@given(facts_strategy, st.sampled_from(GATES))
def test_closing_a_gate_never_raises_the_level(f: Facts, name: str) -> None:
    closed = replace(f, **{name: Gate(False, ("closed",))})
    assert rank(climb(closed).level) <= rank(climb(f).level)


@given(facts_strategy)
def test_a_counterexample_or_tampering_never_raises_the_level(f: Facts) -> None:
    worse = [replace(f, counterexamples=(*f.counterexamples, "another finding")),
             replace(f, tampering=(*f.tampering, "integrity (a file changed)"))]  # fmt: skip
    for other in worse:
        assert rank(climb(other).level) <= rank(climb(f).level)


def test_every_gate_open_is_l4() -> None:
    rung = climb(Facts(reproduced=Gate(True), guarded=Gate(True), l3=Gate(True), l4=Gate(True)))
    assert rung.level is L.L4
    assert len(rung.reasons) == 4


def test_the_order_of_levels() -> None:
    assert [rank(x) for x in (L.COUNTEREXAMPLE, L.L0, L.L1, L.L2, L.L3, L.L4)] == list(range(6))


# --- the strict L4 gate -------------------------------------------------------------------------


def test_a_full_attack_opens_l4() -> None:
    assert l4_gate(attack()) == Gate(True)


def test_exactly_the_minimum_inputs_is_enough() -> None:
    assert l4_gate(attack(targets=(target(inputs_tried=L4_MIN_INPUTS),))).allowed


@pytest.mark.parametrize(
    ("changed", "says"),
    [
        ({"status": AttackStatus.INCONCLUSIVE}, "Break My Fix ended inconclusive"),
        ({"status": AttackStatus.FOUND}, "Break My Fix ended found"),
        ({"skipped": (Skipped(PATH, "pkg.calc.g", "a generator"),)}, "could not be attacked"),
        ({"targets": ()}, "no changed function was attacked"),
        ({"targets": (target(attacked=False, reason="no property"),)}, "was not attacked"),
        ({"targets": (target(finished=False),)}, "its attack did not finish"),
        ({"targets": (target(inputs_tried=L4_MIN_INPUTS - 1),)}, "inputs tried"),
        ({"properties": (prop(origin="docstring"),)}, "no counted model property"),
        ({"properties": (prop(constrains_result=False),)}, "no counted model property"),
        ({"properties": (prop(status="rejected"),)}, "no counted model property"),
        ({"properties": (prop(target="t2"),)}, "no counted model property"),
        ({"targets": (target(reached=((PATH, (3,)),)),)}, "fix lines 4 were never run"),
        ({"fix_lines": (*FIX_LINES, ("pkg/other.py", (9,)))}, "pkg/other.py: fix lines 9"),
    ],
)
def test_each_l4_condition_alone_closes_the_gate(changed: dict[str, object], says: str) -> None:
    gate = l4_gate(attack(**changed))
    assert not gate.allowed
    assert any(says in r for r in gate.reasons), gate.reasons


def test_every_target_needs_its_own_property() -> None:
    both = attack(targets=(target("t1"), target("t2")), properties=(prop("t1"),))
    gate = l4_gate(both)
    assert gate.reasons == ("pkg.calc.f_t2: no counted model property constrains its result",)


def test_no_attack_closes_l4() -> None:
    assert l4_gate(None) == Gate(False, ("Break My Fix did not run",))


# --- facts read from the stages -------------------------------------------------------------------


def test_a_run_meeting_every_condition_is_l4() -> None:
    assert level(l4_run()).level is L.L4


def test_a_confirmed_regression_is_a_counterexample() -> None:
    rung = level(l4_run(regressions=regressions(regression())))
    assert rung.level is L.COUNTEREXAMPLE
    assert rung.reasons == ("regression: tests/test_other.py::test_total passed before the fix "
                            "and fails after it",)  # fmt: skip


def test_an_inconclusive_regression_check_is_not_a_counterexample() -> None:
    unsure = RegressionResult(RegressionStatus.INCONCLUSIVE, "a run timed out")
    rung = level(l4_run(regressions=unsure))
    assert rung.level is L.L3  # not a counterexample; it only keeps L4 out of reach
    assert rung.reasons[-1] == "not L4: the no-regression check was inconclusive: a run timed out"


@pytest.mark.parametrize(
    ("overrides", "says"),
    [
        ({"integrity": None}, "the integrity stage failed inside Tracefix"),
        ({"regressions": None}, "the regressions stage failed inside Tracefix"),
        ({"integrity": IntegrityResult(IntegrityStatus.INCONCLUSIVE, "a run timed out")},
         "the integrity audit was inconclusive: a run timed out"),
        ({"regressions": RegressionResult(RegressionStatus.INCONCLUSIVE, "a run timed out")},
         "the no-regression check was inconclusive: a run timed out"),
    ],
)  # fmt: skip
def test_l4_needs_the_integrity_audit_and_the_no_regression_check(
    overrides: dict[str, object], says: str
) -> None:
    """Either one failing or inconclusive could hide a counterexample (verifier S1)."""
    rung = level(l4_run(**overrides))
    assert rung.level is L.L3
    assert any(r.startswith(f"not L4: {says}") for r in rung.reasons), rung.reasons


def test_a_missing_audit_stage_closes_l4() -> None:
    record = l4_run()
    record = replace(record, stages=tuple(s for s in record.stages if s.name != "integrity"))
    assert level(record).reasons[-1] == "not L4: the integrity stage did not run"


@pytest.mark.parametrize(
    "overrides",
    [{"integrity": IntegrityResult(IntegrityStatus.SKIPPED, "the fix changes no test file")},
     {"regressions": RegressionResult(RegressionStatus.SKIPPED, "no test passed before")}],
)  # fmt: skip
def test_a_skipped_audit_keeps_l4(overrides: dict[str, object]) -> None:
    assert level(l4_run(**overrides)).level is L.L4


@pytest.mark.parametrize(
    "overrides",
    [
        {"reproduce": repro(ReproStatus.FIX_DOES_NOT_FIX)},
        {"integrity": integrity(flag())},
        {"break_my_fix": attack(status=AttackStatus.FOUND, findings=(finding(),))},
    ],
)
def test_each_kind_of_counterexample(overrides: dict[str, object]) -> None:
    assert level(l4_run(**overrides)).level is L.COUNTEREXAMPLE


def test_a_counterexample_stays_with_tampering_elsewhere() -> None:
    found = l4_run(break_my_fix=attack(status=AttackStatus.FOUND, findings=(finding(),)))
    tampered = replace(found, stages=(*found.stages, stage("fix_line_coverage", None, "invalid")))
    assert level(tampered).level is L.COUNTEREXAMPLE


def test_tampering_in_any_stage_caps_at_l0() -> None:
    tampered = stage("fix_line_coverage", None, "invalid", reason="a file changed in src")
    passing = l4_run()
    rung = level(replace(passing, stages=(*passing.stages, tampered)))
    assert rung.level is L.L0
    assert rung.reasons[0] == "tampering detected in fix_line_coverage (a file changed in src)"


def test_findings_of_an_invalid_stage_do_not_count() -> None:
    invalid = attack(status=AttackStatus.INVALID, findings=(finding(),))
    rung = level(l4_run(break_my_fix=invalid))
    assert rung.level is L.L0
    assert "tampering detected in break_my_fix" in rung.reasons[0]


@pytest.mark.parametrize("status", [RunStatus.ENVIRONMENT_ERROR, RunStatus.INVALID,
                                    RunStatus.ERROR])  # fmt: skip
def test_a_stopped_run_is_l0_whatever_its_stages_say(status: RunStatus) -> None:
    stopped = replace(l4_run(), status=status, status_reason="the base suite cannot run")
    assert level(stopped) == climb(Facts(stopped="the base suite cannot run"))


def test_a_stage_that_raised_gives_no_evidence() -> None:
    rung = level(l4_run(guard=None))
    assert rung.level is L.L1
    assert "not L2: the guard stage failed inside Tracefix, so it gives no evidence" in rung.reasons


def test_a_stage_that_did_not_run() -> None:
    record = l4_run()
    without = replace(record, stages=tuple(s for s in record.stages if s.name != "reproduce"))
    assert facts(without).reproduced == Gate(False, ("the reproduce stage did not run",))


def test_the_gates_read_each_stage_status() -> None:
    assert level(l4_run(reproduce=repro(ReproStatus.NOT_REPRODUCED))).level is L.L0
    assert level(l4_run(guard=guard(GuardStatus.INCONCLUSIVE))).level is L.L1
    assert level(l4_run(behaviour_diff=behaviour(l3=False))).level is L.L2
    assert level(l4_run(break_my_fix=attack(targets=(target(finished=False),)))).level is L.L3


def test_an_empty_run_is_l0() -> None:
    assert level(run()).level is L.L0
    assert level(run(StageRecord("environment", "ok", "base suite passed"))).level is L.L0


# --- the last receipt's findings (M9, developer, 14 Oct 2026) -----------------------------------


def _replayed(*results: Replay, status: PreviousStatus = PreviousStatus.REPLAYED) -> StageRecord:
    found = tuple(Replayed(i, f"parse_port(raw='{i}')", f"findings/finding_{i}.py", r, "ran")
                  for i, r in enumerate(results, start=1))  # fmt: skip
    result = PreviousResult(status, f"{status.value} for the test", "c" * 40, "COUNTEREXAMPLE",
                            "2026-10-14T09:00:00+00:00", found)  # fmt: skip
    return stage(PREVIOUS, result)


def _with(record: RunRecord, previous: StageRecord) -> RunRecord:
    return replace(record, stages=(record.stages[0], previous, *record.stages[1:]))


def test_without_previous_the_gate_is_open() -> None:
    assert previous_gate(l4_run()) == Gate(True)


@pytest.mark.parametrize(
    "previous",
    [_replayed(Replay.FIXED, Replay.FIXED), _replayed(status=PreviousStatus.SKIPPED)],
)
def test_every_old_finding_fixed_keeps_l4(previous: StageRecord) -> None:
    assert level(_with(l4_run(), previous)).level is L.L4


def test_an_old_finding_that_still_fails_keeps_l4_out_of_reach() -> None:
    rung = level(_with(l4_run(), _replayed(Replay.FIXED, Replay.STILL_FAILS)))
    assert rung.level is L.L3
    assert rung.reasons[-1] == (
        "not L4: finding 2 of the last receipt (parse_port(raw='2')) still fails on this commit"
    )


@pytest.mark.parametrize("status", [PreviousStatus.INCONCLUSIVE, PreviousStatus.REPLAYED])
def test_a_replay_that_could_not_show_a_fix_closes_l4(status: PreviousStatus) -> None:
    results = () if status is PreviousStatus.INCONCLUSIVE else (Replay.UNFINISHED,)
    rung = level(_with(l4_run(), _replayed(*results, status=status)))
    assert rung.level is L.L3


def test_a_replay_that_raised_closes_l4() -> None:
    failed = StageRecord(PREVIOUS, "error", "Tracefix raised", error="KeyError: 'x'")
    rung = level(_with(l4_run(), failed))
    assert rung.level is L.L3
    assert "the previous stage failed inside Tracefix" in rung.reasons[-1]


def test_tampering_while_replaying_caps_at_l0() -> None:
    rung = level(_with(l4_run(), _replayed(status=PreviousStatus.INVALID)))
    assert rung.level is L.L0 and rung.reasons[0].startswith("tampering detected in previous")


run_strategy = st.sampled_from([
    {},
    {"break_my_fix": attack(status=AttackStatus.FOUND, findings=(finding(),))},
    {"reproduce": repro(ReproStatus.NOT_REPRODUCED)},
    {"reproduce": repro(ReproStatus.FIX_DOES_NOT_FIX)},
    {"guard": guard(GuardStatus.INCONCLUSIVE)},
    {"behaviour_diff": behaviour(l3=False)},
    {"break_my_fix": attack(targets=(target(finished=False),))},
    {"integrity": integrity(flag())},
]).map(lambda overrides: l4_run(**overrides))  # fmt: skip


@given(run_strategy, st.lists(st.sampled_from(list(Replay)), max_size=5),
       st.sampled_from([PreviousStatus.REPLAYED, PreviousStatus.SKIPPED,
                        PreviousStatus.INCONCLUSIVE]))  # fmt: skip
def test_old_findings_only_ever_close_l4(record: RunRecord, results: list[Replay],
                                         status: PreviousStatus) -> None:  # fmt: skip
    """Whatever the replay shows, it changes nothing below L4 and never makes a COUNTEREXAMPLE:
    this run's own stages decide that."""
    without = level(record).level
    found = results if status is PreviousStatus.REPLAYED else []
    with_previous = level(_with(record, _replayed(*found, status=status))).level
    if without is not L.L4:
        assert with_previous is without
    else:
        shown_fixed = status is PreviousStatus.SKIPPED or (
            status is PreviousStatus.REPLAYED and all(r is Replay.FIXED for r in found)
        )
        assert with_previous is (L.L4 if shown_fixed else L.L3)
