"""The Claude Code hooks in scripts/: which commands count as a commit, and the format hook."""

import io
import json
import subprocess
from pathlib import Path
from typing import Any

import commit_hook
import format_hook
import pytest

COMMITS = [
    "git commit -m x",
    'cd /c/repo && git commit -q -m "M5: integrity"',
    "git -c user.name=a commit -m z",
    "git add -A && git commit --amend --no-edit",
    "(git commit -m x)",
]
NOT_COMMITS = [
    "git status",
    "sed -n 1,2p src/tracefix/guard.py",
    "git log --grep commit",
    "echo committed",
    "gitcommit",
    "git show HEAD:docs/commit.md",
]


@pytest.mark.parametrize("command", COMMITS)
def test_commit_commands_are_recognised(command: str) -> None:
    assert commit_hook.COMMIT.search(command)


@pytest.mark.parametrize("command", NOT_COMMITS)
def test_other_commands_are_not_commits(command: str) -> None:
    assert not commit_hook.COMMIT.search(command)


def _run_hook(monkeypatch: pytest.MonkeyPatch, payload: str) -> tuple[int, list[Any]]:
    calls: list[Any] = []

    def fake_run(args: list[str], **_: Any) -> subprocess.CompletedProcess[bytes]:
        calls.append(args)
        return subprocess.CompletedProcess(args, 1)

    monkeypatch.setattr(commit_hook.subprocess, "run", fake_run)
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    return commit_hook.main(), calls


def test_the_checks_run_and_block_only_for_a_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    code, calls = _run_hook(monkeypatch, json.dumps({"tool_input": {"command": "git status"}}))
    assert (code, calls) == (0, [])
    code, calls = _run_hook(monkeypatch, json.dumps({"tool_input": {"command": "git commit"}}))
    assert code == 2 and len(calls) == 1 and calls[0][-2:] == [calls[0][-2], "--fast"]
    assert calls[0][-2].endswith("check.py")
    assert _run_hook(monkeypatch, "not json")[0] == 0


def test_format_hook_formats_python_and_ignores_the_rest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    messy = tmp_path / "messy.py"
    messy.write_text("x = {  'a':1 }\n", encoding="utf-8")
    notes = tmp_path / "notes.md"
    notes.write_text("x = {  'a':1 }\n", encoding="utf-8")
    for path in (messy, notes):
        payload = json.dumps({"tool_input": {"file_path": str(path)}})
        monkeypatch.setattr("sys.stdin", io.StringIO(payload))
        assert format_hook.main() == 0
    assert messy.read_text(encoding="utf-8") == 'x = {"a": 1}\n'
    assert notes.read_text(encoding="utf-8") == "x = {  'a':1 }\n"
    monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
    assert format_hook.main() == 0
