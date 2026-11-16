"""M7 acceptance: the behaviour diff and the Judge on every fixture, graded against expected.json
(ground truth).

The reproducer's and the Judge's answers are replayed from tests/recordings; everything else is
real: copies, watched runs on both sides, the in-run harness.

Record missing answers (costs money, needs ANTHROPIC_API_KEY); existing ones are replayed:
    TRACEFIX_RECORD=1 uv run pytest tests/test_behaviour_recorded.py
"""

import json
from pathlib import Path
from typing import Any

import make_fixtures
import pytest
from test_guard_recorded import provider
from test_repro_recorded import issue_text

from tracefix.attack_runtime import from_source
from tracefix.behaviour_diff import BehaviourResult, BehaviourStatus, behaviour_diff
from tracefix.behaviour_rules import Change
from tracefix.diffscope import compute_scope
from tracefix.judge import JUDGE_CALLS, JUDGE_SAMPLES, JudgeStatus
from tracefix.llm import LLMClient
from tracefix.repro import ReproStatus, reproduce
from tracefix.workspace import Workspace

CASES = sorted(make_fixtures.CASES)


def expected(case: str) -> dict[str, Any]:
    path = make_fixtures.FIXTURES_DIR / case / "expected.json"
    receipt: dict[str, Any] = json.loads(path.read_text("utf-8"))["receipt"]
    return receipt


def summary(result: BehaviourResult) -> str:
    labels = {lab.change: (lab.label, lab.reason) for lab in result.judge.labels}
    lines = [
        f"{result.status}: {result.reason}",
        f"  checks {result.checks.reasons}",
        f"  l3 {result.l3}",
        f"  judge {result.judge.status} {result.judge.notes}",
    ]
    for g in result.groups:
        lines.append(f"  group {g.key} {len(g.changes)} explained={g.explained}")
        for c in g.shown:
            b, a = c.before.outcome or {}, c.after.outcome or {}
            lines.append(f"    {c.id} {dict(c.args)} {b.get('text')} -> {a.get('text')} "
                         f"{labels.get(c.id)}")  # fmt: skip
    return "\n".join(lines + [f"  note {n}" for n in result.notes])


def labelled(result: BehaviourResult) -> list[tuple[str, Change, str]]:
    """(function, change, label) for every shown change."""
    functions = {t.id: t.function for t in result.targets}
    labels = result.judge.by_id
    return [(functions[g.target], c, labels.get(c.id, "")) for g in result.groups for c in g.shown]


def matches(function: str, change: Change, label: str, must: dict[str, Any]) -> bool:
    """The expected change: same function and input, the expected outcomes before and after the
    fix, and the expected label."""
    if function != must["function"]:
        return False
    if {k: from_source(v) for k, v in change.args} != must["input"]:
        return False
    before, after = change.before.outcome or {}, change.after.outcome or {}
    return (before.get("text"), after.get("text"), label) == (
        must["base"],
        must["head"],
        must["label"],
    )


def test_the_cases_graded_on_the_behaviour_diff_are_covered() -> None:
    finds = [
        c for c in CASES if any(m["stage"] == "behaviour_diff" for m in expected(c)["must_find"])
    ]
    quiet = [c for c in CASES if "suspicious_behaviour_change" in expected(c)["must_not_find"]]
    assert finds == ["wrong_but_green"]
    assert quiet == ["env_broken", "good_fix", "method_good"]


@pytest.mark.parametrize("case", CASES)
def test_the_behaviour_diff_matches_expected_json(case: str, built: dict[str, Path]) -> None:
    answer = expected(case)
    client = LLMClient(provider())
    with Workspace(built[case], "base", "head") as ws:
        scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
        # The pipeline stops at ENVIRONMENT_ERROR before the Reproducer; the diff still gets to
        # show it compares nothing it can't load.
        repro = (
            reproduce(ws, scope, issue_text(case), client)
            if "reproduce" in answer["stages"]
            else None
        )
        if repro is not None:
            assert repro.status is ReproStatus(answer["stages"]["reproduce"]), repro.reason
        judge_calls = len(client.calls)
        result = behaviour_diff(ws, scope, repro, issue_text(case), client)
        assert ws.copies == [ws.base, ws.head]
    found = labelled(result)
    for must in answer["must_find"]:
        if must["stage"] == "behaviour_diff":
            assert any(matches(*f, must) for f in found), summary(result)
    if "suspicious_behaviour_change" in answer["must_not_find"]:
        assert not any(label == "suspicious" for _, _, label in found), summary(result)
    assert result.status is not BehaviourStatus.INVALID, summary(result)
    # Two samples, each the request and at most one follow-up.
    assert sum(c.role == "judge" for c in client.calls[judge_calls:]) <= JUDGE_SAMPLES * JUDGE_CALLS
    # Whatever the Judge said, L3 never goes past what our own checks allow.
    assert result.checks.allowed or not result.l3.allowed
    if result.groups:
        assert result.judge.status is JudgeStatus.LABELLED, summary(result)
    CASE_CHECKS.get(case, lambda _: None)(result)


def good_fix(result: BehaviourResult) -> None:
    """Explained by its own reproduction test, and every shown change labelled intended: L3."""
    assert result.checks.allowed, summary(result)
    [group] = result.groups
    assert "the reproduction test calls this input" in group.explained
    assert result.l3.allowed, summary(result)


def wrong_but_green(result: BehaviourResult) -> None:
    """Our own checks stop it (a broken docstring example); the Judge agrees, but needn't."""
    assert not result.checks.allowed, summary(result)
    assert any("breaks the docstring example" in r for r in result.checks.reasons)
    assert not result.l3.allowed


def env_broken(result: BehaviourResult) -> None:
    """Nothing can be loaded, so nothing is compared and no Judge is asked."""
    assert result.status is BehaviourStatus.INCONCLUSIVE, summary(result)
    assert result.judge.status is JudgeStatus.NOT_NEEDED and not result.l3.allowed


CASE_CHECKS = {"good_fix": good_fix, "wrong_but_green": wrong_but_green, "env_broken": env_broken}
