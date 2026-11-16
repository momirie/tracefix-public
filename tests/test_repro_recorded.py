"""M3 acceptance: the Reproducer on fixtures 1-7, replaying recorded model answers.

The expected outcome comes from each fixture's expected.json (ground truth). The test runs real
pytest in real worktrees; only the model's answers are replayed. No network by default.

Re-record (costs money, needs ANTHROPIC_API_KEY):
    TRACEFIX_RECORD=1 uv run pytest tests/test_repro_recorded.py
"""

import json
import os
from pathlib import Path

import make_fixtures
import pytest

from tracefix.diffscope import compute_scope
from tracefix.llm import AnthropicProvider, LLMClient, Provider, RecordedProvider, RecordingProvider
from tracefix.repro import ReproStatus, reproduce
from tracefix.workspace import Workspace

RECORDINGS = Path(__file__).parent / "recordings"
CASES = [c for c in sorted(make_fixtures.CASES) if c != "env_broken"]  # env_broken stops earlier


def provider() -> Provider:
    if os.environ.get("TRACEFIX_RECORD") == "1":
        return RecordingProvider(AnthropicProvider(), RECORDINGS)
    return RecordedProvider(RECORDINGS)


def expected_reproduce(case: str) -> ReproStatus:
    data = json.loads((make_fixtures.FIXTURES_DIR / case / "expected.json").read_text("utf-8"))
    return ReproStatus(data["receipt"]["stages"]["reproduce"])


def issue_text(case: str) -> str:
    return (make_fixtures.FIXTURES_DIR / case / "ISSUE.md").read_text(encoding="utf-8")


def test_every_case_but_env_broken_is_covered() -> None:
    assert len(CASES) == 9


@pytest.mark.parametrize("case", CASES)
def test_reproducer_matches_expected_json(case: str, built: dict[str, Path]) -> None:
    client = LLMClient(provider())
    with Workspace(built[case], "base", "head") as ws:
        scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
        result = reproduce(ws, scope, issue_text(case), client)
    summary = [(a.number, a.verdict.value, a.reason) for a in result.attempts]
    assert result.status is expected_reproduce(case), f"{result.reason}\n{summary}"
    assert len(client.calls) <= 3
