"""Opt-in live test: calls the real Anthropic API (costs money).

Run with:  TRACEFIX_LIVE=1 uv run pytest -m live
"""

import os
from pathlib import Path

import make_fixtures
import pytest

from tracefix.diffscope import compute_scope
from tracefix.llm import AnthropicProvider, LLMClient
from tracefix.repro import ReproStatus, reproduce
from tracefix.workspace import Workspace

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(os.environ.get("TRACEFIX_LIVE") != "1", reason="set TRACEFIX_LIVE=1"),
]


def test_live_reproducer_on_good_fix(built: dict[str, Path]) -> None:
    issue = (make_fixtures.FIXTURES_DIR / "good_fix" / "ISSUE.md").read_text(encoding="utf-8")
    client = LLMClient(AnthropicProvider(), max_calls=3)
    with Workspace(built["good_fix"], "base", "head") as ws:
        scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
        result = reproduce(ws, scope, issue, client)
    tokens = [(c.input_tokens, c.output_tokens) for c in client.calls]
    print(f"\nlive calls: {len(client.calls)}, tokens (in, out): {tokens}")
    assert result.status is ReproStatus.REPRODUCED, result.reason


def test_live_guard_on_good_fix(built: dict[str, Path]) -> None:
    from tracefix.guard import GuardStatus, guard

    issue = (make_fixtures.FIXTURES_DIR / "good_fix" / "ISSUE.md").read_text(encoding="utf-8")
    client = LLMClient(AnthropicProvider(), max_calls=6)  # reproducer (3 + retries) and mutator
    with Workspace(built["good_fix"], "base", "head") as ws:
        scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
        result = guard(ws, scope, reproduce(ws, scope, issue, client), client)
    print(f"\nguard: {result.status}, kill rate {result.kill_rate}, rejected {result.rejected}")
    assert result.status is GuardStatus.GUARDED, result.reason


def test_live_break_my_fix_on_partial_fix(built: dict[str, Path]) -> None:
    from tracefix.attack import AttackStatus, break_my_fix

    issue = (make_fixtures.FIXTURES_DIR / "partial_fix" / "ISSUE.md").read_text(encoding="utf-8")
    client = LLMClient(AnthropicProvider(), max_calls=3)  # the adversary only: 2 calls at most
    with Workspace(built["partial_fix"], "base", "head") as ws:
        scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
        result = break_my_fix(ws, scope, None, issue, client)
    print(f"\nbreak my fix: {result.status}, {[(f.function, f.input) for f in result.findings]}")
    assert result.status is AttackStatus.FOUND, result.reason
    assert any(dict(f.input) == {"raw": "''"} for f in result.findings)


def test_live_judge_on_wrong_but_green(built: dict[str, Path]) -> None:
    from tracefix.behaviour_diff import behaviour_diff

    case = "wrong_but_green"
    issue = (make_fixtures.FIXTURES_DIR / case / "ISSUE.md").read_text(encoding="utf-8")
    client = LLMClient(AnthropicProvider(), max_calls=8)  # reproducer (3 + retries), Judge (2x2)
    with Workspace(built[case], "base", "head") as ws:
        scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
        result = behaviour_diff(ws, scope, reproduce(ws, scope, issue, client), issue, client)
    labels = result.judge.by_id
    wanted = {"value": "-5", "width": "10"}
    negative = [c for g in result.groups for c in g.shown if dict(c.args) == wanted]
    print(f"\njudge: {result.judge.status}, labels {labels}")
    assert negative and labels.get(negative[0].id) == "suspicious"
    assert not result.l3.allowed
