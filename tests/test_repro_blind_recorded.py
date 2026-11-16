"""The blind shadow test on the fixtures, replaying recorded model answers; real pytest runs.

No fixture's expected.json names a blind result: it is report only and has no ground truth, so
this checks that it ran, within its bounds, with every answer recorded.

Record missing answers (costs money, needs ANTHROPIC_API_KEY); existing ones are replayed:
    TRACEFIX_RECORD=1 uv run pytest tests/test_repro_blind_recorded.py
"""

from pathlib import Path

import pytest
from test_guard_recorded import provider
from test_repro_recorded import CASES, issue_text

from tracefix.diffscope import compute_scope
from tracefix.llm import LLMClient
from tracefix.repro import BLIND_ATTEMPTS, BlindStatus, ReproStatus, blind, reproduce
from tracefix.workspace import Workspace


@pytest.mark.parametrize("case", CASES)
def test_blind_runs_after_a_reproduction_and_only_then(case: str, built: dict[str, Path]) -> None:
    client = LLMClient(provider())
    issue = issue_text(case)
    with Workspace(built[case], "base", "head") as ws:
        scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
        main = reproduce(ws, scope, issue, client)
        before = len(client.calls)
        result = blind(ws, scope, main, issue, client)
    if main.status is not ReproStatus.REPRODUCED:
        assert result.status is BlindStatus.NOT_RUN and len(client.calls) == before
        return
    assert not client.problems, client.problems
    assert result.status is not BlindStatus.NOT_RUN, result.reason
    assert 1 <= len(client.calls) - before <= BLIND_ATTEMPTS * 2  # each may retry a bad format
    assert result.test_code is not None
