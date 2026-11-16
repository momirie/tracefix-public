"""M6 acceptance: Break My Fix on every fixture, graded against expected.json (ground truth).

The reproducer's and the adversary's answers are replayed from tests/recordings; everything else
is real: copies, watched runs, the in-run harness, probes and repro files.

Record missing answers (costs money, needs ANTHROPIC_API_KEY); existing ones are replayed:
    TRACEFIX_RECORD=1 uv run pytest tests/test_attack_recorded.py
"""

import json
from pathlib import Path
from typing import Any

import make_fixtures
import pytest
from test_guard_recorded import provider
from test_repro_recorded import issue_text

from tracefix.attack import AttackResult, AttackStatus, Finding, break_my_fix
from tracefix.attack_runtime import from_source
from tracefix.diffscope import compute_scope
from tracefix.llm import LLMClient, LLMRequest, LLMResponse, MissingRecording, Provider
from tracefix.repro import ReproStatus, reproduce
from tracefix.runner import Outcome
from tracefix.workspace import Workspace

CASES = sorted(make_fixtures.CASES)


class NoMissing:
    """A provider that remembers the requests it has no recording for."""

    def __init__(self, inner: Provider) -> None:
        self.inner = inner
        self.missing: list[str] = []

    def send(self, request: LLMRequest) -> LLMResponse:
        try:
            return self.inner.send(request)
        except MissingRecording:
            self.missing.append(f"{request.role} {request.key()[:32]}")
            raise


def expected(case: str) -> dict[str, Any]:
    path = make_fixtures.FIXTURES_DIR / case / "expected.json"
    receipt: dict[str, Any] = json.loads(path.read_text("utf-8"))["receipt"]
    return receipt


def summary(result: AttackResult) -> str:
    lines = [f"{result.status}: {result.reason}"]
    for f in result.findings:
        lines.append(f"  finding {f.function} {dict(f.input)} {f.outcome} | {f.relation}")
    lines += [f"  pre-existing {f.function} {dict(f.input)}" for f in result.pre_existing]
    lines += [f"  discarded {d.input} {d.property}: {d.reason}" for d in result.discarded]
    for p in result.properties:
        lines.append(f"  property {p.id or '-'} {p.name!r} {p.status} {p.reason[:150]}")
        lines.append(f"      {p.claim[:150]}")
    lines += [f"  target {t.function}: {t.inputs_tried} inputs, {t.reason}" for t in result.targets]
    return "\n".join(lines + [f"  note {n}" for n in result.notes])


def matches(finding: Finding, must: dict[str, Any]) -> bool:
    """A finding is the expected one: same function, the expected input among the ones it shows,
    and the expected outcome ("ValueError", "returns 29, not 28", or "returns 8080": the value
    only). A method's input without "self" matches on any object (M7.5)."""
    if finding.function != must["function"]:
        return False
    inputs = [finding.input, *(i for i in finding.other_inputs if i is not None)]
    wanted = must["input"]

    def shown(args: tuple[tuple[str, str], ...]) -> dict[str, Any]:
        return {k: from_source(v) for k, v in args if k != "self" or "self" in wanted}

    if not any(shown(args) == wanted for args in inputs):
        return False
    outcome: str = must["outcome"]
    if outcome.startswith("returns "):
        value, _, should = outcome.removeprefix("returns ").partition(", not ")
        same = finding.outcome.get("repr") == value
        return same and (not should or finding.expected == should)
    return finding.outcome.get("kind") == "raised" and finding.outcome.get("type") == outcome


def test_the_cases_graded_on_break_my_fix_are_covered() -> None:
    finds = [
        c for c in CASES if any(m["stage"] == "break_my_fix" for m in expected(c)["must_find"])
    ]
    quiet = [c for c in CASES if "break_my_fix_finding" in expected(c)["must_not_find"]]
    assert finds == ["method_partial", "partial_fix", "special_cased"]
    assert quiet == ["env_broken", "good_fix", "method_good", "unguarded_test"]


@pytest.mark.parametrize("case", CASES)
def test_break_my_fix_matches_expected_json(case: str, built: dict[str, Path]) -> None:
    answer = expected(case)
    spy = NoMissing(provider())
    client = LLMClient(spy)
    with Workspace(built[case], "base", "head") as ws:
        scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
        # The pipeline stops at ENVIRONMENT_ERROR before the Reproducer; Break My Fix still gets
        # to show it finds nothing it can't prove.
        repro = (
            reproduce(ws, scope, issue_text(case), client)
            if "reproduce" in answer["stages"]
            else None
        )
        if repro is not None:
            assert repro.status is ReproStatus(answer["stages"]["reproduce"]), repro.reason
        result = break_my_fix(ws, scope, repro, issue_text(case), client)
        assert ws.copies == [ws.base, ws.head]
    for must in answer["must_find"]:
        if must["stage"] == "break_my_fix":
            assert any(matches(f, must) for f in result.findings), summary(result)
    if "break_my_fix_finding" in answer["must_not_find"]:
        assert not result.findings, summary(result)
    # What every receipt relies on: each finding proven by its own failing repro file on head.
    for finding in result.findings:
        assert finding.repro_run is not None and finding.repro_run.outcome is Outcome.FAILED
        assert finding.property is not None and finding.property.status == "counted"
    assert result.status is not AttackStatus.INVALID, summary(result)
    # The request, at most one follow-up, and the second sample (ADVERSARY_SAMPLES).
    assert sum(c.role == "adversary" for c in client.calls) <= 3
    # Every request is byte for byte one already recorded: a fixture whose targets all ran inputs
    # gets no new follow-up (M11 S3). A missing first answer or follow-up raises by itself; a
    # missing second sample is only a note, so the spy is what catches that one.
    assert not spy.missing, summary(result)
