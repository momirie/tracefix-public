"""receipt.json (plan P12): built from synthetic stage results; no machine path leaves it."""

import hashlib
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

import pytest
import receipt_schema
from synthetic import (
    PATH,
    attack,
    behaviour,
    finding,
    flag,
    guard,
    integrity,
    l4_run,
    mutant,
    regression,
    regressions,
    repro,
    run,
    run_result,
    stage,
    target,
)

from tracefix.attack import AttackStatus, Doubt
from tracefix.attack_rules import Expectation
from tracefix.behaviour_diff import SurvivorCheck
from tracefix.behaviour_rules import UNOBSERVED, Change, ChangeGroup, Kind, Seen
from tracefix.envcheck import OriginCheck
from tracefix.guard import MutantResult, MutantStatus
from tracefix.judge import JudgeResult, JudgeStatus, Label
from tracefix.ladder import EvidenceLevel, level
from tracefix.llm import CallRecord, Problem
from tracefix.previous import PreviousResult, PreviousStatus, Replay, Replayed
from tracefix.receipt import (
    COST_LABEL,
    MAX_COMMANDS,
    MAX_DIFF_LINES,
    NOT_CHECKED,
    NOT_THE_FIX,
    Receipt,
    build,
    summary_facts,
)
from tracefix.record import PREVIOUS, RunRecord, RunStatus, StageRecord
from tracefix.repro import ReproStatus
from tracefix.runner import EnvStatus
from tracefix.sandbox import BASIC_WARNING
from tracefix.workspace import Workspace


@pytest.fixture
def ws(tmp_path: Path) -> Workspace:
    """Only the folders matter: the receipt masks them."""
    repo = tmp_path / "my repo"
    repo.mkdir()
    workspace = Workspace(repo, "main", "fix")
    workspace.root = tmp_path / "tracefix-work"
    workspace.copies = [tmp_path / "tracefix-abc" / "repo", tmp_path / "tracefix-def" / "repo"]
    return workspace


def _strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [s for v in value for s in _strings(v)]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _strings(v)]
    return []


def test_no_machine_path_leaves_the_machine(ws: Workspace) -> None:
    repo, copy = ws.repo, ws.copies[1]
    home, temp = Path.home(), Path(tempfile.gettempdir())
    leaky = [str(repo / "src" / "calc.py"), repo.as_posix() + "/src/calc.py",
             str(copy / "tests" / "test_x.py"), str(home / ".cache" / "x"),
             str(temp / "pytest-1" / "x.py"), str(ws.root / "scratch")]  # fmt: skip
    # As an OSError's message holds them (a repr: doubled backslashes on Windows).
    leaky += [f"No such file or directory: {str(copy / 'data.json')!r}", repr(str(home / "x"))]
    # And as pytest shows an assertion on such a message (a repr of a repr: verifier round 2).
    leaky.append(repr(f"[Errno 2] No such file or directory: {str(home / 'proj' / 'd.txt')!r}"))
    text = " and ".join(leaky)
    run_ = l4_run(
        reproduce=repro(reason=f"failed at {text}"),
        break_my_fix=attack(status=AttackStatus.FOUND, findings=(
            finding(outcome={"kind": "raised", "type": "OSError", "message": text}),)),
    )  # fmt: skip
    records = [replace(s, problems=(Problem("adversary", "m", "network", None, text),))
               for s in run_.stages]  # fmt: skip
    suite = run_result(sys.executable, "-m", "pytest", str(copy / "tests"))
    records.append(stage("environment", suite, "ok", reason=text))
    record = replace(run_, stages=tuple(records), notes=(text,), warnings=(text,))
    dumped = build(record, ws).model_dump(mode="json")
    strings = _strings(dumped)
    forbidden = [str(p) for p in (repo, copy.parent, home, temp, ws.root)]
    forbidden += [Path(p).as_posix() for p in forbidden] + [sys.executable]
    forbidden += [p.replace("\\", "\\\\") for p in forbidden]
    forbidden += [p.replace("\\\\", "\\\\\\\\") for p in forbidden if "\\\\" in p]
    for s in strings:
        for path in forbidden:
            assert path.lower() not in s.lower(), (path, s)
    assert any("<repo>/src/calc.py" in s for s in strings)
    assert "python -m pytest <work>/repo/tests" in dumped["stages"][-1]["commands"]


def test_values_that_look_like_addresses_or_timings_stay(ws: Workspace) -> None:
    found = finding(input=(("x", "0x1f"),), outcome={"kind": "returned", "repr": "'in 2.5s'"})
    built = build(l4_run(break_my_fix=attack(status=AttackStatus.FOUND, findings=(found,))), ws)
    assert built.findings[0].input == {"x": "0x1f"}
    assert built.findings[0].call == "f_t1(x=0x1f)"
    assert built.findings[0].outcome == "returns 'in 2.5s'"


def test_the_level_comes_from_the_ladder(ws: Workspace) -> None:
    for record in (l4_run(), l4_run(regressions=regressions(regression())), run()):
        built = build(record, ws)
        rung = level(record)
        assert (built.level, built.level_reasons) == (rung.level, list(rung.reasons))
        assert built.summary.by == "tracefix"
        assert built.summary.text.startswith(rung.level.value)


def test_top_level_facts(ws: Workspace) -> None:
    record = l4_run()
    built = build(record, ws)
    assert built.schema_version == 1
    assert (built.base.ref, built.head.sha) == ("main", "b" * 40)
    assert built.issue.title == "f returns a negative number"
    assert built.issue.sha256 == hashlib.sha256(record.issue.encode()).hexdigest()
    assert built.status is RunStatus.OK
    assert [s.name for s in built.stages] == [s.name for s in record.stages]


def test_the_basic_isolation_warning_shows_exactly_when_basic(ws: Workspace) -> None:
    basic = build(l4_run(), ws)
    assert basic.isolation.level == "basic"
    assert basic.isolation.warning == BASIC_WARNING
    with_warning = replace(l4_run(), warnings=(BASIC_WARNING, "another"))
    assert build(with_warning, ws).warnings == ["another"]  # shown once, under isolation
    strict = build(replace(l4_run(), isolation="strict", isolation_why="bubblewrap works"), ws)
    assert strict.isolation.warning is None


def test_findings_and_their_files(ws: Workspace) -> None:
    found = (finding(1), finding(2, repro_code=""))
    pre = (finding(3),)
    built = build(l4_run(break_my_fix=attack(status=AttackStatus.FOUND, findings=found,
                                             pre_existing=pre)), ws)  # fmt: skip
    assert [f.file for f in built.findings] == ["findings/finding_1.py", None]
    assert built.findings[0].property is not None
    assert built.findings[0].property.claim == "result >= 0"
    assert built.findings[0].base_outcome == "returns -1"
    assert [(f.number, f.file) for f in built.pre_existing] == [(3, None)]
    # Where each finding points, and the failure its file must end with (M9 annotations, replay).
    assert (built.findings[0].path, built.findings[0].line, built.findings[0].expect) == (
        None, None, None)  # fmt: skip
    expect = Expectation(frozenset({"ValueError", "AssertionError"}), True)
    located = finding(1, path=PATH, line=3, expect=expect)
    entry = build(l4_run(break_my_fix=attack(status=AttackStatus.FOUND, findings=(located,))),
                  ws).findings[0]  # fmt: skip
    assert (entry.path, entry.line) == (PATH, 3)
    assert entry.expect is not None
    assert (entry.expect.types, entry.expect.in_file) == (["AssertionError", "ValueError"], True)


def test_flags_and_regressions(ws: Workspace) -> None:
    built = build(l4_run(integrity=integrity(flag(), flag()),
                         regressions=regressions(regression())), ws)  # fmt: skip
    assert [f.id for f in built.integrity_flags] == ["f1", "f2"]
    assert built.integrity_flags[0].note is None
    assert built.regressions[0].test == "test_total"
    assert built.regressions[0].line is None
    located = build(l4_run(regressions=regressions(replace(regression(), line=9))), ws)
    assert located.regressions[0].line == 9


def test_fix_does_not_fix_names_the_model_behind_it(ws: Workspace) -> None:
    built = build(l4_run(reproduce=repro(ReproStatus.FIX_DOES_NOT_FIX)), ws)
    entry = built.stages[0]
    assert entry.reason.endswith("This rests on a test written by the model claude-sonnet-5-5.")
    assert entry.evidence["oracle"] == "a test written by the model claude-sonnet-5-5"
    assert entry.evidence["test_file"] == "repro/test_tracefix_repro.py"


def test_survivors_are_changes_no_test_noticed_with_stable_ids(ws: Workspace) -> None:
    long_diff = "\n".join(f"+line {i}" for i in range(50))
    mutants = (mutant(1), mutant(2, MutantStatus.KILLED), mutant(3, line=9, diff=long_diff,
                                                                replacement="y" * 300))  # fmt: skip
    check = SurvivorCheck(1, "model", PATH, 3, "differs", examples=(("f(x=0)", "0", "1"),))
    built = build(l4_run(guard=guard(mutants=mutants),
                         behaviour_diff=behaviour(survivors=(check,))), ws)  # fmt: skip
    first, third = built.survivors
    assert first.id == mutants[0].mutant.id
    assert first.words.startswith("pkg/calc.py:3: changing `x < 0` to `x <= 0` made no test fail")
    assert "behaves differently from the fix" in first.words
    assert first.examples[0].mutant == "1"
    assert third.check == "not_checked"
    assert len(third.replacement) == 203
    assert len(third.diff.splitlines()) == MAX_DIFF_LINES + 1
    # The same edit has the same id in another run, whatever its number there.
    again = build(l4_run(guard=guard(mutants=(mutant(7),))), ws)
    assert again.survivors[0].id == first.id
    assert built.stages[1].evidence["killed_ids"] == [mutants[1].mutant.id]


def rule_mutant(number: int, kind: str, status: MutantStatus = MutantStatus.KILLED) -> MutantResult:
    return mutant(number, status, origin="rule", kind=kind, replacement=f"x <= {number}")


def test_rule_mutants_are_reported_by_kind_and_kinds_with_no_place_are_named(ws: Workspace) -> None:
    rules = (
        rule_mutant(1, "compare"),
        rule_mutant(2, "compare"),
        rule_mutant(3, "compare", MutantStatus.SURVIVED),
        rule_mutant(4, "drop_call", MutantStatus.SURVIVED),
        rule_mutant(5, "reraise", MutantStatus.DISCARDED),  # ran, but judged nothing
    )
    built = build(l4_run(guard=guard(rule_mutants=rules)), ws)
    evidence = built.stages[1].evidence
    assert evidence["rule_kinds"] == ["compare: 2 of 3 killed", "drop_call: 0 of 1 killed",
                                      "reraise: 0 of 0 killed"]  # fmt: skip
    assert evidence["rule_kinds_absent"] == ["body", "logic", "negate_if", "constant",
                                             "arithmetic", "membership", "loop"]  # fmt: skip
    assert [(s.origin, s.kind) for s in built.survivors] == [("rule", "compare"),
                                                             ("rule", "drop_call")]  # fmt: skip


def test_a_model_survivor_has_no_kind_and_no_rule_mutant_claims_no_absent_kind(
    ws: Workspace,
) -> None:
    # No rule mutant at all may mean their step failed (a note): nothing is claimed about kinds.
    built = build(l4_run(guard=guard(mutants=(mutant(1),))), ws)
    assert built.survivors[0].kind is None
    assert built.stages[1].evidence["rule_kinds"] == []
    assert built.stages[1].evidence["rule_kinds_absent"] == []


def test_guards_evidence_counts_the_mutants_left_unrun(ws: Workspace) -> None:
    """Guard's early stop (M11): the receipt says how many model mutants were never run. The
    benchmark reads it to tell a stopped run from one played to the end (M11's mutant target),
    and nothing else did until S11's teeth check reported 0 for it unnoticed."""
    ran = (mutant(1), mutant(2), mutant(3, MutantStatus.DISCARDED))
    left = (mutant(4).mutant, mutant(5).mutant)
    stopped = build(l4_run(guard=guard(mutants=ran, not_run=left)), ws).stages[1].evidence
    assert (stopped["mutants"], stopped["discarded"], stopped["not_run"]) == (2, 1, 2)
    played_out = build(l4_run(guard=guard(mutants=ran)), ws).stages[1].evidence
    assert played_out["not_run"] == 0


def test_kinds_never_touch_a_mutants_id(ws: Workspace) -> None:
    plain = mutant(1, MutantStatus.SURVIVED, origin="rule")
    kinded = mutant(1, MutantStatus.SURVIVED, origin="rule", kind="compare")
    assert plain.mutant.id == kinded.mutant.id


def test_problems_are_shown_on_the_stage_they_hurt(ws: Workspace) -> None:
    limited = Problem("adversary", "claude-opus-5-5", "rate_limit", 429, "RateLimitError: slow")
    record = l4_run()
    stages = tuple(replace(s, problems=(limited,)) if s.name == "break_my_fix" else s
                   for s in record.stages)  # fmt: skip
    budget = Problem("judge", "claude-opus-5-5", "budget", None, "BudgetExceeded: 40 calls")
    built = build(replace(record, stages=stages, problems=(budget,)), ws)
    by_name = {s.name: s for s in built.stages}
    assert [p.words for p in by_name["break_my_fix"].problems] == [
        f"the API account's rate limit was reached (HTTP 429): {NOT_THE_FIX}"]  # fmt: skip
    assert all(not s.problems for s in built.stages if s.name != "break_my_fix")
    assert [(p.stage, p.kind) for p in built.llm.problems] == [
        ("break_my_fix", "rate_limit"), ("summary", "budget")]  # fmt: skip


def test_cost_is_labelled_and_unknown_models_named(ws: Workspace) -> None:
    calls = (CallRecord("reproducer", "claude-sonnet-5-5", 1_000_000, 100_000, 1.0, True),)
    built = build(replace(l4_run(), calls=calls), ws)
    assert (built.llm.cost_estimate.usd, built.llm.cost_estimate.label) == (3.0, COST_LABEL)
    assert (built.llm.calls, built.llm.input_tokens, built.llm.output_tokens) == (1, 10**6, 10**5)
    unknown = (*calls, CallRecord("judge", "claude-new-9", 10, 10, 1.0, True))
    cost = build(replace(l4_run(), calls=unknown), ws).llm.cost_estimate
    assert cost.usd is None
    assert cost.label == "unknown: no list price for claude-new-9"
    assert build(l4_run(), ws).llm.settings.models["adversary"] == "claude-opus-5-5"


def test_unchecked_lists_the_limits_and_what_did_not_run(ws: Workspace) -> None:
    record = l4_run(guard=None)
    skipped = StageRecord("integrity", "skipped", "the fix changes no test file")
    stages = tuple(skipped if s.name == "integrity" else s for s in record.stages)
    unchecked = build(replace(record, stages=stages), ws).unchecked
    assert unchecked[: len(NOT_CHECKED)] == list(NOT_CHECKED)
    assert f"not observed by the behaviour diff: {UNOBSERVED[0]}" in unchecked
    assert "environment: did not run" in unchecked
    assert "guard: failed inside Tracefix" in unchecked
    assert "integrity: skipped (the fix changes no test file)" in unchecked


def test_unchecked_names_the_files_the_origin_check_could_not_check(ws: Workspace) -> None:
    check = OriginCheck(EnvStatus.OK, "", (), (), ("src/ns/m.py",))
    record = l4_run()
    record = replace(record, stages=(stage("import_check", check), *record.stages))
    unchecked = build(record, ws).unchecked
    assert any(
        u.startswith("the import origin check could not check src/ns/m.py") for u in unchecked
    )


def test_behaviour_changes_with_the_judges_labels(ws: Workspace) -> None:
    before = Seen({"kind": "returned", "type": "int", "text": "-1"})
    after = Seen({"kind": "returned", "type": "int", "text": "0"})
    change = Change("t1", 0, (("x", "-1"),), "explicit", Kind.VALUE, before, after,
                    explains=("the issue calls f(-1)",), id="c1")  # fmt: skip
    group = ChangeGroup(change.group_key, Kind.VALUE, (change,), (change,))
    labels = (Label("c1", "intended", "the issue's case"), Label("c9", "suspicious", "no such"))
    judged = JudgeResult(JudgeStatus.LABELLED, labels)
    built = build(l4_run(behaviour_diff=behaviour(groups=(group,), judge=judged)), ws)
    (entry,) = built.behaviour_changes
    assert (entry.function, entry.kind, entry.count) == ("t1", "value", 1)
    assert (entry.before, entry.after) == ("returns -1", "returns 0")
    assert entry.explained == ["the issue calls f(-1)"]
    assert [lab.change for lab in entry.labels] == ["c1"]
    assert entry.examples[0].call == "t1(x=-1)"


def test_tampering_is_listed(ws: Workspace) -> None:
    record = l4_run()
    tampered = StageRecord("fix_line_coverage", "invalid", "a file changed: src/x.py")
    built = build(replace(record, stages=(*record.stages, tampered)), ws)
    assert [(t.stage, t.detail) for t in built.tampering] == [
        ("fix_line_coverage", "a file changed: src/x.py")]  # fmt: skip
    assert built.level is EvidenceLevel.L0
    stopped = run(status=RunStatus.INVALID, status_reason="a file changed during the base run")
    assert build(stopped, ws).tampering[0].stage == "environment"


def test_commands_are_distinct_and_capped(ws: Workspace) -> None:
    runs = tuple((f"set {i}", run_result("python", "-m", "pytest", f"t{i % 30}.py"))
                 for i in range(60))  # fmt: skip
    built = build(l4_run(regressions=replace(regressions(), runs=runs)), ws)
    commands = next(s for s in built.stages if s.name == "regressions").commands
    assert len(commands) == MAX_COMMANDS + 1
    assert commands[-1] == "... 10 more commands"


def test_a_stage_error_is_recorded(ws: Workspace) -> None:
    built = build(l4_run(guard=None), ws)
    entry = next(s for s in built.stages if s.name == "guard")
    assert (entry.status, entry.error, entry.evidence) == ("error", "KeyError: 'x'", {})


def test_round_trip(ws: Workspace) -> None:
    record: RunRecord = l4_run(integrity=integrity(flag()), guard=guard(mutants=(mutant(),)))
    built = build(record, ws)
    assert Receipt.model_validate_json(built.model_dump_json()) == built


def test_a_receipt_without_the_m9_fields_still_validates(ws: Workspace) -> None:
    # Schema v1 readers and M8-era receipts: every field M9 added is optional.
    found = (finding(1, path=PATH, line=3, expect=Expectation(frozenset(), None)),)
    record = l4_run(break_my_fix=attack(status=AttackStatus.FOUND, findings=found),
                    regressions=regressions(replace(regression(), line=9)))  # fmt: skip
    data = build(record, ws).model_dump(mode="json")
    for entry in data["findings"]:
        del entry["path"], entry["line"], entry["expect"]
    for entry in data["regressions"]:
        del entry["line"]
    del data["previous"]
    old = Receipt.model_validate(data)
    assert (old.findings[0].path, old.findings[0].expect, old.regressions[0].line) == (
        None, None, None)  # fmt: skip


def test_break_my_fix_targets_and_their_inputs_are_listed(ws: Workspace) -> None:
    """M11 S1: every target, with the inputs run against it, whether its attack finished and
    why it was not attacked; never anything that sets the level."""
    targets = (
        target("t1"),
        target("t2", function="pkg.calc._helper", attacked=False, inputs_tried=0,
               reason=f"no property to check it against in {ws.repo}"),
        target("t3", finished=False, inputs_tried=7, via="a public caller of the changed _p"),
    )  # fmt: skip
    record = l4_run(break_my_fix=attack(targets=targets))
    built = build(record, ws)
    assert built.attack_targets is not None
    assert [(t.function, t.path, t.attacked, t.inputs_tried, t.finished)
            for t in built.attack_targets] == [
        ("pkg.calc.f_t1", PATH, True, 150, True), ("pkg.calc._helper", PATH, False, 0, True),
        ("pkg.calc.f_t3", PATH, True, 7, False),
    ]  # fmt: skip
    assert built.attack_targets[1].reason == "no property to check it against in <repo>"
    assert built.attack_targets[2].via == "a public caller of the changed _p"
    assert built.level is level(record).level  # the ladder's, as before
    assert build(run(), ws).attack_targets is None  # Break My Fix left no result


def test_a_receipt_without_the_m11_fields_still_validates(ws: Workspace) -> None:
    data = build(l4_run(), ws).model_dump(mode="json")
    assert data["attack_targets"]
    del data["attack_targets"]
    assert Receipt.model_validate(data).attack_targets is None


def test_the_committed_schema_is_current() -> None:
    committed = receipt_schema.SCHEMA_FILE.read_text(encoding="utf-8")
    assert committed == receipt_schema.text(), "run: uv run python scripts/receipt_schema.py"


# --- the last receipt's findings (M9) -----------------------------------------------------------


def _replay_stage(status: PreviousStatus = PreviousStatus.REPLAYED, head: str = "c" * 40
                  ) -> StageRecord:  # fmt: skip
    found = (Replayed(1, "parse_port(raw='')", "findings/finding_1.py", Replay.STILL_FAILS,
                      "failed: assert 0 == 8080"),
             Replayed(2, "parse_port(raw=' ')", "findings/finding_2.py", Replay.FIXED,
                      "passed 3 times in a row"))  # fmt: skip
    result = PreviousResult(status, "replayed for the test", head, "COUNTEREXAMPLE",
                            "2026-10-14T09:00:00+00:00", found if head else ())  # fmt: skip
    return stage(PREVIOUS, result)


def _with_replay(previous: StageRecord) -> RunRecord:
    record = l4_run()
    return replace(record, stages=(record.stages[0], previous, *record.stages[1:]))


def test_the_replay_is_in_the_receipt(ws: Workspace) -> None:
    built = build(_with_replay(_replay_stage()), ws)
    assert built.previous is not None
    assert built.previous.head_sha == "c" * 40
    assert built.previous.level is EvidenceLevel.COUNTEREXAMPLE
    assert [(f.number, f.result.value) for f in built.previous.findings] == [
        (1, "still_fails"), (2, "fixed")]  # fmt: skip
    entry = next(s for s in built.stages if s.name == PREVIOUS)
    assert entry.evidence == {"findings": 2, "fixed": 1, "last_level": "COUNTEREXAMPLE"}
    assert [s.name for s in built.stages][:2] == ["reproduce", PREVIOUS]
    assert built.level is EvidenceLevel.L3
    assert Receipt.model_validate_json(built.model_dump_json()) == built


def test_without_a_replay_there_is_no_previous(ws: Workspace) -> None:
    built = build(l4_run(), ws)
    assert built.previous is None
    assert not any(u.startswith(PREVIOUS) for u in built.unchecked)


def test_an_unreadable_last_receipt_is_listed_as_unchecked(ws: Workspace) -> None:
    unreadable = PreviousResult(PreviousStatus.INCONCLUSIVE, "the last receipt can't be used: x")
    built = build(_with_replay(stage(PREVIOUS, unreadable)), ws)
    assert built.level is EvidenceLevel.L3
    # Kept, so the next run knows it can't tell which findings are open (verifier M9 B2).
    assert built.previous is not None
    assert (built.previous.head_sha, built.previous.level) == ("", None)
    assert built.previous.still_open_known is False
    skipped = build(_with_replay(_replay_stage(PreviousStatus.SKIPPED, head="")), ws)
    assert "previous: skipped (replayed for the test)" in skipped.unchecked


def test_the_judge_reads_the_same_facts_with_or_without_the_replay(ws: Workspace) -> None:
    every_fixed = replace(_replay_stage(), result=PreviousResult(
        PreviousStatus.SKIPPED, "the last receipt has no findings", "c" * 40, "L2",
        "2026-10-14T09:00:00+00:00"))  # fmt: skip
    plain, replayed = build(l4_run(), ws), build(_with_replay(every_fixed), ws)
    assert replayed.previous is not None and plain.level is replayed.level
    assert summary_facts(plain) == summary_facts(replayed)


@pytest.mark.parametrize("doubt", ["refused", "os_limit", "finished_object"])
def test_s5_a_doubt_flag_shows_and_changes_no_level_and_nothing_the_judge_reads(
    ws: Workspace, doubt: Doubt
) -> None:
    def receipt(flag: Doubt | None) -> Receipt:
        flagged = finding(1, doubt=flag)
        return build(l4_run(break_my_fix=attack(status=AttackStatus.FOUND, findings=(flagged,),
                                                pre_existing=(replace(flagged, number=2),))),
                     ws)  # fmt: skip

    plain, flagged = receipt(None), receipt(doubt)
    assert flagged.findings[0].doubt == doubt and flagged.pre_existing[0].doubt == doubt
    assert plain.findings[0].doubt is None
    assert flagged.level is plain.level and flagged.level_reasons == plain.level_reasons
    assert flagged.status == plain.status and flagged.stages == plain.stages
    assert summary_facts(flagged) == summary_facts(plain)


def test_s5_a_receipt_written_before_doubt_still_validates(ws: Workspace) -> None:
    found = attack(status=AttackStatus.FOUND, findings=(finding(1),))
    written = build(l4_run(break_my_fix=found), ws).model_dump(mode="json")
    del written["findings"][0]["doubt"]
    assert Receipt.model_validate(written).findings[0].doubt is None
