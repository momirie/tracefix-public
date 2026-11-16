"""The benchmark's numbers (M10 plan P7, P8, P9): rates from runs, receipts and labels. Only the
developer's labels count; an unlabelled finding is never a false alarm or a find; every rate
carries its count; report.md is rebuilt byte for byte from summary.json."""

from __future__ import annotations

import json
import shutil
from fractions import Fraction
from pathlib import Path
from typing import Any

import bench_fakes
import benchmark
import pytest
from bench import data, report
from bench.patches import Label
from bench.prepare import Prepared, Reason, Touched, TriedAgent, TriedVariant
from bench.report import FindingLabel, Labels, Run
from bench.run import Results, RunLine
from bench_fakes import CREATED_AT, case, ready, receipt, task, tried
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from tracefix.receipt import AttackTargetEntry, Receipt, RegressionEntry

ID = "tracefix__synthetic-1"
LEVELS = ("COUNTEREXAMPLE", "L1", "L2", "L3", "L4")


def line(kind: str = "gold", instance_id: str = ID, repeat: int = 1, **changes: Any) -> RunLine:
    facts = {"instance_id": instance_id, "kind": kind, "repeat": repeat, "live": True,
             "variant": "gold" if kind == "gold" else "v0", "outcome": "receipt"}  # fmt: skip
    return RunLine.model_validate_json(json.dumps({**facts, **changes}))  # as runs.jsonl is read


def replayed(*results: str) -> dict[str, Any]:
    found = [{"number": n, "carried": False, "result": r} for n, r in enumerate(results, 1)]
    return {"status": "replayed", "isolation": "strict", "findings": found}


def label(run: str, finding: int, value: str, by: str = "developer", instance_id: str = ID
          ) -> FindingLabel:  # fmt: skip
    return FindingLabel.model_validate(
        {
            "instance_id": instance_id,
            "run": run,
            "finding": finding,
            "label": value,
            "by": by,
            "receipt_created_at": CREATED_AT,
        }
    )


def by_key(*labels: FindingLabel) -> dict[tuple[str, str, int], FindingLabel]:
    return {lb.key: lb for lb in labels}


def gold_run(level: str, instance_id: str = ID) -> Run:
    return Run(line("gold", instance_id), receipt(level))


def partial_run(level: str, *replay: str, instance_id: str = ID) -> Run:
    changes = {"replay": replayed(*replay)} if replay else {}
    return Run(line("partial", instance_id, **changes), receipt(level))


# --- labels -------------------------------------------------------------------------------------


def test_every_gold_finding_needs_a_label_but_a_partial_one_fixed_on_gold_does_not() -> None:
    assert report.needs_label(gold_run("COUNTEREXAMPLE")) == [1, 2]
    assert report.needs_label(partial_run("COUNTEREXAMPLE", "fixed", "still_fails")) == [2]
    assert report.needs_label(partial_run("COUNTEREXAMPLE")) == [1, 2]  # never replayed
    assert report.needs_label(Run(line("gold", outcome="timeout"), None)) == []


def test_a_gold_counterexample_without_findings_is_labelled_as_the_run_itself() -> None:
    alone = receipt("COUNTEREXAMPLE").model_copy(update={"findings": []})
    gold = Run(line("gold"), alone)
    assert report.needs_label(gold) == [report.RUN_ITSELF]
    assert report.needs_label(Run(line("partial"), alone)) == []  # the detection we expect
    assert report.needs_label(Run(line("gold"), receipt("L1"))) == []
    added = report.with_missing(Labels(), [gold]).labels
    assert [(lb.finding, lb.label) for lb in added] == [(report.RUN_ITSELF, None)]
    assert report.gold([gold], {})["unreviewed"] == {"n": 1, "of": 1}
    marked = by_key(label("gold-r1", report.RUN_ITSELF, "false_alarm"))
    assert report.gold([gold], marked)["false_alarm"] == {"n": 1, "of": 1}
    assert report.gold([gold], marked)["unreviewed"] == {"n": 0, "of": 1}
    # on a run with findings, a label on the run itself counts for nothing
    assert report.gold([gold_run("COUNTEREXAMPLE")], marked)["false_alarm"] == {"n": 0, "of": 1}
    row = report.findings([gold], marked)
    assert [(f["finding"], f["outcome"], f["label"]) for f in row] == [
        (report.RUN_ITSELF, f"{alone.level_reasons[0]} (and 1 more)", "false_alarm")
    ]  # the fake COUNTEREXAMPLE has two reasons
    assert "| tracefix__synthetic-1 | gold-r1 | - |" in report.markdown({"findings": row}, "t")


def test_a_gold_counterexample_cause_no_finding_carries_is_labelled_as_the_run_itself() -> None:
    mixed = regressed("tests/test_calc.py", finding=True)  # finding 1 and a regression
    gold = Run(line("gold"), mixed)
    assert report.needs_label(gold) == [report.RUN_ITSELF, 1]
    assert report.needs_label(Run(line("partial"), mixed)) == [1]  # the detection we expect
    assert report.needs_label(gold_run("COUNTEREXAMPLE")) == [1, 2]  # findings are all its causes
    marked = by_key(label("gold-r1", 1, "false_alarm"))
    assert report.gold([gold], marked)["unreviewed"] == {"n": 1, "of": 1}  # the regression
    both = by_key(
        label("gold-r1", 1, "false_alarm"), label("gold-r1", report.RUN_ITSELF, "real_bug")
    )
    assert report.gold([gold], both)["unreviewed"] == {"n": 0, "of": 1}
    assert report.gold([gold], both)["real_bug_in_gold"] == {"n": 1, "of": 1}
    rows = report.findings([gold], both)
    assert [(f["finding"], f["outcome"]) for f in rows] == [
        (report.RUN_ITSELF, mixed.level_reasons[1]),
        (1, mixed.findings[0].outcome),
    ]  # the run itself shows only the cause no finding carries
    added = report.with_missing(Labels(), [gold]).labels
    assert [lb.finding for lb in added] == [report.RUN_ITSELF, 1]


def test_two_labels_for_one_finding_are_refused(tmp_path: Path) -> None:
    once = label("gold-r1", 1, "false_alarm")
    twice = (once, label("gold-r1", 1, "real_bug"))
    with pytest.raises(ValidationError, match="more than one label"):
        Labels(labels=twice)
    path = tmp_path / "slice1.json"
    path.write_text(json.dumps({"labels": [lb.model_dump() for lb in twice]}), encoding="utf-8")
    with pytest.raises(data.DataError, match="more than one label"):
        benchmark.read_labels(path)
    assert benchmark.read_labels(tmp_path / "none.json") == Labels()


def test_missing_labels_are_added_empty_and_existing_ones_kept() -> None:
    kept = label("gold-r1", 1, "false_alarm")
    labels = report.with_missing(Labels(labels=(kept,)), [gold_run("COUNTEREXAMPLE")])
    assert labels.labels[0] == kept
    assert [(lb.finding, lb.label, lb.by) for lb in labels.labels[1:]] == [(2, None, None)]
    assert report.with_missing(labels, [gold_run("COUNTEREXAMPLE")]) == labels


def test_a_label_counts_only_on_the_receipt_it_judged() -> None:
    first = receipt("COUNTEREXAMPLE")
    again = first.model_copy(update={"created_at": "2026-01-02T00:00:00+00:00"})  # tried again
    judged = Labels(labels=(label("gold-r1", 1, "false_alarm"), label("gold-r1", 2, "unclear")))
    keyed = by_key(*judged.labels)
    assert report.gold([Run(line("gold"), first)], keyed)["false_alarm"] == {"n": 1, "of": 1}
    retried = Run(line("gold"), again)
    assert report.gold([retried], keyed)["false_alarm"] == {"n": 0, "of": 1}
    assert report.gold([retried], keyed)["unreviewed"] == {"n": 1, "of": 1}
    assert [f["label"] for f in report.findings([retried], keyed)] == [None, None]
    # `label` swaps each stale entry, in place, for an empty one naming the new receipt
    fresh = report.with_missing(judged, [retried]).labels
    assert [(lb.finding, lb.label, lb.by, lb.receipt_created_at) for lb in fresh] == [
        (1, None, None, again.created_at), (2, None, None, again.created_at)
    ]  # fmt: skip
    assert fresh[0].note == f"earlier attempt ({CREATED_AT}): false_alarm by developer."
    assert report.with_missing(Labels(labels=fresh), [retried]).labels == fresh


def test_a_finding_is_reviewed_only_once_the_developer_gave_it_a_label() -> None:
    one = receipt("COUNTEREXAMPLE")
    one = one.model_copy(update={"findings": one.findings[:1]})
    receipts = {(ID, "gold", 1): one}

    def unreviewed(entry: FindingLabel) -> Any:
        return summary([line("gold")], receipts, Labels(labels=(entry,)))["gold"]["unreviewed"]

    assert unreviewed(label("gold-r1", 1, "false_alarm")) == {"n": 0, "of": 1}
    assert unreviewed(label("gold-r1", 1, "false_alarm", "claude-proposed")) == {"n": 1, "of": 1}
    # the developer's name on an entry with no label yet is not a review
    started = FindingLabel(instance_id=ID, run="gold-r1", finding=1, by="developer",
                           receipt_created_at=CREATED_AT)  # fmt: skip
    assert unreviewed(started) == {"n": 1, "of": 1}


# --- gold and partial ---------------------------------------------------------------------------


def test_a_gold_counterexample_is_a_false_alarm_only_by_the_developers_label() -> None:
    runs = [gold_run("COUNTEREXAMPLE", f"tracefix__synthetic-{i}") for i in range(1, 5)] + [
        gold_run("L4", "tracefix__synthetic-5")
    ]
    labels = by_key(
        label("gold-r1", 1, "false_alarm", instance_id="tracefix__synthetic-1"),
        label("gold-r1", 1, "false_alarm", "claude-proposed", "tracefix__synthetic-2"),
        label("gold-r1", 2, "real_bug", instance_id="tracefix__synthetic-3"),
    )  # synthetic-4: nobody looked
    found = report.gold(runs, labels)
    assert found["counterexample"] == {"n": 4, "of": 5}
    assert found["false_alarm"] == {"n": 1, "of": 5}
    assert found["false_alarm_proposed"] == {"n": 1, "of": 5}
    assert found["real_bug_in_gold"] == {"n": 1, "of": 5}
    assert found["unreviewed"] == {"n": 4, "of": 5}  # every one still has an unlabelled finding
    assert found["l4"] == {"n": 1, "of": 5}


def test_partial_detection_false_passes_and_leftovers_confirmed_on_gold() -> None:
    runs = [
        partial_run("COUNTEREXAMPLE", "fixed", "still_fails"),  # found what gold fixes
        partial_run("COUNTEREXAMPLE", "still_fails", "still_fails"),
        partial_run("L1"),
        partial_run("L2"),
        partial_run("L4"),
    ]
    found = report.partial(runs, {})
    assert found["detection"] == {"n": 2, "of": 5}
    assert found["not_green_lit"] == {"n": 3, "of": 5}
    assert found["false_pass_l2"] == {"n": 2, "of": 5}
    assert found["false_pass_l3"] == {"n": 1, "of": 5}
    assert found["leftover_found"] == {"n": 1, "of": 5}
    assert found["levels"] == {"COUNTEREXAMPLE": 2, "L0": 0, "L1": 1, "L2": 1, "L3": 0, "L4": 1}


def test_separation_compares_each_tasks_gold_and_partial_levels() -> None:
    gold = [gold_run("L4", "tracefix__synthetic-1"), gold_run("L2", "tracefix__synthetic-2"),
            gold_run("L1", "tracefix__synthetic-3")]  # fmt: skip
    partial = [partial_run("COUNTEREXAMPLE", instance_id="tracefix__synthetic-1"),
               partial_run("L2", instance_id="tracefix__synthetic-2"),
               partial_run("L4", instance_id="tracefix__synthetic-3")]  # fmt: skip
    found = report.separation(gold, partial)
    assert found == {"gold_above": {"n": 1, "of": 3}, "same": {"n": 1, "of": 3},
                     "gold_below": {"n": 1, "of": 3}}  # fmt: skip


def test_stage_numbers_come_from_the_receipts() -> None:
    runs = [gold_run("L4"), gold_run("L1"), gold_run("L3"), gold_run("L2")]
    assert report.reproducer(runs)["fail_to_pass"] == {"n": 4, "of": 4}
    assert report.guard(runs)["guarded"] == {"n": 3, "of": 4}
    assert report.break_my_fix(runs)["first_l4_blocker"] == {"<name>: its attack did not finish": 1}
    assert report.behaviour_diff(runs)["first_l3_blocker"] == {"a change nothing explains": 1}


def test_stability_counts_repeated_tasks_whose_level_verdict_guard_or_findings_differ() -> None:
    def runs(kind: str, n: int, *receipts: Receipt | None) -> list[Run]:
        instance_id = f"tracefix__synthetic-{n}"
        return [Run(line(kind, instance_id, i), r) for i, r in enumerate(receipts, 1)]

    no_findings = receipt("COUNTEREXAMPLE").model_copy(update={"findings": []})
    found = report.stability(
        runs("gold", 1, receipt("L1"), receipt("L2"))  # level and Guard
        + runs("gold", 2, receipt("COUNTEREXAMPLE"), receipt("L2"))  # level, verdict, findings
        + runs("partial", 3, receipt("COUNTEREXAMPLE"), no_findings, None)  # findings only
        + runs("partial", 1, receipt("COUNTEREXAMPLE"))  # one run: not repeated
        + runs("gold", 4, receipt("L1"), None)  # a timeout has no receipt to compare
    )
    assert found == {"groups": 3, "level_flips": {"n": 2, "of": 3},
                     "counterexample_flips": {"n": 1, "of": 3}, "guard_flips": {"n": 1, "of": 3},
                     "finding_flips": {"n": 2, "of": 3}}  # fmt: skip


def test_reasons_lose_their_run_specific_names_and_numbers() -> None:
    assert report.reason_kind("pkg.calc.f_t1: its attack did not finish") == (
        "<name>: its attack did not finish"
    )
    assert report.reason_kind("pkg/calc.py: fix lines 3, 4 were never run") == (
        "<name>: fix lines N, N were never run"
    )
    assert report.reason_kind("Break My Fix ended skipped: no callable") == (
        "Break My Fix ended skipped: no callable"
    )


# --- the whole summary --------------------------------------------------------------------------


def summary(lines: list[RunLine], receipts: dict[tuple[str, str, int], Receipt | None],
            labels: Labels | None = None, test_patch: str = "") -> dict[str, Any]:  # fmt: skip
    first = case(ID, 0)
    first = first.model_copy(update={"task": first.task.model_copy(
        update={"test_patch": test_patch})})  # fmt: skip
    cases = [first, case("tracefix__synthetic-2", 1)]
    prepared = {ID: ready(ID),
                "tracefix__synthetic-2": Prepared(instance_id="tracefix__synthetic-2",
                                                  excluded=Reason.SUITE_TOO_SLOW)}  # fmt: skip
    return report.summarise(cases, prepared, lines, receipts, labels or Labels(), reserve=3.0)


def test_the_summary_reads_each_runs_last_line_and_counts_the_funnel() -> None:
    lines = [
        line("gold", outcome="harness_error"),  # tried again:
        line("gold", cost_usd=0.5, receipt="x/gold-r1"),
        line("partial", cost_usd=None, outcome="timeout", exit_code=None),
    ]
    receipts = {(ID, "gold", 1): receipt("L4"), (ID, "partial", 1): None}
    found = summary(lines, receipts)
    assert found["funnel"]["excluded"] == {"base_suite_too_slow": 1}
    assert found["funnel"]["runs"] == {"gold": {"receipt": 1}, "partial": {"timeout": 1}}
    assert found["gold"]["l4"] == {"n": 1, "of": 1}
    assert found["partial"]["detection"] == {"n": 0, "of": 0}
    # every live attempt is spent: the harness error and the timeout count a whole reserve
    assert found["cost_and_time"]["usd_spent_live"] == 6.5
    # ... which the report also shows apart from what receipts say was spent
    assert found["cost_and_time"]["usd_spent_known"] == 0.5
    assert found["cost_and_time"]["live_attempts_cost_unknown"] == 2


def test_an_anchored_arms_spend_is_its_live_calls_not_the_receipts_estimates() -> None:
    """Replayed calls are in a receipt's estimate but cost nothing: the report says what the
    spend guard counted, or an anchored arm would look dearer than it was."""
    lines = [
        line("gold", cost_usd=5.0, live_usd=0.25, mode="anchored", receipt="x/gold-r1"),
        line("partial", cost_usd=5.0, mode="anchored", outcome="no_receipt"),  # new files lost
    ]
    found = summary(lines, {(ID, "gold", 1): receipt("L4"), (ID, "partial", 1): None})
    assert found["cost_and_time"]["usd_spent_live"] == 3.25
    assert found["cost_and_time"]["usd_spent_known"] == 0.25
    assert found["cost_and_time"]["live_attempts_cost_unknown"] == 1


def test_the_headline_reads_first_repeats_and_stability_reads_them_all() -> None:
    lines = [line("gold"), line("gold", repeat=2)]
    receipts = {(ID, "gold", 1): receipt("L4"), (ID, "gold", 2): receipt("COUNTEREXAMPLE")}
    found = summary(lines, receipts)
    assert found["gold"]["l4"] == {"n": 1, "of": 1}
    assert found["gold"]["counterexample"] == {"n": 0, "of": 1}
    assert found["stability"]["counterexample_flips"] == {"n": 1, "of": 1}


# The PR's own test patch: it edits one test file and adds another.
TEST_PATCH = (
    "diff --git a/tests/test_calc.py b/tests/test_calc.py\n"
    "--- a/tests/test_calc.py\n"
    "+++ b/tests/test_calc.py\n"
    "@@ -1 +1 @@\n"
    "-assert double(1) == 3\n"
    "+assert double(1) == 2\n"
    "diff --git a/tests/test_new.py b/tests/test_new.py\n"
    "new file mode 100644\n"
    "--- /dev/null\n"
    "+++ b/tests/test_new.py\n"
    "@@ -0,0 +1 @@\n"
    "+def test_b(): pass\n"
)


def regressed(*files: str, finding: bool = False) -> Receipt:
    """A COUNTEREXAMPLE from one regression in each of `files`, plus Break My Fix finding 1 if
    asked; its level reasons are its causes, as `ladder.climb` writes them."""
    built = receipt("COUNTEREXAMPLE")
    entries = [
        RegressionEntry(file=f, test="test_a", evidence="passed on base only") for f in files
    ]
    reasons = [f"regression: {f}::test_a passed before the fix and fails after it" for f in files]
    return built.model_copy(update={
        "findings": built.findings[:1] if finding else [],
        "level_reasons": (built.level_reasons[:1] if finding else []) + reasons,
        "regressions": entries,
    })  # fmt: skip


def test_the_files_the_prs_own_test_patch_changes() -> None:
    def files(patch: str) -> frozenset[str]:
        return report.updated_tests(task().model_copy(update={"test_patch": patch}))

    assert files(TEST_PATCH) == {"tests/test_calc.py", "tests/test_new.py"}
    assert files("") == frozenset()
    assert files("not a diff\n") == frozenset()  # unreadable: nothing is set aside for it


def test_only_a_counterexample_resting_on_updated_tests_alone_is_set_aside() -> None:
    updated = report.updated_tests(task().model_copy(update={"test_patch": TEST_PATCH}))

    both = regressed("tests/test_calc.py", "tests/test_new.py")

    def aside(found: Receipt, kind: str = "gold", gold: Receipt | None = both) -> bool:
        return report.rests_on_updated_tests(Run(line(kind), found), updated, gold)

    assert aside(regressed("tests/test_calc.py"))
    assert aside(regressed("tests/test_calc.py"), gold=None)  # gold's own run needs no gold
    assert aside(both, "partial")
    assert aside(regressed("tests/test_new.py"), "partial")  # gold shares it
    # a regression gold's first run doesn't have is the partial fix's own (NOTES #34 S4)
    assert not aside(both, "partial", regressed("tests/test_calc.py"))
    assert not aside(both, "partial", receipt("L4"))
    assert not aside(both, "partial", None)  # no gold run to compare with
    assert not aside(regressed("tests/test_other.py"))  # a test the PR left alone
    assert not aside(regressed("tests/test_calc.py", "tests/test_other.py"))
    assert not aside(regressed("tests/test_calc.py", finding=True))  # another cause too
    assert not aside(receipt("COUNTEREXAMPLE"))  # no regression at all
    assert not aside(regressed())  # no cause at all: nothing to rest on
    assert not aside(receipt("L2"))
    assert not report.rests_on_updated_tests(Run(line(outcome="timeout"), None), updated)


def test_the_summary_sets_those_runs_aside_from_gold_partial_and_separation() -> None:
    lines = [line("gold"), line("partial")]
    receipts = {(ID, "gold", 1): regressed("tests/test_calc.py", "tests/test_new.py"),
                (ID, "partial", 1): regressed("tests/test_new.py")}  # fmt: skip
    found = summary(lines, receipts, test_patch=TEST_PATCH)
    assert found["set_aside"] == {"gold": {"n": 1, "of": 1}, "partial": {"n": 1, "of": 1},
                                  "tasks": ID}  # fmt: skip
    assert found["gold"]["counterexample"] == {"n": 0, "of": 0}
    assert found["partial"]["detection"] == {"n": 0, "of": 0}
    assert found["separation"]["same"] == {"n": 0, "of": 0}
    assert found["splits"] == {"dev": 1}  # the stage sections still read the run
    # without the PR's test patch the same regressions count as they are
    plain = summary(lines, receipts)
    assert plain["set_aside"] == {"gold": {"n": 0, "of": 1}, "partial": {"n": 0, "of": 1},
                                  "tasks": None}  # fmt: skip
    assert plain["gold"]["counterexample"] == {"n": 1, "of": 1}
    assert plain["partial"]["detection"] == {"n": 1, "of": 1}
    # a partial fix's regression gold doesn't share counts, though gold's is set aside
    own = {**receipts, (ID, "gold", 1): regressed("tests/test_calc.py")}
    split = summary(lines, own, test_patch=TEST_PATCH)
    assert split["set_aside"] == {"gold": {"n": 1, "of": 1}, "partial": {"n": 0, "of": 1},
                                  "tasks": ID}  # fmt: skip
    assert split["partial"]["detection"] == {"n": 1, "of": 1}


def test_the_report_is_rebuilt_byte_for_byte_from_summary_json() -> None:
    lines = [line("gold"), line("partial", replay=replayed("fixed", "still_fails"))]
    receipts = {(ID, "gold", 1): receipt("L3"), (ID, "partial", 1): receipt("COUNTEREXAMPLE")}
    found = summary(lines, receipts, Labels(labels=(label("v0-r1", 2, "real_bug"),)))
    text = report.markdown(found, "t")
    assert report.markdown(json.loads(json.dumps(found)), "t") == text
    assert "| tracefix__synthetic-1 | v0-r1 | 1 |" in text and "| fixed | unreviewed |" in text
    assert "real_bug (developer)" in text
    assert "1/1 (100%)" in text


# --- properties ---------------------------------------------------------------------------------

LABEL = st.sampled_from([None, "real_bug", "false_alarm", "unclear"])
BY = st.sampled_from(["developer", "claude-proposed"])
RESULT = st.sampled_from(["fixed", "still_fails", "fails_differently", "cannot_run"])
TASK = st.tuples(st.sampled_from(LEVELS), st.sampled_from(LEVELS), st.lists(RESULT, max_size=2),
                 st.lists(st.tuples(LABEL, BY), min_size=5, max_size=5))  # fmt: skip


def runs_and_labels(tasks: list[Any]) -> tuple[list[Run], list[Run], list[FindingLabel]]:
    gold, partial, labels = [], [], []
    for i, (g, p, results, chosen) in enumerate(tasks, 1):
        iid = f"tracefix__synthetic-{i}"
        gold.append(gold_run(g, iid))
        partial.append(partial_run(p, *results, instance_id=iid))
        keys = [("gold-r1", 1), ("gold-r1", 2), ("v0-r1", 1), ("v0-r1", 2),
                ("gold-r1", report.RUN_ITSELF)]  # fmt: skip
        for (run, n), (value, by) in zip(keys, chosen, strict=True):
            if value is not None:
                labels.append(label(run, n, value, by, iid))
    return gold, partial, labels


def rates(value: object) -> list[dict[str, int]]:
    if isinstance(value, dict) and set(value) == {"n", "of"}:
        return [value]
    if isinstance(value, dict):
        return [r for v in value.values() for r in rates(v)]
    return []


@given(st.lists(TASK, max_size=6))
def test_every_rate_is_a_count_within_its_total(tasks: list[Any]) -> None:
    gold, partial, labels = runs_and_labels(tasks)
    keyed = by_key(*labels)
    for section in (report.gold(gold, keyed), report.partial(partial, keyed),
                    report.separation(gold, partial)):  # fmt: skip
        for r in rates(section):
            assert 0 <= r["n"] <= r["of"]


@given(st.lists(TASK, max_size=6))
def test_unlabelled_findings_are_never_false_alarms_or_finds(tasks: list[Any]) -> None:
    gold, partial, labels = runs_and_labels(tasks)
    # a label counts only on a finding the receipt has (a COUNTEREXAMPLE receipt has 1 and 2)
    has = {r.line.instance_id: {f.number for f in r.receipt.findings} for r in gold if r.receipt}
    flagged = {
        lb.instance_id
        for lb in labels
        if lb.by == "developer"
        and lb.label == "false_alarm"
        and lb.run == "gold-r1"
        and lb.finding in has[lb.instance_id]
    }
    found = report.gold(gold, by_key(*labels))
    assert found["false_alarm"]["n"] == sum(r.line.instance_id in flagged for r in gold)
    assert report.gold(gold, {})["false_alarm"]["n"] == 0
    assert report.partial(partial, {})["real_bug_by_label"]["n"] == 0
    # a find on a partial fix is only ever our own replay's `fixed`
    assert report.partial(partial, {})["leftover_found"]["n"] == sum(
        any(f.result.value == "fixed" for f in r.line.replay.findings) for r in partial
        if r.line.replay is not None
    )  # fmt: skip


# --- the commands on disk -----------------------------------------------------------------------


def test_label_then_report_from_the_files_on_disk(tmp_path: Path) -> None:
    data.write_cases(tmp_path / "cases" / "slice1.jsonl", [case(ID, 0)])
    prepared = tmp_path / "prepared" / "slice1"
    prepared.mkdir(parents=True)
    (prepared / f"{ID}.json").write_text(ready(ID).model_dump_json(), encoding="utf-8")
    results = Results(tmp_path / "results" / "slice1")
    for kind, level in (("gold", "COUNTEREXAMPLE"), ("partial", "L2")):
        found = line(kind, receipt=f"{ID}/{'gold' if kind == 'gold' else 'v0'}-r1")
        folder = results.folder / str(found.receipt)
        folder.mkdir(parents=True)
        (folder / "receipt.json").write_text(receipt(level).model_dump_json(), encoding="utf-8")
        results.append(found)
    assert benchmark.add_labels(tmp_path, "slice1") == {"labels": 2, "added": 2, "unlabelled": 2,
                                                        "count_nowhere": []}  # fmt: skip
    assert benchmark.add_labels(tmp_path, "slice1")["added"] == 0
    assert benchmark.write_report(tmp_path, "slice1") == {"runs": 2, "findings": 2}
    written = json.loads((results.folder / "summary.json").read_text(encoding="ascii"))
    assert written["gold"]["unreviewed"] == {"n": 1, "of": 1}
    text = (results.folder / "report.md").read_text(encoding="utf-8")
    assert text == report.markdown(written, "Tracefix benchmark: slice1")
    for name in ("summary.json", "report.md"):  # the same bytes on every OS
        assert b"\r\n" not in (results.folder / name).read_bytes()


def test_a_result_set_has_its_own_labels_and_report(tmp_path: Path) -> None:
    """M11 S0: `--results m11-a` reads the slice's cases and prepare records, and its own
    runs and labels; the slice's own folders are never touched."""
    data.write_cases(tmp_path / "cases" / "slice1.jsonl", [case(ID, 0)])
    prepared = tmp_path / "prepared" / "slice1"
    prepared.mkdir(parents=True)
    (prepared / f"{ID}.json").write_text(ready(ID).model_dump_json(), encoding="utf-8")
    results = Results(tmp_path / "results" / "slice1-m11-a")
    found = line("gold", receipt=f"{ID}/gold-r1", issue="title")
    (results.folder / ID / "gold-r1").mkdir(parents=True)
    (results.folder / ID / "gold-r1" / "receipt.json").write_text(
        receipt("COUNTEREXAMPLE").model_dump_json(), encoding="utf-8"
    )
    results.append(found)
    assert benchmark.add_labels(tmp_path, "slice1", "m11-a")["added"] == 2
    assert (tmp_path / "labels" / "slice1-m11-a.json").is_file()
    assert benchmark.write_report(tmp_path, "slice1", "m11-a")["runs"] == 1
    text = (results.folder / "report.md").read_text(encoding="utf-8")
    assert text.startswith("# Tracefix benchmark: slice1-m11-a\n")
    assert not (tmp_path / "results" / "slice1").exists()
    assert not (tmp_path / "labels" / "slice1.json").exists()


def test_a_run_whose_receipt_no_longer_parses_stops_the_report(tmp_path: Path) -> None:
    data.write_cases(tmp_path / "cases" / "slice1.jsonl", [case(ID, 0)])
    results = Results(tmp_path / "results" / "slice1")
    folder = results.folder / ID / "gold-r1"
    folder.mkdir(parents=True)
    (folder / "receipt.json").write_text(receipt("L2").model_dump_json(), encoding="utf-8")
    results.append(line("gold", receipt=f"{ID}/gold-r1"))
    results.append(line("partial", outcome="timeout", exit_code=None))  # no receipt: fine
    assert benchmark.write_report(tmp_path, "slice1")["runs"] == 2
    (folder / "receipt.json").write_text('{"schema_version": 1}', encoding="utf-8")
    for command in (benchmark.write_report, benchmark.add_labels):
        with pytest.raises(data.DataError, match=f"{ID} gold-r1"):
            command(tmp_path, "slice1")


def test_stats_give_a_nearest_rank_90th_percentile() -> None:
    times = [float(n) for n in range(1, 11)]  # 1..10: the 9th value of 10
    assert report._stats(times) == {"n": 10, "mean": 5.5, "median": 5.5, "p90": 9.0, "max": 10.0}
    assert report._stats([3.0])["p90"] == 3.0
    assert report._stats([]) == {"n": 0}
    assert "p90 9.0" in report.show(report._stats(times))


# --- NOTES #34 leftovers ------------------------------------------------------------------------


def test_a_false_alarm_needs_a_counterexample() -> None:
    """A finding on a gold run that stayed below COUNTEREXAMPLE raised no alarm (N8)."""
    found = receipt("L2").model_copy(update={"findings": receipt("COUNTEREXAMPLE").findings})
    labels = by_key(label("gold-r1", 1, "false_alarm"), label("gold-r1", 2, "false_alarm",
                                                              "claude-proposed"))  # fmt: skip
    quiet = report.gold([Run(line("gold"), found)], labels)
    assert quiet["false_alarm"] == {"n": 0, "of": 1}
    assert quiet["false_alarm_proposed"] == {"n": 0, "of": 1}
    loud = report.gold([gold_run("COUNTEREXAMPLE")], labels)
    assert loud["false_alarm"] == {"n": 1, "of": 1} == loud["false_alarm_proposed"]


def test_a_stale_entry_never_labelled_says_so() -> None:
    again = receipt("COUNTEREXAMPLE").model_copy(update={"created_at": "2026-01-02T00:00:00+00:00"})
    empty = FindingLabel(instance_id=ID, run="gold-r1", finding=1, receipt_created_at=CREATED_AT)
    [fresh, _] = report.with_missing(Labels(labels=(empty,)), [Run(line("gold"), again)]).labels
    assert fresh.note == f"earlier attempt ({CREATED_AT}): not labelled."


def test_entries_that_count_nowhere_are_listed() -> None:
    again = receipt("COUNTEREXAMPLE").model_copy(update={"created_at": "2026-01-02T00:00:00+00:00"})
    labels = Labels(labels=(
        label("gold-r1", 1, "false_alarm"),  # its receipt: counts
        label("gold-r1", 7, "false_alarm"),  # the receipt has no finding 7
        label("v0-r1", 2, "real_bug"),  # the partial run was tried again: a stale entry
        label("gold-r2", 1, "unclear"),  # no such run any more
    ))  # fmt: skip
    runs = [gold_run("COUNTEREXAMPLE"), Run(line("partial", replay=replayed("fixed", "fixed")),
                                            again)]  # fmt: skip
    assert report.orphaned(labels, runs) == [f"{ID} gold-r1 #7", f"{ID} v0-r1 #2",
                                             f"{ID} gold-r2 #1"]  # fmt: skip


def test_the_report_refuses_runs_of_a_variant_prepare_no_longer_keeps(tmp_path: Path) -> None:
    data.write_cases(tmp_path / "cases" / "slice1.jsonl", [case(ID, 0)])
    prepared = tmp_path / "prepared" / "slice1"
    prepared.mkdir(parents=True)
    (prepared / f"{ID}.json").write_text(ready(ID).model_dump_json(), encoding="utf-8")
    results = Results(tmp_path / "results" / "slice1")
    results.append(line("partial", variant="v1", outcome="timeout"))
    with pytest.raises(data.DataError, match=f"{ID} v1-r1"):
        benchmark.write_report(tmp_path, "slice1")
    results.append(line("partial", outcome="timeout"))  # run again on the kept variant
    assert benchmark.write_report(tmp_path, "slice1")["runs"] == 1


SLICE1 = Path(__file__).parents[1] / "benchmarks"


def _copy_committed(tmp_path: Path, slice_name: str, *sets: str) -> None:
    """The committed cases and prepare records of a slice, and each named result set's runs,
    receipts and labels, copied to `tmp_path` as a benchmarks folder."""
    parts = [f"cases/{slice_name}.jsonl", f"prepared/{slice_name}"]
    parts += [part for name in sets for part in (f"results/{name}", f"labels/{name}.json")]
    for part in parts:
        source, copy = SLICE1 / part, tmp_path / part
        copy.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, copy)
        else:
            shutil.copyfile(source, copy)


def _same_as_committed(tmp_path: Path, folder: str, names: tuple[str, ...]) -> None:
    for name in names:
        built = (tmp_path / "results" / folder / name).read_bytes()
        committed = SLICE1 / "results" / folder / name
        assert built == committed.read_bytes().replace(b"\r\n", b"\n"), name


@pytest.mark.parametrize(
    ("slice_name", "results_name"), [("slice1", None), ("slice2", None), ("slice2", "m11")]
)
def test_committed_report_is_rebuilt_byte_for_byte(
    tmp_path: Path, slice_name: str, results_name: str | None
) -> None:
    """From the committed cases, prepare records, runs, receipts and labels: today's rules give
    the committed summary.json and report.md exactly. M11's arm B (`slice2-m11`) too."""
    folder = benchmark.named(slice_name, results_name)
    _copy_committed(tmp_path, slice_name, folder)
    benchmark.write_report(tmp_path, slice_name, results_name)
    _same_as_committed(tmp_path, folder, ("summary.json", "report.md"))


def test_committed_comparison_is_rebuilt_byte_for_byte(tmp_path: Path) -> None:
    """M11's arm B against arm A, which docs/BENCHMARK.md quotes: from the committed files of
    both result sets, today's rules give the committed compare-slice2.json and .md exactly."""
    _copy_committed(tmp_path, "slice2", "slice2", "slice2-m11")
    benchmark.write_compare(tmp_path, "slice2", None, "m11")
    _same_as_committed(tmp_path, "slice2-m11", ("compare-slice2.json", "compare-slice2.md"))


# --- slice 2: agents' patches (M10 part 2 plan C5) ----------------------------------------------

SECOND = "tracefix__synthetic-2"


def agent_line(kind: str, instance_id: str = ID, **changes: Any) -> RunLine:
    return line(kind, instance_id, variant=kind, **changes)


def test_a_correct_agents_findings_all_need_labels_a_wrong_agents_fixed_ones_do_not() -> None:
    both = {"replay": replayed("fixed", "still_fails")}
    ok = Run(agent_line("agent_ok", **both), receipt("COUNTEREXAMPLE"))
    wrong = Run(agent_line("agent_wrong", **both), receipt("COUNTEREXAMPLE"))
    assert report.needs_label(ok) == [1, 2]  # finding 1 differs from gold: still judged
    assert report.needs_label(wrong) == [2]
    alone = receipt("COUNTEREXAMPLE").model_copy(update={"findings": []})
    assert report.needs_label(Run(agent_line("agent_ok"), alone)) == [report.RUN_ITSELF]


def agent_summary(lines: list[RunLine], receipts: dict[tuple[str, str, int], Receipt | None],
                  labels: Labels) -> dict[str, Any]:  # fmt: skip
    """Two slice 2 tasks: ID on Python 3.9 with both agents run, SECOND on 3.11 whose
    agent_wrong patch our runs disagreed on (not run)."""
    cases = [bench_fakes.agent_case(ID, 0), bench_fakes.agent_case(SECOND, 1)]
    both = (tried("agent_wrong"), tried("agent_ok"))
    one = (tried("agent_wrong", kept=False), tried("agent_ok"))
    prepared = {
        ID: ready(ID, agents=both).model_copy(update={"python": "3.9.18"}),
        SECOND: ready(SECOND, agents=one).model_copy(update={"python": "3.11.9"}),
    }
    return report.summarise(cases, prepared, lines, receipts, labels, reserve=3.0)


def test_slice2_reads_agents_with_correct_fixes_together_and_by_python() -> None:
    fixed = {"replay": replayed("fixed", "still_fails")}
    lines = [
        line("gold", ID),
        agent_line("agent_wrong", ID, **fixed),
        agent_line("agent_ok", ID, **fixed),
        line("gold", SECOND),
        agent_line("agent_ok", SECOND),
    ]
    receipts: dict[tuple[str, str, int], Receipt | None] = {
        (ID, "gold", 1): receipt("L4"),
        (ID, "agent_wrong", 1): receipt("COUNTEREXAMPLE"),
        (ID, "agent_ok", 1): receipt("COUNTEREXAMPLE"),
        (SECOND, "gold", 1): receipt("COUNTEREXAMPLE"),
        (SECOND, "agent_ok", 1): receipt("L4"),
    }
    labels = Labels(labels=(label("agent_ok-r1", 2, "false_alarm"),
                            label("gold-r1", 1, "real_bug", instance_id=SECOND)))  # fmt: skip
    found = agent_summary(lines, receipts, labels)
    assert found["funnel"]["agents"] == {"agent_ok: hidden_tests_pass": 2,
                                         "agent_wrong: partial": 1,
                                         "agent_wrong: partial (not run)": 1}  # fmt: skip
    assert set(found["funnel"]["runs"]) == {"gold", "partial", "agent_wrong", "agent_ok"}
    wrong, ok, correct = found["agent_wrong"], found["agent_ok"], found["correct_fixes"]
    assert (wrong["detection"], wrong["leftover_found"]) == (report.rate(1, 1), report.rate(1, 1))
    assert ok["false_alarm"] == report.rate(1, 2)
    assert ok[report.DIFFERS] == report.rate(1, 2)
    assert (correct["counterexample"], correct["false_alarm"]) == (report.rate(2, 4),
                                                                   report.rate(1, 4))  # fmt: skip
    assert found["separation_agent_wrong"]["gold_above"] == report.rate(1, 1)
    old, new = found["by_python"]["3.9/3.10"], found["by_python"]["3.11+"]
    assert (old["correct_false_alarm"], old["agent_wrong_caught"]) == (
        report.rate(1, 2),
        report.rate(1, 1),
    )
    assert (new["correct_false_alarm"], new["agent_wrong_caught"]) == (
        report.rate(0, 2),
        report.rate(0, 0),
    )
    assert found["by_split"]["held_out"]["correct_false_alarm"] == report.rate(0, 0)
    assert found["by_split"]["dev"]["agent_ok_false_alarm"] == report.rate(1, 2)
    assert old["agent_ok_false_alarm"] == report.rate(1, 1)
    assert set(found["guard"]) == {"gold", "partial", "agent_wrong", "agent_ok"}
    on_gold = {(f["run"], f["finding"]): f["replay_on_gold"] for f in found["findings"]
               if f["instance_id"] == ID}  # fmt: skip
    assert on_gold[("agent_ok-r1", 1)] == report.DIFFERS
    assert on_gold[("agent_wrong-r1", 1)] == "fixed"
    text = report.markdown(found, "slice2")
    for shown in ("## Agent wrong", "## Correct fixes", "## By python", "### 3.9/3.10",
                  "### agent_ok", f"{report.DIFFERS}: an agent_ok finding"):  # fmt: skip
        assert shown in text


def test_a_slice_without_agents_has_none_of_their_sections() -> None:
    found = summary([line("gold")], {(ID, "gold", 1): receipt("L4")})
    assert not {"agent_wrong", "agent_ok", "correct_fixes", "by_python"} & set(found)
    assert "agents" not in found["funnel"] and set(found["guard"]) == {"gold", "partial"}


@pytest.mark.parametrize(("version", "group"), [
    ("3.9.18", "3.9/3.10"), ("3.10.0", "3.9/3.10"), ("3.11.9", "3.11+"), ("3.13.1", "3.11+"),
    ("", None), ("x.y", None),
])  # fmt: skip
def test_the_projects_python_groups(version: str, group: str | None) -> None:
    assert report.python_group(version) == group


# --- M11 S2: miss causes, paired A/B, the sign test --------------------------------------------


@pytest.mark.parametrize(
    ("wins", "losses", "p"),
    [(5, 0, Fraction(1, 32)), (7, 1, Fraction(9, 256)), (0, 0, Fraction(1)), (0, 5, Fraction(1)),
     (1, 1, Fraction(3, 4)), (4, 0, Fraction(1, 16)), (6, 2, Fraction(37, 256))],
)  # fmt: skip
def test_the_sign_test_is_the_exact_one_sided_binomial_tail(
    wins: int, losses: int, p: Fraction
) -> None:
    assert report.sign_test(wins, losses) == p


@given(st.integers(0, 40), st.integers(0, 40))
def test_the_sign_test_is_a_probability_that_falls_as_wins_grow(wins: int, losses: int) -> None:
    p = report.sign_test(wins, losses)
    assert 0 < p <= 1
    assert report.sign_test(wins + 1, losses) < p  # one more win, one more pair: rarer
    assert report.sign_test(0, losses) == 1


def test_the_sign_test_takes_counts_only() -> None:
    with pytest.raises(ValueError, match="counts"):
        report.sign_test(-1, 2)


def touched(function: str | None, path: str = "pkg/calc.py") -> Touched:
    return Touched(path=path, function=function)


def prepared_with(functions: tuple[Touched, ...] | None, label: str = "partial",
                  agents: tuple[TriedAgent, ...] = ()) -> Prepared:  # fmt: skip
    variant = TriedVariant(index=0, path="pkg/calc.py", old_start=1, old_len=2,
                           label=Label(label), failing=1, functions=functions)  # fmt: skip
    return ready(ID).model_copy(update={"variants": (variant,), "agents": agents})


def with_targets(level: str, *targets: AttackTargetEntry | None) -> Receipt:
    built = receipt(level)
    shown = None if targets == (None,) else [t for t in targets if t is not None]
    return built.model_copy(update={"attack_targets": shown})


def entry(function: str = "pkg.calc.f_t1", inputs: int = 150, via: str = "",
          attacked: bool = True) -> AttackTargetEntry:  # fmt: skip
    return AttackTargetEntry(function=function, path="pkg/calc.py", via=via, attacked=attacked,
                             inputs_tried=inputs, finished=True, reason="")  # fmt: skip


def missed(built: Receipt, prepared: Prepared | None, kind: str = "partial", **line_changes: Any
           ) -> str | None:  # fmt: skip
    variant = "v0" if kind == "partial" else kind
    return report.miss_cause(Run(line(kind, variant=variant, **line_changes), built), prepared)


def test_a_miss_cause_is_given_only_for_a_wrong_fix_whose_leftover_was_not_found() -> None:
    p = prepared_with((touched("f_t1"),))
    assert missed(receipt("L4"), p, "gold") is None
    assert missed(receipt("COUNTEREXAMPLE"), p, replay=replayed("fixed", "still_fails")) is None
    assert report.miss_cause(Run(line("partial", outcome="timeout"), None), p) is None
    assert missed(receipt("L4"), p) == report.NO_COUNTEREXAMPLE


def test_each_miss_cause_comes_from_the_receipt_and_the_prepare_record() -> None:
    p = prepared_with((touched("f_t1"),))
    assert missed(receipt("L4"), prepared_with((touched("f_t1"),), "no_effect")) == \
        report.NO_EFFECT  # fmt: skip
    no_stage = receipt("L4").model_copy(update={"stages": [
        s for s in receipt("L4").stages if s.name != "break_my_fix"]})  # fmt: skip
    assert missed(no_stage, p) == report.NOT_RUN
    assert missed(with_targets("L4", None), p) == report.TARGETS_UNKNOWN  # an older receipt
    assert missed(receipt("L4"), prepared_with(None)) == report.LEFTOVER_UNKNOWN
    assert missed(receipt("L4"), None) == report.LEFTOVER_UNKNOWN
    assert missed(receipt("L4"), prepared_with(())) == report.NO_SOURCE
    assert missed(receipt("L4"), prepared_with((touched(None),))) == report.OUTSIDE
    assert missed(receipt("L4"), prepared_with((touched("other"),))) == report.NOT_TARGET
    elsewhere = prepared_with((touched("f_t1", "pkg/other.py"),))
    assert missed(receipt("L4"), elsewhere) == report.NOT_TARGET  # same name, other file
    assert missed(with_targets("L4", entry(inputs=0)), p) == report.NO_INPUT
    other_ran = with_targets("L4", entry(inputs=0, attacked=False), entry("pkg.calc.g"))
    assert missed(other_ran, p) == report.NOT_ATTACKED
    assert missed(receipt("COUNTEREXAMPLE"), p,
                  replay=replayed("still_fails", "still_fails")) == report.NOT_LEFTOVER  # fmt: skip
    assert missed(receipt("L4"), prepared_with((touched(None), touched("f_t1")))) == \
        report.NO_COUNTEREXAMPLE  # fmt: skip


def test_a_public_caller_attacked_on_behalf_of_the_leftovers_function_counts() -> None:
    caller = with_targets("L4", entry("pkg.api.load", via="a public caller of the changed _parse"))
    assert missed(caller, prepared_with((touched("_parse"),))) == report.NO_COUNTEREXAMPLE
    assert missed(caller, prepared_with((touched("parse"),))) == report.NOT_TARGET


def test_a_wrong_agents_leftover_is_where_it_differs_from_gold() -> None:
    agent = tried("agent_wrong").model_copy(update={"functions": (touched("f_t1"),),
                                                   "differs": (touched("half"),)})  # fmt: skip
    p = prepared_with(None, agents=(agent,))
    assert missed(receipt("L4"), p, "agent_wrong") == report.NOT_TARGET
    on_target = agent.model_copy(update={"differs": (touched("f_t1"),)})
    assert missed(receipt("L4"), prepared_with(None, agents=(on_target,)), "agent_wrong") == (
        report.NO_COUNTEREXAMPLE
    )


def test_paired_units_match_task_kind_variant_and_repeat_with_receipts_on_both_sides() -> None:
    a = [gold_run("L4"), partial_run("L2"), Run(line("gold", repeat=2), receipt("L4")),
         Run(line("partial", repeat=2), None)]  # fmt: skip
    b = [Run(line("partial", repeat=2), receipt("L1")), partial_run("L1"), gold_run("L3"),
         Run(line("partial", variant="v1", repeat=3), receipt("L1"))]  # fmt: skip
    pairs = report.paired(a, b)
    assert [(x.line.tag, y.line.tag) for x, y in pairs] == [("gold-r1", "gold-r1"),
                                                            ("v0-r1", "v0-r1")]  # fmt: skip
    assert pairs[0][0] is a[0] and pairs[0][1] is b[2]
    other_variant = [Run(line("partial", variant="v1"), receipt("L1"))]
    assert report.paired(a, other_variant) == []


def test_compare_counts_wins_losses_false_alarms_and_misses() -> None:
    p = {ID: prepared_with((touched("f_t1"),)), SECOND: prepared_with((touched("other"),))}
    found = replayed("fixed", "still_fails")

    def wrong(arm_found: bool, instance_id: str, repeat: int) -> Run:
        changes = {"replay": found} if arm_found else {}
        level = "COUNTEREXAMPLE" if arm_found else "L4"
        return Run(line("partial", instance_id, repeat, **changes), receipt(level))

    a = [wrong(False, ID, 1), wrong(False, ID, 2), wrong(True, SECOND, 1), wrong(False, SECOND, 2),
         gold_run("COUNTEREXAMPLE"), gold_run("L4", SECOND)]  # fmt: skip
    b = [wrong(True, ID, 1), wrong(True, ID, 2), wrong(False, SECOND, 1), wrong(False, SECOND, 2),
         gold_run("L4"), gold_run("L4", SECOND)]  # fmt: skip
    a_labels = by_key(label("gold-r1", 1, "false_alarm"), label("gold-r1", 2, "false_alarm"))
    result = report.compare(a, b, p, a_labels, {})
    assert result["pairs"] == {"wrong_fixes": 4, "correct_fixes": 2}
    assert result["wrong_fixes"] == {"b_only": 2, "a_only": 1, "sign_test_p": "1/2 (0.5000)"}
    assert result["a"]["leftover_found"] == report.rate(1, 4)
    assert result["b"]["leftover_found"] == report.rate(2, 4)
    assert result["a"]["false_alarm"] == report.rate(1, 2)
    assert result["b"]["false_alarm"] == report.rate(0, 2)
    assert result["a"]["misses"] == {report.NOT_TARGET: 1, report.NO_COUNTEREXAMPLE: 2}
    assert result["a"]["reachable_misses"] == 2
    assert result["b"]["misses"] == {report.NOT_TARGET: 2}
    assert result["b"]["reachable_misses"] == 0
    assert result["a"]["unpaired"] == result["b"]["unpaired"] == 0


def with_stage(built: Receipt, name: str, status: str, **evidence: object) -> Receipt:
    """`built` with one more stage, or that stage replaced."""
    entry = built.stages[0].model_copy(update={"name": name, "status": status,
                                               "evidence": evidence, "reason": ""})  # fmt: skip
    kept = [s for s in built.stages if s.name != name]
    return built.model_copy(update={"stages": [*kept, entry]})


@pytest.mark.parametrize(
    ("killed", "valid", "not_run", "flips"),
    [(4, 5, 0, True),  # 80%: one survivor more is 60%
     (5, 5, 0, False),  # 100%: one survivor more is still 80%
     (3, 3, 0, True), (8, 10, 0, True), (9, 10, 0, False),
     (3, 5, 0, True),  # 60%: one kill more is 80%
     (2, 5, 0, False),  # 40%: one kill more is 60%
     (0, 3, 0, False), (7, 10, 0, True),
     (1, 3, 2, True),  # stopped early: 3 of 5 at best, one kill more is 80%
     (0, 4, 2, False)],  # 2 of 6 at best, one kill more is 50%
)  # fmt: skip
def test_one_mutant_from_flipping(killed: int, valid: int, not_run: int, flips: bool) -> None:
    assert report.one_mutant_from_flipping(killed, valid, not_run) is flips


def test_compare_moves_levels_per_kind_and_tests_not_green_lit_in_pairs() -> None:
    def run(kind: str, instance_id: str, level: str) -> Run:
        return Run(line(kind, instance_id), receipt(level))

    a = [run("partial", ID, "L2"), run("partial", SECOND, "L1"), run("gold", ID, "L3")]
    b = [run("partial", ID, "L1"), run("partial", SECOND, "L2"), run("gold", ID, "L4")]
    found = report.compare(a, b, {}, {}, {})
    assert found["levels"] == {"gold": {"up": 1, "down": 0, "same": 0},
                               "partial": {"up": 1, "down": 1, "same": 0}}  # fmt: skip
    assert found["not_green_lit"]["partial"] == {"b_only": 1, "a_only": 1,
                                                 "sign_test_p": "3/4 (0.7500)"}  # fmt: skip
    assert found["not_green_lit"]["agent_wrong"]["b_only"] == 0
    assert found["a"]["gold_at_least_l2"] == report.rate(1, 1)
    assert found["a"]["headline"]["partial_not_green_lit"] == report.rate(1, 2)
    assert found["b"]["headline"]["partial_not_green_lit"] == report.rate(1, 2)


def test_compare_reads_mutants_no_input_and_seconds_on_each_arm() -> None:
    judged = with_stage(receipt("L2"), "guard", "guarded", mutants=5, killed=4, not_run=0)
    firm = with_stage(receipt("L2"), "guard", "guarded", mutants=10, killed=10, not_run=0)
    unjudged = with_stage(receipt("L2"), "guard", "skipped", mutants=9, killed=9)
    stopped = with_stage(receipt("L2"), "break_my_fix", "inconclusive", inputs_tried=0)
    entry = next(s for s in stopped.stages if s.name == "break_my_fix")
    no_input = entry.model_copy(update={"reason": "the attack ran no input"})
    stopped = stopped.model_copy(update={"stages": [*stopped.stages[:-1], no_input]})
    a = [Run(line("gold", ID, seconds=10.0), judged),
         Run(line("partial", ID, seconds=20.0), firm),
         Run(line("gold", SECOND, seconds=30.0), unjudged),
         Run(line("partial", SECOND, seconds=40.0), stopped)]  # fmt: skip
    arm = report.compare(a, a, {}, {}, {})["a"]
    mutants = arm["guard_mutants"]
    assert mutants["valid_mutants"]["n"] == 2 and mutants["valid_mutants"]["median"] == 7.5
    assert mutants["gold_valid_mutants"]["median"] == 5
    assert mutants["one_mutant_from_flipping"] == report.rate(1, 2)
    assert mutants["gold_one_mutant_from_flipping"] == report.rate(1, 1)
    assert arm["no_input"] == report.rate(1, 4)
    assert arm["seconds"]["median"] == 25 and arm["seconds"]["p90"] == 40


def test_compare_counts_an_arms_timeouts_at_the_seconds_they_ran() -> None:
    """A run that hit the time limit has no receipt, so no pair, and `seconds` never sees it.
    The time target must (developer, 13 Nov 2026): it is counted beside, at the limit it hit."""
    a = [Run(line("gold", ID, seconds=10.0), receipt("L2")),
         Run(line("partial", ID, seconds=20.0), receipt("L1")),
         Run(line("gold", SECOND, seconds=30.0), receipt("L2"))]  # fmt: skip
    b = [*a[:2], Run(line("gold", SECOND, outcome="timeout", seconds=7200.0), None)]
    found = report.compare(a, b, {}, {}, {})
    assert found["a"]["timeouts"] == 0 and found["a"]["unpaired"] == 1
    assert found["a"]["seconds_with_timeouts"] == found["a"]["seconds"]
    assert found["b"]["timeouts"] == 1
    assert found["b"]["seconds"] == {"n": 2, "mean": 15.0, "median": 15.0, "p90": 20.0, "max": 20.0}
    assert found["b"]["seconds_with_timeouts"] == {
        "n": 3, "mean": 2410.0, "median": 20.0, "p90": 7200.0, "max": 7200.0,
    }  # fmt: skip


def test_the_mutant_target_reads_only_runs_guard_did_not_stop() -> None:
    whole = with_stage(receipt("L2"), "guard", "guarded", mutants=9, killed=8, not_run=0)
    older = with_stage(receipt("L2"), "guard", "guarded", mutants=7, killed=6)  # no `not_run`: M10
    cut = with_stage(receipt("L1"), "guard", "not_guarded", mutants=3, killed=0, not_run=6)
    runs = [Run(line("gold", ID), whole), Run(line("partial", ID), older),
            Run(line("gold", SECOND), cut)]  # fmt: skip
    mutants = report.guard_mutants(runs)
    # The current rows keep every judged run, the stopped one's low count too.
    assert (mutants["valid_mutants"]["n"], mutants["valid_mutants"]["median"]) == (3, 7)
    assert (mutants["gold_valid_mutants"]["n"], mutants["gold_valid_mutants"]["median"]) == (2, 6)
    # The target's rows don't, and a run from before the early stop counts as not stopped.
    found = mutants["valid_mutants_not_stopped"]
    assert (found["n"], found["median"]) == (2, 8)
    gold = mutants["gold_valid_mutants_not_stopped"]
    assert (gold["n"], gold["median"]) == (1, 9)
    only_stopped = report.guard_mutants([Run(line("gold", ID), cut)])
    assert only_stopped["valid_mutants_not_stopped"] == {"n": 0}
    assert only_stopped["valid_mutants"]["n"] == 1
    # The other rows still read the stopped run.
    assert mutants["one_mutant_from_flipping"]["of"] == 3


def test_the_blind_rows_say_what_a_rule_would_do_and_stay_out_of_every_other_row() -> None:
    def blind(level: str, status: str) -> Receipt:
        return with_stage(receipt(level), "blind", status)

    a = [Run(line("agent_wrong", ID), receipt("L2")),
         Run(line("agent_wrong", SECOND), receipt("L1")),
         Run(line("gold", ID), receipt("L3")),
         Run(line("gold", SECOND), receipt("L2"))]  # fmt: skip
    b = [Run(line("agent_wrong", ID), blind("L2", "fails_on_head")),
         Run(line("agent_wrong", SECOND), blind("L1", "fails_on_head")),  # L1 already: no change
         Run(line("gold", ID), blind("L3", "reproduced")),
         Run(line("gold", SECOND), blind("L2", "fails_differently"))]  # fmt: skip
    found = report.compare(a, b, {}, {}, {})
    assert found["a"]["blind"] == {"statuses": {}, "rule_would_cap_at_l1": {}}
    shown = found["b"]["blind"]
    assert shown["statuses"] == {"agent_wrong": {"fails_on_head": 2},
                                 "gold": {"fails_differently": 1, "reproduced": 1}}  # fmt: skip
    assert shown["rule_would_cap_at_l1"] == {"agent_wrong": report.rate(1, 1),
                                             "gold": report.rate(1, 2)}  # fmt: skip
    assert found["levels"]["agent_wrong"]["same"] == 2  # the rule is only worked out, not applied
    assert found["not_green_lit"]["agent_wrong"]["b_only"] == 0


def flagged(*doubts: str | None, level: str = "COUNTEREXAMPLE", **changes: Any) -> Receipt:
    """A receipt whose findings carry these doubt flags, in order."""
    built = receipt(level)
    found = [f.model_copy(update={"doubt": d})
             for f, d in zip(built.findings, doubts, strict=True)]  # fmt: skip
    return built.model_copy(update={"findings": found, **changes})


def doubt_rows(runs: list[Run], labels: dict[Any, FindingLabel] | None = None) -> dict[str, Any]:
    plain = [Run(r.line, receipt("L2")) for r in runs]
    return report.compare(plain, runs, {}, {}, labels or {})["b"]["doubt"]


def test_the_doubt_rows_count_each_flag_on_findings_and_on_pre_existing_ones() -> None:
    both = flagged("refused", "os_limit")
    older = both.model_copy(update={"pre_existing": [both.findings[0]]})
    rows = doubt_rows([Run(line("gold", ID), older),
                       Run(line("gold", SECOND), flagged(None, "refused")),
                       Run(line("partial", ID), flagged(None, None))])  # fmt: skip
    assert rows["findings"] == {"gold": {"os_limit": 1, "refused": 2}, "partial": {}}
    assert rows["pre_existing"] == {"gold": {"refused": 1}, "partial": {}}


def test_a_doubt_rule_moves_a_counterexample_only_if_flagged_findings_are_its_every_cause() -> None:
    reasons = flagged(None, None).level_reasons
    other = [*reasons, "regression: tests/test_a.py::test_b passed before the fix"]
    rows = doubt_rows([
        Run(line("gold", "t/1"), flagged("refused", "refused")),
        Run(line("gold", "t/2"), flagged("refused", "os_limit")),  # only all three rules together
        Run(line("gold", "t/3"), flagged("refused", None)),  # another finding still stands
        Run(line("gold", "t/4"), flagged("refused", "refused", level_reasons=other)),  # regression
        Run(line("gold", "t/5"), receipt("L2")),  # no counterexample to move
        Run(line("partial", "t/1"), flagged("finished_object", "finished_object")),
    ])  # fmt: skip
    moved = {rule: found["would_leave_counterexample"] for rule, found in rows["rules"].items()}
    assert moved == {
        "any": {"gold": report.rate(2, 4), "partial": report.rate(1, 1)},
        "os_limit": {"gold": report.rate(0, 4), "partial": report.rate(0, 1)},
        "finished_object": {"gold": report.rate(0, 4), "partial": report.rate(1, 1)},
        "refused": {"gold": report.rate(1, 4), "partial": report.rate(0, 1)},
    }


def test_a_doubt_rule_says_which_false_alarms_go_and_which_real_bugs_and_leftovers_it_costs() -> (
    None
):
    def replays(*results: str) -> dict[str, Any]:
        return {"replay": replayed(*results)}

    runs = [
        Run(line("gold", "t/1"), flagged("refused", "refused")),  # false alarm + real bug, both go
        Run(line("gold", "t/2"), flagged("refused", None)),  # false alarm stays: finding 2 stands
        # A real bug under another flag:
        Run(
            line("agent_ok", "t/3", variant="agent_ok", **replays("fixed", "still_fails")),
            flagged(None, "os_limit"),
        ),
        # Leftover found only through a flagged finding: lost, though finding 2 keeps the catch.
        Run(line("partial", "t/4", **replays("fixed", "still_fails")), flagged("refused", None)),
        # Found through the plain finding as well: a rule leaves it found.
        Run(line("partial", "t/5", **replays("fixed", "fixed")), flagged("refused", None)),
        Run(line("partial", "t/6"), flagged("refused", "refused")),  # no leftover found to lose
    ]
    labels = by_key(
        label("gold-r1", 1, "false_alarm", instance_id="t/1"),
        label("gold-r1", 2, "real_bug", instance_id="t/1"),
        label("gold-r1", 1, "false_alarm", instance_id="t/2"),
        label("agent_ok-r1", 2, "real_bug", instance_id="t/3"),
        label(
            "v0-r1", 1, "false_alarm", instance_id="t/6"
        ),  # a wrong fix's: no false alarm counted
    )
    tag = {r.line.instance_id: r.line.tag for r in runs}
    assert tag["t/1"] == "gold-r1" and tag["t/3"] == "agent_ok-r1"  # the labels above reach them
    rules = doubt_rows(runs, labels)["rules"]
    assert rules["refused"]["false_alarms_gone"] == report.rate(1, 2)
    assert rules["refused"]["real_bug_findings_dropped"] == report.rate(1, 2)
    assert rules["refused"]["leftovers_lost"] == report.rate(1, 2)
    assert rules["any"]["real_bug_findings_dropped"] == report.rate(2, 2)
    assert rules["os_limit"]["false_alarms_gone"] == report.rate(0, 2)
    assert rules["os_limit"]["real_bug_findings_dropped"] == report.rate(1, 2)
    assert rules["os_limit"]["leftovers_lost"] == report.rate(0, 2)


def test_a_doubt_rule_counts_only_the_developers_labels() -> None:
    runs = [Run(line("gold", "t/1"), flagged("refused", "refused"))]
    labels = by_key(
        label("gold-r1", 1, "false_alarm", by="claude-proposed", instance_id="t/1"),
        label("gold-r1", 2, "real_bug", by="claude-proposed", instance_id="t/1"),
    )
    rule = doubt_rows(runs, labels)["rules"]["refused"]
    assert rule["false_alarms_gone"] == report.rate(0, 0)
    assert rule["real_bug_findings_dropped"] == report.rate(0, 0)


def test_the_doubt_rows_are_only_worked_out_a_flagged_finding_still_counts() -> None:
    a = [Run(line("gold", ID), flagged(None, None))]
    b = [Run(line("gold", ID), flagged("refused", "refused"))]
    found = report.compare(a, b, {}, {}, {})
    assert found["levels"]["gold"] == {"up": 0, "down": 0, "same": 1}
    assert found["b"]["headline"] == found["a"]["headline"]
    assert found["b"]["guard_mutants"] == found["a"]["guard_mutants"]
    assert found["b"]["doubt"]["rules"]["refused"]["would_leave_counterexample"] == {
        "gold": report.rate(1, 1)
    }
    assert found["a"]["doubt"]["rules"]["refused"]["would_leave_counterexample"] == {
        "gold": report.rate(0, 1)
    }


def with_inputs(*inputs: dict[str, str], **changes: Any) -> Receipt:
    """A COUNTEREXAMPLE receipt whose findings hold these inputs, in order."""
    built = receipt("COUNTEREXAMPLE")
    found = [f.model_copy(update={"input": given})
             for f, given in zip(built.findings, inputs, strict=True)]  # fmt: skip
    return built.model_copy(update={"findings": found, **changes})


TRICKY = {"s": "'Ab'"}  # a whole tricky string, written as a receipt holds it
PLAIN = {"s": "'a'"}


def tricky_rows(runs: list[Run], labels: dict[Any, FindingLabel] | None = None) -> dict[str, Any]:
    plain = [Run(r.line, receipt("L2")) for r in runs]
    return report.compare(plain, runs, {}, {}, labels or {})["b"]["tricky_strings"]


def test_the_tricky_rows_count_findings_by_their_input_per_kind() -> None:
    older = with_inputs(TRICKY, PLAIN)
    with_older = older.model_copy(update={"pre_existing": [older.findings[0], older.findings[1]]})
    rows = tricky_rows([Run(line("gold", "t/1"), with_older),
                        Run(line("gold", "t/2"), with_inputs(PLAIN, PLAIN)),
                        Run(line("partial", "t/1"), with_inputs(TRICKY, TRICKY)),
                        Run(line("agent_ok", "t/3"), receipt("L2"))])  # fmt: skip
    assert rows["findings"] == {"agent_ok": report.rate(0, 0), "gold": report.rate(1, 4),
                                "partial": report.rate(2, 2)}  # fmt: skip
    assert rows["pre_existing"] == {"agent_ok": report.rate(0, 0), "gold": report.rate(1, 2),
                                    "partial": report.rate(0, 0)}  # fmt: skip


def test_the_tricky_rows_read_the_labels_of_the_findings_that_need_one() -> None:
    def replays(*results: str) -> dict[str, Any]:
        return {"replay": replayed(*results)}

    runs = [
        Run(line("gold", "t/1"), with_inputs(TRICKY, TRICKY)),
        Run(line("gold", "t/2"), with_inputs(TRICKY, PLAIN)),
        # Finding 1 passes on gold, so no one has to label it; finding 2 isn't tricky.
        Run(line("partial", "t/4", **replays("fixed", "still_fails")), with_inputs(TRICKY, PLAIN)),
    ]
    labels = by_key(
        label("gold-r1", 1, "false_alarm", instance_id="t/1"),
        label("gold-r1", 2, "real_bug", by="claude-proposed", instance_id="t/1"),  # not reviewed
        label("gold-r1", 2, "false_alarm", instance_id="t/2"),  # a plain input's
    )
    assert tricky_rows(runs, labels)["labels"] == {
        "gold": {"false_alarm": 1, "unreviewed": 2}, "partial": {},
    }  # fmt: skip


def test_the_tricky_rows_say_which_leftovers_only_they_found() -> None:
    def replays(*results: str) -> dict[str, Any]:
        return {"replay": replayed(*results)}

    rows = tricky_rows([
        Run(line("partial", "t/1", **replays("fixed", "still_fails")), with_inputs(TRICKY, PLAIN)),
        Run(line("partial", "t/2", **replays("fixed", "fixed")), with_inputs(TRICKY, PLAIN)),
        Run(line("agent_wrong", "t/3", **replays("still_fails", "fixed")),
            with_inputs(TRICKY, PLAIN)),
        Run(line("partial", "t/4"), with_inputs(TRICKY, TRICKY)),  # no leftover found
        # A correct fix has no leftover to find:
        Run(line("gold", "t/5", **replays("fixed", "fixed")), with_inputs(TRICKY, TRICKY)),
    ])  # fmt: skip
    assert rows["leftovers_only_through_them"] == report.rate(1, 3)


def test_the_new_rows_leave_out_a_run_resting_only_on_updated_tests() -> None:
    aside = regressed("tests/test_changed.py")
    assert aside.level.value == "COUNTEREXAMPLE"
    flagged_run = Run(line("agent_ok", SECOND, variant="agent_ok"), flagged("refused", "refused"))
    runs = [Run(line("gold", ID), aside), flagged_run]
    plain = [Run(r.line, receipt("L2")) for r in runs]
    updated = {ID: frozenset({"tests/test_changed.py"})}
    arm = report.compare(plain, runs, {}, {}, {}, updated)["b"]
    assert arm["set_aside"] == 1
    assert arm["doubt"]["rules"]["refused"]["would_leave_counterexample"] == {
        "agent_ok": report.rate(1, 1)
    }
    assert arm["tricky_strings"]["findings"] == {"agent_ok": report.rate(0, 2)}


def test_the_comparison_page_shows_the_new_rows() -> None:
    runs = [Run(line("gold", ID), flagged("refused", "refused"))]
    body = report.compare(runs, runs, {}, {}, {})
    page = report.compare_markdown({"all": body}, "M11")
    assert "| doubt | findings: gold: refused: 2" in page
    assert "refused: would_leave_counterexample: gold: 1/1 (100%)" in page
    assert "| tricky_strings | findings: gold: 0/2 (0%)" in page


def test_the_rows_read_slice_2_as_its_committed_numbers_say() -> None:
    """Arm A of M11's comparison is slice 2 dev: the baseline in docs/plans/M11.md and
    docs/BENCHMARK.md, so a row counted differently would move M11's targets unnoticed."""
    prepared = benchmark.read_prepared(SLICE1 / "prepared" / "slice2")
    tasks = {c.task.instance_id for c in data.read_cases(SLICE1 / "cases" / "slice2.jsonl")}
    cases = data.read_cases(SLICE1 / "cases" / "slice2.jsonl")
    runs, labels = benchmark.result_set(SLICE1, "slice2", prepared, tasks)
    found = report.compare_by_split(cases, runs, runs, prepared, labels, labels)["all"]
    arm = found["a"]
    assert arm == found["b"]
    assert arm["set_aside"] == 12  # docs/BENCHMARK.md: regressions only in tests the PR updated
    assert arm["false_alarm"] == report.rate(8, 85)
    assert arm["no_input"] == report.rate(33, 145)
    mutants = arm["guard_mutants"]
    assert mutants["one_mutant_from_flipping"] == report.rate(49, 116)
    assert mutants["gold_one_mutant_from_flipping"] == report.rate(23, 46)
    assert (mutants["valid_mutants"]["median"], mutants["gold_valid_mutants"]["median"]) == (5, 4)
    assert mutants["valid_mutants_not_stopped"] == mutants["valid_mutants"]  # before the early stop
    assert mutants["gold_valid_mutants_not_stopped"] == mutants["gold_valid_mutants"]
    assert arm["headline"]["correct_false_alarm"] == report.rate(8, 85)
    assert arm["headline"]["agent_wrong_not_green_lit"] == report.rate(16, 20)
    assert arm["headline"]["partial_not_green_lit"] == report.rate(26, 28)
    assert round(arm["seconds"]["median"] / 60, 1) == 3.7
    assert round(arm["seconds"]["p90"] / 60, 1) == 16.5
    assert arm["timeouts"] == 0 and arm["seconds_with_timeouts"] == arm["seconds"]
    assert arm["blind"] == {"statuses": {}, "rule_would_cap_at_l1": {}}  # before S7
    kinds = ("agent_ok", "agent_wrong", "gold", "partial")
    doubt = arm["doubt"]  # before S5: no finding has a flag, so no rule moves anything
    assert doubt["findings"] == doubt["pre_existing"] == {kind: {} for kind in kinds}
    assert doubt["rules"]["any"]["false_alarms_gone"] == report.rate(0, 8)
    assert doubt["rules"]["any"]["real_bug_findings_dropped"] == report.rate(0, 10)
    assert doubt["rules"]["any"]["leftovers_lost"] == report.rate(0, 3)
    tricky = arm["tricky_strings"]  # before S6. proxy.py's b'\r\n' is bytes, none of these strings
    assert tricky["findings"] == {
        "agent_ok": report.rate(0, 4),
        "agent_wrong": report.rate(0, 5),
        "gold": report.rate(0, 10),
        "partial": report.rate(0, 9),
    }
    assert tricky["pre_existing"] == {
        "agent_ok": report.rate(0, 1),
        "agent_wrong": report.rate(0, 1),
        "gold": report.rate(0, 0),
        "partial": report.rate(0, 1),
    }
    assert tricky["labels"] == {kind: {} for kind in kinds}
    assert tricky["leftovers_only_through_them"] == report.rate(0, 3)
    assert {move["up"] + move["down"] for move in found["levels"].values()} == {0}
    assert found["not_green_lit"]["agent_wrong"]["sign_test_p"] == "1/1 (1.0000)"


def test_compare_writes_its_own_files_and_leaves_the_report_alone(tmp_path: Path) -> None:
    """`compare` from the files on disk: per split, into B's folder; slice 1's report.md and
    summary.json are never written."""
    data.write_cases(tmp_path / "cases" / "slice1.jsonl", [case(ID, 0)])
    prepared = tmp_path / "prepared" / "slice1"
    prepared.mkdir(parents=True)
    record = prepared_with((touched("f_t1"),))
    (prepared / f"{ID}.json").write_text(record.model_dump_json(), encoding="utf-8")
    anchored = {"cost_usd": 5.0, "live_usd": 0.25, "mode": "anchored"}
    arms = (("slice1-a", "L4", {"cost_usd": 1.5}), ("slice1-b", "COUNTEREXAMPLE", anchored))
    for name, level, spend in arms:
        results = Results(tmp_path / "results" / name)
        changes = {"replay": replayed("fixed", "still_fails")} if level != "L4" else {}
        found = line("partial", receipt=f"{ID}/v0-r1", **changes, **spend)
        (results.folder / ID / "v0-r1").mkdir(parents=True)
        (results.folder / ID / "v0-r1" / "receipt.json").write_text(
            receipt(level).model_dump_json(), encoding="utf-8")  # fmt: skip
        results.append(found)
    assert benchmark.write_compare(tmp_path, "slice1", "a", "b") == {
        "pairs": {"wrong_fixes": 1, "correct_fixes": 0},
        "sign_test_p": "1/2 (0.5000)",
    }
    folder = tmp_path / "results" / "slice1-b"
    written = json.loads((folder / "compare-slice1-a.json").read_text(encoding="ascii"))
    assert set(written) == {"all", "dev"}
    assert written["dev"]["a"]["misses"] == {report.NO_COUNTEREXAMPLE: 1}
    # Each arm's own, and the anchored one's live calls, not its receipt's estimate.
    assert written["all"]["live_spend_usd"] == {"a": 1.5, "b": 0.25}
    text = (folder / "compare-slice1-a.md").read_text(encoding="utf-8")
    assert text == report.compare_markdown(written, "Tracefix benchmark: slice1-b against "
                                                    "slice1-a") + "\n"  # fmt: skip
    assert not (folder / "report.md").exists() and not (tmp_path / "results" / "slice1").exists()
    same = benchmark.write_compare(tmp_path, "slice1", "a", "a")  # one set: its misses
    assert same["pairs"] == {"wrong_fixes": 1, "correct_fixes": 0}


def test_m11s_targets_as_the_committed_comparison_gives_them() -> None:
    """MILESTONES M11's targets on slice 2 dev, each against its limit, from the committed
    comparison (which the test above rebuilds from the receipts): four met, and the two the
    developer recorded as missed on 13 Nov 2026 really are missed, not reworded."""
    path = SLICE1 / "results" / "slice2-m11" / "compare-slice2.json"
    dev = json.loads(path.read_text(encoding="ascii"))["dev"]
    a, b = dev["a"], dev["b"]
    played_out = b["guard_mutants"]["valid_mutants_not_stopped"]
    assert (played_out["median"], played_out["n"]) == (7.0, 39)  # met, on the line: >= 7
    close_a, close_b = (arm["guard_mutants"]["one_mutant_from_flipping"] for arm in (a, b))
    assert (close_a, close_b) == (report.rate(49, 115), report.rate(87, 118))
    # Missed: at most half of A's share was the limit.
    assert close_b["n"] * close_a["of"] * 2 > close_a["n"] * close_b["of"]
    assert (a["no_input"], b["no_input"]) == (report.rate(33, 144), report.rate(31, 144))
    assert b["no_input"]["n"] > 22  # missed: down by a third was the limit
    assert (a["false_alarm"], b["false_alarm"]) == (report.rate(8, 85), report.rate(7, 85))  # met
    kept = [arm["headline"]["agent_wrong_not_green_lit"] for arm in (a, b)]
    assert kept == [report.rate(16, 20), report.rate(16, 20)]  # met: no fewer than A
    times = b["seconds_with_timeouts"]  # met, with the run that hit the 2-hour limit counted
    assert (b["timeouts"], times["n"], times["max"]) == (1, 145, 7200.766)
    assert times["median"] <= 5 * 60 and times["p90"] <= 20 * 60
    assert b["unreviewed"] == report.rate(0, 85)  # every finding that needs a label has one


def test_compare_refuses_a_result_set_that_has_no_runs(tmp_path: Path) -> None:
    """A mistyped `--a` or `--b` names a set with no runs.jsonl: `compare` says so and writes
    nothing, where it used to write a comparison against no runs."""
    data.write_cases(tmp_path / "cases" / "slice1.jsonl", [case(ID, 0)])
    (tmp_path / "prepared" / "slice1").mkdir(parents=True)
    Results(tmp_path / "results" / "slice1-a").append(line("gold", outcome="timeout"))
    for a, b in (("a", "typo"), ("typo", "a")):
        with pytest.raises(data.DataError, match=r"slice1-typo: no runs\.jsonl"):
            benchmark.write_compare(tmp_path, "slice1", a, b)
    assert not (tmp_path / "results" / "slice1-typo").exists()
    assert sorted(p.name for p in (tmp_path / "results" / "slice1-a").iterdir()) == ["runs.jsonl"]


def test_old_prepared_records_and_receipts_still_parse() -> None:
    """Every committed prepare record and slice 1 receipt (written before M11 S1/S2) still
    parses; their missing fields read as unknown (None)."""
    records = list((SLICE1 / "prepared" / "slice1").glob("*.json"))
    assert records
    for path in records:
        Prepared.model_validate_json(path.read_text(encoding="utf-8"))
    results = Results(SLICE1 / "results" / "slice1")
    counted = [ln for ln in results.lines() if ln.outcome == "receipt"]
    assert counted and all(results.receipt(ln) is not None for ln in counted)


# --- M11 S6: findings that use a tricky string ---------------------------------------------------


@pytest.mark.parametrize(
    ("given", "uses"),
    [
        ({"s": "'\u0130'"}, True),
        ({"s": "'\\r\\n'"}, True),  # receipts hold it as to_source writes it, escapes and all
        ({"n": "1", "s": "'\\u200b'"}, True),
        ({"names": "['\u00df']"}, True),
        ({"where": "{'k': 'Ab'}"}, True),
        # A made-up object: `self` is the literal of its code, so its escapes are written twice.
        ({"self": repr("Name(raw='\\ufeff')")}, True),
        ({"self": repr("Name(raw='Ab', n=1)")}, True),
        ({"s": "'a'"}, False),
        ({"s": "'\u00e9'"}, False),  # the older accent, not the decomposed one
        ({"s": "'xAb'"}, False),  # the string itself, not any text holding it
        ({"s": repr("'Ab'")}, False),  # a string with quotes in it is no object's code
        ({"n": "1"}, False),
        ({"self": repr("Name(raw='a')")}, False),
        ({"self": repr("not code (")}, False),
        ({"s": "not a literal ("}, False),
        ({}, False),
    ],
)
def test_s6_a_finding_uses_a_tricky_string_only_when_its_input_holds_one_whole(
    given: dict[str, str], uses: bool
) -> None:
    assert report.uses_tricky_string(given) is uses
