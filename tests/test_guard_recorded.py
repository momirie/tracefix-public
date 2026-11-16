"""M4 acceptance: Guard on every fixture whose expected.json names a guard result.

The reproducer's and the mutator's answers are replayed from tests/recordings; everything else is
real: copies, pytest runs, the tamper watch. Graded against expected.json (ground truth).

Record missing answers (costs money, needs ANTHROPIC_API_KEY); existing ones are replayed:
    TRACEFIX_RECORD=1 uv run pytest tests/test_guard_recorded.py
"""

import json
import os
from pathlib import Path
from typing import Any

import make_fixtures
import pytest
from test_repro_recorded import RECORDINGS, issue_text

from tracefix.diffscope import compute_scope
from tracefix.guard import GuardResult, GuardStatus, MutantStatus, guard
from tracefix.llm import (
    AnthropicProvider,
    LLMClient,
    LLMRequest,
    LLMResponse,
    MissingRecording,
    Provider,
    RecordedProvider,
    RecordingProvider,
)
from tracefix.repro import ReproStatus, reproduce
from tracefix.workspace import Workspace


def expected(case: str) -> dict[str, Any]:
    path = make_fixtures.FIXTURES_DIR / case / "expected.json"
    receipt: dict[str, Any] = json.loads(path.read_text("utf-8"))["receipt"]
    return receipt


CASES = [c for c in sorted(make_fixtures.CASES) if "guard" in expected(c)["stages"]]


class ReplayOrRecord:
    """Replays what is recorded; sends only missing requests live (and records them)."""

    def __init__(self, directory: Path) -> None:
        self.replay = RecordedProvider(directory)
        self.record = RecordingProvider(AnthropicProvider(), directory)

    def send(self, request: LLMRequest) -> LLMResponse:
        try:
            return self.replay.send(request)
        except MissingRecording:
            return self.record.send(request)


def provider() -> Provider:
    if os.environ.get("TRACEFIX_RECORD") == "1":
        return ReplayOrRecord(RECORDINGS)
    return RecordedProvider(RECORDINGS)


def summary(result: GuardResult) -> str:
    lines = [f"{result.status}: {result.reason}"]
    for r in result.mutants:
        m = r.mutant
        lines.append(f"  #{m.number} {m.path}:{m.line} {m.original!r} -> {m.replacement!r}: "
                     f"{r.status} {r.killed_by} {r.reason}")  # fmt: skip
    lines += [f"  rejected {r.proposal.line} {r.proposal.original!r}: {r.reason}"
              for r in result.rejected]  # fmt: skip
    return "\n".join(lines + [f"  note: {n}" for n in result.notes])


def test_the_four_cases_with_a_guard_answer_are_covered() -> None:
    # partial_fix has none since M4: its verdict flips with the mutants (see fixtures README).
    assert CASES == ["good_fix", "method_good", "unguarded_test", "wrong_but_green"]


@pytest.mark.parametrize("case", CASES)
def test_guard_matches_expected_json(case: str, built: dict[str, Path]) -> None:
    client = LLMClient(provider())
    with Workspace(built[case], "base", "head") as ws:
        scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
        repro = reproduce(ws, scope, issue_text(case), client)
        assert repro.status is ReproStatus.REPRODUCED, repro.reason
        result = guard(ws, scope, repro, client)
    answer = expected(case)
    assert result.status is GuardStatus(answer["stages"]["guard"]), summary(result)
    for must in answer["must_find"]:
        if must["stage"] == "guard":
            assert any(f.kind == must["kind"] and f.file == must["file"] for f in result.findings)
    # What the receipt will show: who killed each mutant, and the repro test's own rate.
    valid = [r for r in result.mutants if r.status is not MutantStatus.DISCARDED]
    assert len(valid) >= 3, summary(result)
    assert all(bool(r.killed_by) == (r.status is MutantStatus.KILLED) for r in valid)
    assert result.repro_kill_rate is not None and result.kill_rate is not None
    assert sum(c.role == "mutator" for c in client.calls) <= 2
