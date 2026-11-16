import io
import json
import os
import shutil
import socket
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import make_fixtures
import pytest
from conftest import make_repo
from synthetic import attack, finding, l4_run

from tracefix import __version__, cli, pipeline
from tracefix.attack import AttackStatus
from tracefix.cli import (
    MAX_ISSUE_CHARS,
    UsageError,
    build_parser,
    flag_settings,
    main,
    read_issue,
    write_out,
)
from tracefix.config import FileSettings
from tracefix.llm import FakeProvider
from tracefix.pipeline import Verified
from tracefix.receipt import build
from tracefix.record import RunStatus
from tracefix.workspace import Workspace

VERIFY_ARGS = ["verify", "--repo", ".", "--base", "HEAD~1", "--head", "HEAD", "--issue", "x"]


def test_help_prints_usage_and_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "usage: tracefix" in out
    assert "verify" in out


def test_verify_help_lists_all_required_flags(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["verify", "--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for flag in ("--repo", "--base", "--head", "--issue"):
        assert flag in out


@pytest.mark.parametrize("missing", ["--repo", "--base", "--head", "--issue"])
def test_verify_rejects_missing_flag(missing: str) -> None:
    i = VERIFY_ARGS.index(missing)
    argv = VERIFY_ARGS[:i] + VERIFY_ARGS[i + 2 :]
    with pytest.raises(SystemExit) as exc:
        main(argv)
    assert exc.value.code == 2


def test_no_subcommand_is_an_error() -> None:
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


def test_installed_console_script_runs() -> None:
    exe = shutil.which("tracefix", path=str(Path(sys.executable).parent))
    assert exe, "tracefix console script is not installed in this environment"
    result = subprocess.run([exe, "--help"], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0
    assert "usage: tracefix" in result.stdout


def test_python_dash_m_runs() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "tracefix", "--version"], capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0
    assert f"tracefix {__version__}" in result.stdout


# --- tracefix verify (M8, plan P15) ---------------------------------------------------------------


def test_the_issue_is_a_file_stdin_or_the_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    issue = tmp_path / "issue.md"
    issue.write_bytes("﻿# Title\r\n\r\nbody é\r\n".encode())
    assert read_issue(str(issue)) == "# Title\n\nbody é\n"  # BOM and CRLF dropped
    assert read_issue("f(-1) gives -1") == "f(-1) gives -1"
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b"from stdin\r\n")))
    assert read_issue("-") == "from stdin\n"


@pytest.mark.parametrize(
    ("content", "message"),
    [(b"  \n\t", "the issue is empty"), (b"\xff\xfe\xfa", "not UTF-8"),
     (b"x" * (MAX_ISSUE_CHARS + 1), "longer than 100,000")],
    ids=["empty", "not-utf8", "too-long"],
)  # fmt: skip
def test_an_unusable_issue_is_refused(tmp_path: Path, content: bytes, message: str) -> None:
    issue = tmp_path / "issue.md"
    issue.write_bytes(content)
    with pytest.raises(UsageError, match=message):
        read_issue(str(issue))


def _flags(*extra: str) -> FileSettings:
    return flag_settings(build_parser().parse_args([*VERIFY_ARGS, *extra]))


def test_flags_become_settings() -> None:
    flags = _flags("--model", "adversary=claude-sonnet-5-5", "--model", "judge=claude-opus-5",
                   "--effort", "high", "--max-tokens", "8000", "--max-llm-calls", "12",
                   "--token-budget", "90000", "--suite-timeout", "60",
                   "--pytest-plugin", "pytest_mock", "--pytest-plugin", "xdist.plugin")  # fmt: skip
    assert flags == FileSettings(
        models={"adversary": "claude-sonnet-5-5", "judge": "claude-opus-5"}, effort="high",
        max_tokens=8000, max_llm_calls=12, token_budget=90_000, suite_timeout_seconds=60,
        pytest_plugins=["pytest_mock", "xdist.plugin"])  # fmt: skip
    assert _flags() == FileSettings()  # nothing given: the config file and defaults decide


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        (["--model", "adversary"], "ROLE=MODEL"),
        (["--model", "judge=a", "--model", "judge=b"], "given twice for judge"),
        (["--model", "boss=claude-opus-5-5"], "models.boss"),
        (["--model", "judge=Not A Model"], "not a model id"),
        (["--max-tokens", "999999"], "max_tokens"),
        (["--suite-timeout", "1"], "suite_timeout_seconds"),
        (["--pytest-plugin", "-p evil"], "not a module name"),
    ],
)
def test_bad_flags_exit_2_before_anything_runs(
    extra: list[str], message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([*VERIFY_ARGS, *extra], provider=FakeProvider([])) == 2
    assert message in capsys.readouterr().err


def test_an_unknown_effort_is_an_argparse_error() -> None:
    with pytest.raises(SystemExit) as exc:
        main([*VERIFY_ARGS, "--effort", "huge"])
    assert exc.value.code == 2


def test_nothing_to_verify_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    argv = ["verify", "--repo", str(tmp_path), "--base", "a", "--head", "b", "--issue", "x",
            "--out", str(tmp_path / "out")]  # fmt: skip
    assert main(argv, provider=FakeProvider([])) == 2
    assert "not a git repository" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()  # no receipt


def _verified(tmp_path: Path) -> Verified:
    found = replace(attack(), status=AttackStatus.FOUND, findings=(finding(2),))
    run = replace(l4_run(break_my_fix=found), status=RunStatus.OK)
    workspace = Workspace(tmp_path, "main", "fix")
    return Verified(run, build(run, workspace))


def test_the_receipt_files_are_written_and_only_ours_replaced(tmp_path: Path) -> None:
    out = tmp_path / "out"
    (out / "findings").mkdir(parents=True)
    (out / "findings" / "finding_9.py").write_text("old run\n")
    (out / "findings" / "notes.txt").write_text("mine\n")
    (out / "keep.md").write_text("mine\n")
    verified = _verified(tmp_path)
    write_out(out, verified)
    names = sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())
    assert names == ["findings/finding_2.py", "findings/notes.txt", "keep.md", "receipt.json",
                     "receipt.md", "repro/test_tracefix_repro.py"]  # fmt: skip
    assert json.loads((out / "receipt.json").read_text("utf-8"))["level"] == "COUNTEREXAMPLE"
    assert verified.receipt.findings[0].file == "findings/finding_2.py"
    assert (out / "findings" / "finding_2.py").read_text("utf-8") == finding(2).repro_code
    assert (out / "receipt.md").read_text("utf-8").startswith("## Fix Receipt: COUNTEREXAMPLE")


def test_verify_writes_the_receipt_and_json_alone_on_stdout(
    built: dict[str, Path], tmp_path: Path, capsysbinary: pytest.CaptureFixture[bytes]
) -> None:
    out = tmp_path / "out"
    issue = make_fixtures.FIXTURES_DIR / "env_broken" / "ISSUE.md"
    argv = ["verify", "--repo", str(built["env_broken"]), "--base", "base", "--head", "head",
            "--issue", str(issue), "--out", str(out), "--json"]  # fmt: skip
    assert main(argv, provider=FakeProvider([])) == 0
    captured = capsysbinary.readouterr()
    receipt = json.loads(captured.out.decode("utf-8"))  # nothing else on stdout
    assert (receipt["status"], receipt["level"]) == ("ENVIRONMENT_ERROR", "L0")
    assert receipt == json.loads((out / "receipt.json").read_text("utf-8"))
    assert captured.err.isascii() and b"[1/10] environment: ENVIRONMENT_ERROR" in captured.err
    assert "lacks 'acme_metrics'" in receipt["status_reason"]
    assert (out / "receipt.md").is_file()


def test_the_installed_command_verifies_without_any_api_access(
    built: dict[str, Path], tmp_path: Path
) -> None:
    """env_broken stops before any model call; even so, no credentials and an API address that
    refuses connections, so an accidental call could never leave the machine."""
    exe = shutil.which("tracefix", path=str(Path(sys.executable).parent))
    assert exe
    with socket.socket() as closed:
        closed.bind(("127.0.0.1", 0))
        port = closed.getsockname()[1]
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("ANTHROPIC")}
    env["ANTHROPIC_BASE_URL"] = f"http://127.0.0.1:{port}"
    issue = make_fixtures.FIXTURES_DIR / "env_broken" / "ISSUE.md"
    out = tmp_path / "out"
    result = subprocess.run(
        [exe, "verify", "--repo", str(built["env_broken"]), "--base", "base", "--head", "head",
         "--issue", str(issue), "--out", str(out)],
        capture_output=True, env=env, timeout=300,
    )  # fmt: skip
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    assert result.stdout.decode().startswith("Fix Receipt: L0 (run status: ENVIRONMENT_ERROR)")
    assert result.stderr.isascii()
    receipt = json.loads((out / "receipt.json").read_text("utf-8"))
    assert receipt["llm"]["calls"] == 0 and receipt["stages"][0]["name"] == "environment"


def test_require_strict_without_bubblewrap_exits_2_before_anything_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(pipeline, "probe", lambda: ("basic", "bubblewrap needs Linux (this is x)"))
    repo = make_repo(tmp_path / "repo", [{"m.py": "x = 1\n"}, {"m.py": "x = 2\n"}])
    out = tmp_path / "out"
    argv = ["verify", "--repo", str(repo), "--base", "c0", "--head", "c1", "--issue", "x",
            "--out", str(out), "--require-strict"]  # fmt: skip
    provider = FakeProvider([])
    assert main(argv, provider=provider) == 2
    err = capsys.readouterr().err
    assert err == ("tracefix verify: strict isolation is required, but this run would be basic: "
                   "bubblewrap needs Linux (this is x)\n")  # fmt: skip
    assert not out.exists() and provider.requests == []


def test_python_reaches_the_run_and_a_missing_one_is_an_environment_error(
    tmp_path: Path,
) -> None:
    """--python is a command-line setting only; a path that names nothing still gets a receipt
    (exit 0, ENVIRONMENT_ERROR), as an environment that can't run the tests does."""
    assert build_parser().parse_args(VERIFY_ARGS).python is None
    repo = make_repo(tmp_path / "repo", [{"m.py": "x = 1\n"}, {"m.py": "x = 2\n"}])
    out = tmp_path / "out"
    argv = ["verify", "--repo", str(repo), "--base", "c0", "--head", "c1", "--issue", "x",
            "--out", str(out), "--python", str(tmp_path / "nothing")]  # fmt: skip
    assert main(argv, provider=FakeProvider([])) == 0
    receipt = json.loads((out / "receipt.json").read_text("utf-8"))
    assert receipt["status"] == "ENVIRONMENT_ERROR"
    assert receipt["stages"][0]["reason"] == "the project's Python (--python) was not found"


def test_require_strict_is_off_by_default() -> None:
    assert build_parser().parse_args(VERIFY_ARGS).require_strict is False
    assert build_parser().parse_args([*VERIFY_ARGS, "--require-strict"]).require_strict is True


def test_a_crash_inside_tracefix_exits_3_with_the_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def crash(*_args: object) -> Verified:
        raise RuntimeError("boom \x1b[31mr\xe9d")

    monkeypatch.setattr(cli, "verify", crash)
    out = tmp_path / "out"
    assert main([*VERIFY_ARGS, "--out", str(out)], provider=FakeProvider([])) == 3
    captured = capsys.readouterr()
    lines = captured.err.splitlines()
    assert lines[0] == ("tracefix verify: internal error (a bug in Tracefix): "
                        "RuntimeError: boom ?[31mr\\xe9d")  # fmt: skip
    assert lines[1] == "Traceback (most recent call last):" and "in crash" in captured.err
    assert captured.err.isascii() and "\x1b" not in captured.err  # safe on any console or log
    assert captured.out == "" and not out.exists()


def test_an_unwritable_out_folder_exits_2_not_3(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A bad --out is a bad argument, not a bug in Tracefix."""
    verified = _verified(tmp_path)
    monkeypatch.setattr(cli, "verify", lambda *_args: verified)
    out = tmp_path / "a-file"
    out.write_text("not a folder\n")
    assert main([*VERIFY_ARGS, "--out", str(out)], provider=FakeProvider([])) == 2
    err = capsys.readouterr().err
    assert err.startswith(f"tracefix verify: can't write the receipt to {out}: ")
    assert "internal error" not in err and out.read_text() == "not a folder\n"


def test_a_previous_folder_without_a_receipt_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "verify", lambda *_args: pytest.fail("nothing may run"))
    for folder, says in ((tmp_path / "nowhere", "is not a folder"),
                         (tmp_path, "holds no receipt.json")):  # fmt: skip
        argv = [*VERIFY_ARGS, "--out", str(tmp_path / "out"), "--previous", str(folder)]
        assert main(argv, provider=FakeProvider([])) == 2
        assert capsys.readouterr().err == f"tracefix verify: --previous: {folder} {says}\n"


def test_the_previous_folder_is_read_before_the_new_receipt_replaces_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "out"
    write_out(out, _verified(tmp_path))  # finding 2
    seen: list[pipeline.Request] = []
    record = l4_run()
    plain = Verified(record, build(record, Workspace(tmp_path, "main", "fix")))

    def fake(request: pipeline.Request, *_args: object) -> Verified:
        seen.append(request)
        return plain

    monkeypatch.setattr(cli, "verify", fake)
    argv = [*VERIFY_ARGS, "--out", str(out), "--previous", str(out)]
    assert main(argv, provider=FakeProvider([])) == 0
    previous = seen[0].previous
    assert previous is not None and previous.problem == ""
    assert [(f.number, f.code) for f in previous.findings] == [(2, finding(2).repro_code)]
    assert not (out / "findings" / "finding_2.py").exists()  # the new receipt has no findings
    assert build_parser().parse_args(VERIFY_ARGS).previous is None
