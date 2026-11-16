"""M3.5: execution isolation. Malicious tests must be caught (basic) or blocked (strict).

Linux CI runs these with bubblewrap and TRACEFIX_REQUIRE_STRICT=1; Windows covers basic.
"""

import errno
import os
import re
import sys
import sysconfig
import tempfile
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import make_repo, old_python

from tracefix import interpreter, isolation
from tracefix.isolation import TamperingDetected, run_checked, watched_folders
from tracefix.runner import Outcome, run_pytest
from tracefix.sandbox import BASIC_WARNING, bwrap_prefix, sandbox_level
from tracefix.snapshots import content_snapshot
from tracefix.workspace import RunSettings, Workspace

LEVEL = sandbox_level()
strict_only = pytest.mark.skipif(LEVEL != "strict", reason="needs bubblewrap (Linux CI)")
basic_only = pytest.mark.skipif(LEVEL != "basic", reason="basic isolation only")
TEST_FILE = "tests/test_attack.py"


@pytest.fixture
def ws(tmp_path: Path) -> Iterator[Workspace]:
    files = {
        "pyproject.toml": '[tool.pytest.ini_options]\npythonpath = ["src"]\n',
        "src/pkg/__init__.py": "",
        "src/pkg/m.py": "def answer():\n    return 41\n",
        "tests/test_m.py": "def test_ok():\n    assert True\n",
    }
    repo = make_repo(
        tmp_path / "victim", [files, {"src/pkg/m.py": "def answer():\n    return 42\n"}]
    )
    with Workspace(repo, "c0", "c1") as workspace:
        yield workspace


def attack_run(
    ws: Workspace, body: str, tree: Path | None = None
) -> tuple[Outcome | None, TamperingDetected | None, str]:
    """Run a hostile test in a copy (default: head), watched: (outcome, tampering, pytest
    output). Outcome and output are empty when tampering was detected."""
    tree = tree or ws.head
    (tree / TEST_FILE).write_text(f"def test_attack():\n{body}", encoding="utf-8")
    try:
        result = run_checked(ws, tree, [TEST_FILE], [TEST_FILE], timeout_s=120, reruns=0)
    except TamperingDetected as exc:
        return None, exc, ""
    finally:
        (tree / TEST_FILE).unlink(missing_ok=True)
    return result.outcome, None, result.first.output


def attack(
    ws: Workspace, body: str, tree: Path | None = None
) -> tuple[Outcome | None, TamperingDetected | None]:
    outcome, tampering, _ = attack_run(ws, body, tree)
    return outcome, tampering


def write_body(target: Path) -> str:
    """A hostile test that writes `target` and reports exactly how the write went."""
    return (
        "    import pytest\n"
        "    try:\n"
        f"        open({target.as_posix()!r}, 'w').write('x')\n"
        "    except OSError as exc:\n"
        "        pytest.fail(f'WRITE BLOCKED errno={exc.errno}')\n"
    )


def strict_errno(target: Path, python: Path | None = None) -> int:
    """Why strict mode must block a write to `target`: hidden folders don't exist inside the
    sandbox (ENOENT); the interpreters (Tracefix's, and `python`'s venv) and everything else
    are read-only (EROFS)."""
    resolved = target.resolve()
    pythons = {Path(p).resolve() for p in (sys.prefix, sys.base_prefix)}
    if python is not None:
        pythons.add(python.parent.parent.resolve())
    if any(resolved.is_relative_to(d) for d in pythons):
        return errno.EROFS
    hidden = [Path("/tmp"), Path(tempfile.gettempdir()).resolve(), Path.home().resolve()]
    if any(resolved.is_relative_to(h) for h in hidden):
        return errno.ENOENT
    return errno.EROFS


def assert_caught_or_blocked(
    ws: Workspace, target: Path, label: str, tree: Path | None = None
) -> None:
    """Basic: the write happened and was detected by name. Strict: it was blocked, for the
    expected reason. Never passes because the write failed for some unrelated reason."""
    assert target.parent.is_dir(), f"precondition: {target.parent} must exist"
    outcome, tampering, output = attack_run(ws, write_body(target), tree)
    if LEVEL == "strict":
        assert tampering is None and outcome is Outcome.FAILED, output[-2000:]
        assert f"WRITE BLOCKED errno={strict_errno(target)}" in output, output[-2000:]
    else:
        assert tampering is not None, f"{label}: the write was not detected (output: {output})"
        assert label in str(tampering) and target.name in str(tampering)


def test_the_isolation_level_is_known_and_required_where_asked() -> None:
    from tracefix.sandbox import probe

    assert LEVEL in ("strict", "basic")
    if os.environ.get("TRACEFIX_REQUIRE_STRICT") == "1":
        assert LEVEL == "strict", f"strict isolation required but not working: {probe()[1]}"


def test_every_run_records_its_isolation_level(ws: Workspace) -> None:
    assert run_pytest(ws.head, timeout_s=120).isolation == LEVEL


def test_editing_the_other_copy_is_caught_or_impossible(ws: Workspace) -> None:
    before = content_snapshot(ws.base)
    assert_caught_or_blocked(ws, ws.base / "src" / "pkg" / "m.py", "the other copy")
    if LEVEL == "strict":
        assert content_snapshot(ws.base) == before


# --- extra copies (M4: Guard's variant of head) ---------------------------------------------------


def test_an_extra_copy_is_a_recorded_export_of_its_commit(ws: Workspace) -> None:
    extra = ws.add_copy(ws.head_sha)
    assert extra.name == "repo" and extra not in (ws.base, ws.head)
    assert ws.copies == [ws.base, ws.head, extra]
    assert content_snapshot(extra) == ws.pristine[extra] == ws.pristine[ws.head]
    ws.cleanup()
    assert not extra.exists()


def test_a_run_in_an_extra_copy_editing_head_is_caught_or_impossible(ws: Workspace) -> None:
    extra = ws.add_copy(ws.head_sha)
    before = content_snapshot(ws.head)
    assert_caught_or_blocked(ws, ws.head / "src" / "pkg" / "m.py", "the other copy", extra)
    if LEVEL == "strict":
        assert content_snapshot(ws.head) == before


def test_a_run_in_head_editing_an_extra_copy_is_caught_or_impossible(ws: Workspace) -> None:
    extra = ws.add_copy(ws.head_sha)
    before = content_snapshot(extra)
    assert_caught_or_blocked(ws, extra / "src" / "pkg" / "m.py", "the other copy")
    if LEVEL == "strict":
        assert content_snapshot(extra) == before


def test_drift_in_an_extra_copy_between_runs_is_caught(ws: Workspace) -> None:
    extra = ws.add_copy(ws.head_sha)
    (extra / "src" / "pkg" / "m.py").write_text("def answer():\n    return 0\n")
    with pytest.raises(TamperingDetected, match=re.escape("changed between runs: src/pkg/m.py")):
        run_checked(ws, ws.base, ["tests"], timeout_s=120, reruns=0)


def test_a_file_removed_for_a_run_is_expected_but_recreating_it_is_tampering(
    ws: Workspace,
) -> None:
    extra = ws.add_copy(ws.head_sha)
    module = "src/pkg/m.py"
    placed = [TEST_FILE, module]  # the test written, the module removed for this run
    (extra / module).unlink()
    (extra / TEST_FILE).write_text("def test_ok():\n    pass\n", encoding="utf-8")
    assert run_checked(ws, extra, [TEST_FILE], placed, timeout_s=120, reruns=0).outcome is (
        Outcome.PASSED
    )
    (extra / TEST_FILE).write_text(
        "def test_plant():\n    import pathlib\n"
        f"    pathlib.Path({module!r}).write_text('x = 1\\n')\n",
        encoding="utf-8",
    )
    with pytest.raises(TamperingDetected, match=module):
        run_checked(ws, extra, [TEST_FILE], placed, timeout_s=120, reruns=0)
    assert not (extra / module).exists()  # planted code is never kept


def test_a_placed_file_swapped_for_a_link_between_runs_is_tampering(
    ws: Workspace, tmp_path: Path
) -> None:
    # M4 verifier review (S5): Tracefix only ever places plain files, so a link there means a
    # process outside the run swapped it (e.g. one that escaped the kill in basic mode).
    extra = ws.add_copy(ws.head_sha)
    module = extra / "src" / "pkg" / "m.py"
    outside = tmp_path / "outside.py"
    outside.write_text("def answer():\n    return 41\n", encoding="utf-8")
    module.unlink()
    try:
        module.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"cannot make a symlink here: {exc}")
    problem = "placed file src/pkg/m.py is not a plain file"
    with pytest.raises(TamperingDetected, match=re.escape(problem)):
        run_checked(ws, extra, ["tests"], ["src/pkg/m.py"], timeout_s=120, reruns=0)
    assert outside.read_text(encoding="utf-8") == "def answer():\n    return 41\n"


def test_a_placed_file_too_large_to_hash_is_still_a_plain_file(ws: Workspace) -> None:
    # M4 verifier review, round 2 (N8): e.g. Guard reverting a data file over 64 MiB. A real
    # large file: lowering the cap instead would change every snapshot of the environment too.
    from tracefix.snapshots import HASH_CAP_BYTES

    extra = ws.add_copy(ws.head_sha)
    with (extra / "data.bin").open("wb") as f:
        f.truncate(HASH_CAP_BYTES + 1)
    result = run_checked(ws, extra, ["tests"], ["data.bin"], timeout_s=120, reruns=0)
    assert result.outcome is Outcome.PASSED


@strict_only
def test_strict_a_run_in_an_extra_copy_sees_no_other_copy(ws: Workspace) -> None:
    extra = ws.add_copy(ws.head_sha)
    body = (
        "    import pathlib\n"
        f"    for p in ({ws.base.as_posix()!r}, {ws.head.as_posix()!r}):\n"
        "        assert not pathlib.Path(p).exists()\n"
    )
    outcome, tampering = attack(ws, body, extra)
    assert tampering is None and outcome is Outcome.PASSED


# The plant is briefly real in the shared venv, where a parallel test's watch would see it too.
@pytest.mark.serial
def test_planting_a_startup_file_in_tracefixs_venv_is_caught_or_impossible(
    ws: Workspace,
) -> None:
    # purelib always exists (getsitepackages() also lists folders that don't, e.g. on Debian).
    purelib = Path(sysconfig.get_paths()["purelib"])
    target = purelib / f"zz_tracefix_attack_{uuid.uuid4().hex}.pth"
    try:
        assert_caught_or_blocked(ws, target, "Tracefix's environment")
        assert not target.exists()  # never left behind in the real venv
    finally:
        target.unlink(missing_ok=True)  # belt and braces: never pollute the venv


def old_ws(tmp_path: Path, python: Path) -> Workspace:
    files = {"src/pkg/__init__.py": "", "src/pkg/m.py": "def answer():\n    return 41\n",
             "tests/test_m.py": "def test_ok():\n    assert True\n"}  # fmt: skip
    fixed = {"src/pkg/m.py": "def answer():\n    return 42\n"}
    repo = make_repo(tmp_path / "victim", [files, fixed])
    found = interpreter.check(str(python), LEVEL).interpreter
    assert found is not None
    return Workspace(repo, "c0", "c1", RunSettings(python=found))


@pytest.mark.parametrize("version", ["3.9", "3.10"])
def test_the_project_s_python_runs_the_tests_at_this_level(tmp_path: Path, version: str) -> None:
    """M10 part 2: also at strict, where the project's venv and the uv Python it links to live
    under the hidden $HOME (scripts/check_linux.py installs uv's Pythons there)."""
    python = old_python(version)
    with old_ws(tmp_path, python) as ws:
        major, minor = map(int, version.split("."))
        body = f"    import sys\n    assert sys.version_info[:2] == ({major}, {minor})\n"
        outcome, tampering, output = attack_run(ws, body)
    assert tampering is None and outcome is Outcome.PASSED, output[-2000:]


# The plant is briefly real in the shared venv, where a parallel test's watch would see it too.
@pytest.mark.serial
def test_planting_a_startup_file_in_the_project_s_python_is_caught_or_impossible(
    tmp_path: Path,
) -> None:
    python = old_python("3.9")
    with old_ws(tmp_path, python) as ws:
        venv = python.parent.parent
        dirs = ws.settings.python.code_dirs
        purelib = next(d for d in dirs if d.name == "site-packages" and d.is_relative_to(venv))
        target = purelib / f"zz_tracefix_attack_{uuid.uuid4().hex}.pth"
        try:
            outcome, tampering, output = attack_run(ws, write_body(target))
            if LEVEL == "strict":
                assert tampering is None and outcome is Outcome.FAILED, output[-2000:]
                errno_ = strict_errno(target, python)
                assert f"WRITE BLOCKED errno={errno_}" in output, output[-2000:]
            else:
                assert tampering is not None, output
                assert "the project's Python environment" in str(tampering)
                assert target.name in str(tampering)
            assert not target.exists()  # never left behind in the project's venv
        finally:
            target.unlink(missing_ok=True)


def test_the_project_s_environment_is_watched_under_its_own_name(tmp_path: Path) -> None:
    python = old_python("3.9")
    with old_ws(tmp_path, python) as ws:
        labels = {f.root: f.label for f in watched_folders(ws)}
    venv = python.parent.parent.resolve()
    assert labels.get(venv) == "the project's Python environment"
    assert "Tracefix's environment" in labels.values()


def test_writing_into_the_users_repository_is_caught_or_impossible(ws: Workspace) -> None:
    target = ws.repo / f"escaped-{uuid.uuid4().hex}.txt"
    try:
        assert_caught_or_blocked(ws, target, "your repository")
        if LEVEL == "strict":
            assert not target.exists()
    finally:
        target.unlink(missing_ok=True)


@strict_only
def test_strict_home_and_other_temp_files_are_out_of_reach(ws: Workspace, tmp_path: Path) -> None:
    home_target = Path.home() / f".tracefix-escape-{uuid.uuid4().hex}"
    tmp_target = tmp_path / "escape.txt"
    body = (
        "    import pathlib\n"
        f"    for p in ({home_target.as_posix()!r}, {tmp_target.as_posix()!r}):\n"
        "        try:\n"
        "            pathlib.Path(p).write_text('x')\n"
        "        except OSError:\n"
        "            pass\n"
        f"    assert not pathlib.Path({ws.base.as_posix()!r}).exists()  # other copy hidden\n"
    )
    outcome, tampering = attack(ws, body)
    assert tampering is None and outcome is Outcome.PASSED
    assert not home_target.exists() and not tmp_target.exists()


def test_the_network_is_blocked_but_loopback_works(ws: Workspace) -> None:
    body = (
        "    import socket\n"
        "    import pytest\n"
        "    with pytest.raises(OSError):\n"
        "        socket.create_connection(('example.com', 80), timeout=5)\n"
        "    server = socket.socket()\n"
        "    server.bind(('127.0.0.1', 0))\n"
        "    server.listen(1)\n"
        "    client = socket.create_connection(server.getsockname(), timeout=5)\n"
        "    client.close()\n"
        "    server.close()\n"
    )
    outcome, tampering = attack(ws, body)
    assert tampering is None and outcome is Outcome.PASSED


def test_runs_see_a_private_home_and_temp_folder(ws: Workspace) -> None:
    real_home = Path.home().as_posix()
    body = (
        "    import os, tempfile, pathlib\n"
        f"    assert pathlib.Path.home().as_posix() != {real_home!r}\n"
        "    assert 'tracefix-run-' in tempfile.gettempdir()\n"
        "    assert 'tracefix-run-' in os.environ['HOME']\n"
    )
    outcome, tampering = attack(ws, body)
    assert tampering is None and outcome is Outcome.PASSED


def test_leftover_data_files_are_removed_not_blamed(ws: Workspace) -> None:
    before = content_snapshot(ws.head)
    (ws.head / TEST_FILE).write_text(
        "def test_log():\n    open('debug.log', 'w').write('x')\n", encoding="utf-8"
    )
    result = run_checked(ws, ws.head, [TEST_FILE], [TEST_FILE], timeout_s=120, reruns=0)
    (ws.head / TEST_FILE).unlink()
    assert result.outcome is Outcome.PASSED
    assert content_snapshot(ws.head) == before


def test_a_run_whose_report_disagrees_with_its_exit_code_is_an_error(ws: Workspace) -> None:
    # The forged-report trick: exit 0 without pytest writing a report.
    outcome, tampering = attack(ws, "    import os\n    os._exit(0)\n")
    assert tampering is None and outcome is Outcome.ERROR


def test_bwrap_command_hides_and_binds_the_right_folders(tmp_path: Path) -> None:
    copy, scratch = tmp_path / "repo", tmp_path / "scratch"
    args = bwrap_prefix([copy, scratch])
    joined = " ".join(args)
    assert args[0] == "bwrap" and "--unshare-all" in args and "--die-with-parent" in args
    assert "--ro-bind / /" in joined and "--tmpfs /tmp" in joined
    assert f"--bind {copy} {copy}" in joined and f"--bind {scratch} {scratch}" in joined
    for folder in {Path(sys.prefix).resolve(), Path(sys.base_prefix).resolve()}:
        assert f"--ro-bind {folder} {folder}" in joined
    # writable binds come last, so nothing re-hides them
    assert joined.rindex("--bind") > joined.rindex("--tmpfs")


def test_watched_folders_cover_the_interpreter_tracefix_and_the_repo(ws: Workspace) -> None:
    import tracefix

    roots = [f.root for f in watched_folders(ws)]
    for needed in (Path(sys.prefix), Path(tracefix.__file__).parent, ws.repo, ws.base.parent):
        assert any(needed.resolve().is_relative_to(r) for r in roots), needed


@basic_only
def test_basic_results_carry_the_warning(ws: Workspace) -> None:
    from tracefix.diffscope import compute_scope
    from tracefix.llm import FakeProvider, LLMClient
    from tracefix.repro import reproduce

    one_answer = FakeProvider([{"test_code": "def test_x():\n    pass\n", "rationale": ""}])
    client = LLMClient(one_answer, max_calls=1)
    result = reproduce(ws, compute_scope(ws.repo, ws.base_sha, ws.head_sha), "issue", client)
    assert result.isolation == "basic" and result.warnings == (BASIC_WARNING,)


def test_a_leftover_that_cannot_be_removed_is_reported_not_raised(
    ws: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    import tracefix.isolation as isolation

    def locked(self: Path, missing_ok: bool = False) -> None:
        raise PermissionError(13, "Access is denied")

    (ws.head / TEST_FILE).write_text(
        "def test_log():\n    open('debug.log', 'w').write('x')\n", encoding="utf-8"
    )
    monkeypatch.setattr(isolation.Path, "unlink", locked)
    with pytest.raises(TamperingDetected, match="could not remove"):
        run_checked(ws, ws.head, [TEST_FILE], [TEST_FILE], timeout_s=120, reruns=0)


def test_an_unreadable_file_still_has_a_snapshot_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import tracefix.snapshots as snapshots

    (tmp_path / "locked.bin").write_bytes(b"x")

    def denied(path: str) -> str:
        raise PermissionError(13, "denied")

    monkeypatch.setattr(snapshots, "_digest", denied)
    snap = content_snapshot(tmp_path)
    assert snap["locked.bin"][0] == "file" and "unreadable" in snap["locked.bin"][-1]


# --- regressions from the M3.5 verifier review --------------------------------------------------


def test_b1_a_change_between_runs_is_caught_at_the_next_run(ws: Workspace) -> None:
    # Stands in for a process that outlived a base run and edits head afterwards.
    run_checked(ws, ws.base, ["tests"], timeout_s=120, reruns=0)
    (ws.head / "src" / "pkg" / "m.py").write_text("def answer():\n    return 0\n")
    (ws.head / TEST_FILE).write_text("def test_ok():\n    pass\n", encoding="utf-8")
    with pytest.raises(TamperingDetected, match=re.escape("changed between runs: src/pkg/m.py")):
        run_checked(ws, ws.head, [TEST_FILE], [TEST_FILE], timeout_s=120, reruns=0)


def test_b2_config_planted_above_a_copy_is_never_read(ws: Workspace) -> None:
    # A copy with no pytest config of its own: pytest must not look in parent folders.
    (ws.head / "pyproject.toml").unlink()
    ws.pristine[ws.head].pop("pyproject.toml")
    parent = ws.head.parent
    (parent / "pytest.ini").write_text("[pytest]\naddopts = -p no:python\n", encoding="utf-8")
    (parent / "conftest.py").write_text(
        "def pytest_collection_modifyitems(items):\n    raise SystemExit(3)\n", encoding="utf-8"
    )
    outcome, tampering = attack(ws, "    assert True\n")
    assert tampering is None and outcome is Outcome.PASSED


def test_b2_planting_config_above_the_copy_is_caught_or_impossible(ws: Workspace) -> None:
    target = ws.head.parent / "conftest.py"
    assert target.parent.is_dir()
    outcome, tampering, output = attack_run(ws, write_body(target))
    if LEVEL == "strict":
        # The parent exists only as an empty in-sandbox mount point: the write lands there and
        # vanishes with the sandbox, never reaching the real folder.
        assert tampering is None and outcome is Outcome.PASSED, output[-2000:]
        assert not target.exists()
    else:
        assert tampering is not None and "a folder around the copies" in str(tampering)
        assert "conftest.py" in str(tampering)


def test_s1_git_bookkeeping_is_ignored_but_hooks_are_watched(ws: Workspace) -> None:
    logs = ws.repo / ".git" / "logs" / f"noise-{uuid.uuid4().hex}"
    hook = ws.repo / ".git" / "hooks" / "pre-commit"
    hook.parent.mkdir(exist_ok=True)  # fixture repos are made with an empty template
    try:
        outcome, tampering = attack(ws, f"    open({logs.as_posix()!r}, 'w').write('x')\n")
        if LEVEL == "basic":
            assert tampering is None and outcome is Outcome.PASSED
        outcome, tampering = attack(ws, f"    open({hook.as_posix()!r}, 'w').write('x')\n")
        if LEVEL == "basic":
            assert tampering is not None and "pre-commit" in str(tampering)
    finally:
        logs.unlink(missing_ok=True)
        hook.unlink(missing_ok=True)


def test_a_system_python_is_watched_by_its_own_folders_not_all_of_usr() -> None:
    # The live M9 run: a venv on the runner's /usr/bin/python3 made every run walk /usr (minutes).
    venv = Path("/home/runner/work/demo/.venv")
    stdlib, dynload = Path("/usr/lib/python3.12"), Path("/usr/lib/python3.12/lib-dynload")
    local = Path("/usr/local/lib/python3.12/dist-packages")
    python_dirs = [stdlib, dynload, local, venv / "lib/python3.12/site-packages",
                   Path("/home/runner/work/demo"), Path("/usr")]  # fmt: skip
    roots = isolation.interpreter_roots([venv, Path("/usr")], python_dirs)
    assert roots == {venv, stdlib, dynload, local}
    # Not a venv (the Action's --system install): the same, without a venv.
    assert isolation.interpreter_roots([Path("/usr"), Path("/usr")], python_dirs) == {
        stdlib, dynload, local,
    }  # fmt: skip


def test_a_dedicated_python_install_is_watched_whole() -> None:
    venv, base = Path("/w/.venv"), Path("/opt/hostedtoolcache/Python/3.12.3/x64")
    roots = isolation.interpreter_roots([venv, base], [base / "lib/python3.12", Path("/w")])
    assert roots == {venv, base}


def test_s1_only_startup_files_are_watched_in_the_shared_interpreter(ws: Workspace) -> None:
    base = Path(sys.base_prefix).resolve()
    if base == Path(sys.prefix).resolve():
        pytest.skip("no separate venv")
    # The folder that watches the base install's stdlib: the base prefix itself, or, for a
    # system Python in a shared prefix such as /usr/local, Python's own folder there.
    base_vars = {"base": sys.base_prefix, "platbase": sys.base_exec_prefix}
    stdlib = Path(sysconfig.get_paths(vars=base_vars)["stdlib"]).resolve()
    shared = [f for f in watched_folders(ws)
              if f.root.is_relative_to(base) and stdlib.is_relative_to(f.root)]  # fmt: skip
    assert shared and not shared[0].keep_file("Lib/__pycache__/x.cpython-311.pyc")
    assert shared[0].keep_file("Lib/site-packages/evil.pth")
    assert shared[0].keep_file("Lib/sitecustomize.py")


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="POSIX only")
def test_s2_a_fifo_in_the_copy_does_not_hang_tracefix(ws: Workspace) -> None:
    outcome, tampering = attack(ws, "    import os\n    os.mkfifo('pipe')\n")
    assert tampering is None and outcome is Outcome.PASSED  # removed as a leftover
    assert not (ws.head / "pipe").exists()


def test_s2_a_read_only_leftover_is_removed(ws: Workspace) -> None:
    body = (
        "    import os, stat\n"
        "    open('ro.log', 'w').write('x')\n"
        "    os.chmod('ro.log', stat.S_IREAD)\n"
    )
    outcome, tampering = attack(ws, body)
    assert tampering is None and outcome is Outcome.PASSED
    assert not (ws.head / "ro.log").exists()


def test_s3_udp_and_name_lookups_are_blocked(ws: Workspace) -> None:
    body = (
        "    import socket\n"
        "    import pytest\n"
        "    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)\n"
        "    with pytest.raises(OSError):\n"
        "        udp.sendto(b'x', ('192.0.2.1', 53))\n"
        "    udp.close()\n"
        "    with pytest.raises(OSError):\n"
        "        socket.gethostbyname('example.com')\n"
    )
    outcome, tampering = attack(ws, body)
    assert tampering is None and outcome is Outcome.PASSED


def test_the_bytecode_flag_is_restored_after_a_watch(ws: Workspace) -> None:
    before = sys.dont_write_bytecode
    attack(ws, "    assert True\n")
    assert sys.dont_write_bytecode == before


# --- regressions from the second M3.5 verifier pass ---------------------------------------------


def test_same_size_edit_with_restored_mtime_is_caught_by_content(
    ws: Workspace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Stand-in for an interpreter folder: the edit keeps the size and sets the mtime back, which
    # Windows metadata cannot see. Interpreter sources there are watched by content.
    import tracefix.isolation as isolation

    fake = tmp_path / "site-packages"
    fake.mkdir()
    module = fake / "victim_mod.py"
    module.write_text("X = 1\n", encoding="utf-8")
    real = isolation.watched_folders
    watched = isolation.Watched("Tracefix's environment", fake, by_content=True)
    monkeypatch.setattr(isolation, "watched_folders", lambda w: [*real(w), watched])
    body = (
        "    import os\n"
        f"    p = {module.as_posix()!r}\n"
        "    st = os.stat(p)\n"
        "    open(p, 'w').write('X = 2\\n')\n"
        "    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns))\n"
    )
    outcome, tampering, output = attack_run(ws, body)
    if LEVEL == "strict":
        # The stand-in folder lives under /tmp, hidden in the sandbox: the edit cannot happen.
        assert tampering is None and outcome is Outcome.FAILED, output[-2000:]
        assert "FileNotFoundError" in output
        assert module.read_text(encoding="utf-8") == "X = 1\n"
    else:
        assert tampering is not None and "victim_mod.py" in str(tampering)


def test_runs_and_tracefix_never_load_pyc_files_from_shared_pycache_folders(ws: Workspace) -> None:
    body = (
        "    import sys\n    assert sys.pycache_prefix and 'tracefix-run-' in sys.pycache_prefix\n"
    )
    outcome, tampering = attack(ws, body)
    assert tampering is None and outcome is Outcome.PASSED
    assert sys.pycache_prefix and "tracefix-pycache-" in sys.pycache_prefix


def test_config_next_to_the_tests_is_used_but_never_above_the_copy(tmp_path: Path) -> None:
    files = {
        "src/pkg/__init__.py": "",
        "src/pkg/m.py": "X = 1\n",
        "tests/pytest.ini": "[pytest]\npythonpath = ../src\n",
        "tests/test_m.py": "from pkg.m import X\n\ndef test_x():\n    assert X == 1\n",
    }
    repo = make_repo(tmp_path / "nested", [files])
    with Workspace(repo, "c0", "c0") as workspace:
        result = run_pytest(workspace.head, ["tests/test_m.py"], timeout_s=120, reruns=0)
    assert result.outcome is Outcome.PASSED, result.first.output[-2000:]


def test_the_environment_check_is_watched_and_leaves_no_leftovers(tmp_path: Path) -> None:
    from tracefix.isolation import check_environment
    from tracefix.runner import EnvStatus

    files = {
        "pyproject.toml": '[tool.pytest.ini_options]\npythonpath = ["src"]\n',
        "src/pkg/__init__.py": "",
        "tests/test_log.py": "def test_log():\n    open('suite.log', 'w').write('x')\n",
    }
    repo = make_repo(tmp_path / "suite", [files])
    with Workspace(repo, "c0", "c0") as workspace:
        check = check_environment(workspace, timeout_s=120)
        assert check.status is EnvStatus.OK
        assert content_snapshot(workspace.base) == workspace.pristine[workspace.base]


def test_a_detected_and_removed_planted_file_does_not_haunt_the_next_run(
    ws: Workspace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Regression: the cached content snapshot was taken before the planted file was deleted, so
    # the next, innocent run reported tampering.
    import tracefix.isolation as isolation

    fake = tmp_path / "site-packages"
    fake.mkdir()
    real = isolation.watched_folders
    watched = isolation.Watched("Tracefix's environment", fake, by_content=True)
    monkeypatch.setattr(isolation, "watched_folders", lambda w: [*real(w), watched])
    planted = (fake / "zz_planted.pth").as_posix()
    outcome, tampering, output = attack_run(ws, f"    open({planted!r}, 'w').write('')\n")
    if LEVEL == "strict":
        # The stand-in folder is under /tmp, hidden in the sandbox: nothing can be planted.
        assert tampering is None and outcome is Outcome.FAILED, output[-2000:]
        assert "FileNotFoundError" in output
    else:
        assert tampering is not None
    assert not Path(planted).exists()
    outcome, tampering = attack(ws, "    assert True\n")
    assert tampering is None and outcome is Outcome.PASSED


def test_the_sandbox_keeps_every_interpreter_path_visible(tmp_path: Path) -> None:
    # CI regression: uv links the venv's python through a version-alias folder under $HOME; with
    # only resolved paths re-bound, bwrap could not exec the venv's python.
    from tracefix.sandbox import _install_root, _interpreter_dirs

    assert _install_root(Path("/opt/py/cpython-3.11/bin/python3")) == Path("/opt/py/cpython-3.11")
    assert _install_root(Path("C:/py/cpython-3.11/python.exe")) == Path("C:/py/cpython-3.11")
    dirs = _interpreter_dirs()
    for needed in (sys.prefix, sys.base_prefix):
        assert Path(needed) in dirs and Path(needed).resolve() in dirs
    args = " ".join(bwrap_prefix([tmp_path]))
    for folder in dirs:
        assert f"--ro-bind {folder} {folder}" in args


def test_the_sandbox_also_shows_the_project_s_python_and_the_install_it_links_to(
    tmp_path: Path,
) -> None:
    from tracefix.sandbox import _interpreter_dirs, executable_dirs

    base = tmp_path / "uv" / "cpython-3.9"
    (base / "bin").mkdir(parents=True)
    venv = tmp_path / "proj" / ".venv"
    (venv / "bin").mkdir(parents=True)
    (venv / "bin" / "python").write_text("")
    (venv / "pyvenv.cfg").write_text(f"home = {base / 'bin'}\nversion = 3.9.25\n")
    assert {venv, base} <= executable_dirs(venv / "bin" / "python")
    assert {venv, base} <= set(_interpreter_dirs(venv / "bin" / "python"))
    assert venv not in _interpreter_dirs()
    args = " ".join(bwrap_prefix([tmp_path], venv / "bin" / "python"))
    assert f"--ro-bind {venv} {venv}" in args and f"--ro-bind {base} {base}" in args


def test_a_version_alias_link_outside_the_hidden_folders_is_not_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Slice 2's prepare (21 Oct 2026): Tracefix's own uv Python lived under /opt, where uv's
    alias cpython-3.11 is an absolute symlink to cpython-3.11.16. Binding the alias onto itself
    made bubblewrap fail ("Can't bind mount ...: No such file or directory"), so every run fell
    back to basic. Outside the hidden folders it is visible through "/" already, so only its
    target is bound; under a hidden folder (CI's $HOME) the alias is still bound, as before."""
    from tracefix import sandbox

    real = tmp_path / "opt" / "cpython-3.11.16"
    real.mkdir(parents=True)
    alias = tmp_path / "opt" / "cpython-3.11"
    try:
        alias.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("this account can't make symlinks (Windows without Developer Mode)")
    monkeypatch.setattr(sandbox, "_interpreter_dirs", lambda executable=None: [alias, real])
    # pytest's tmp_path is itself under /tmp on Linux: the hidden folders are named apart.
    elsewhere = tmp_path / "elsewhere"
    monkeypatch.setattr(sandbox, "_hidden", lambda: [elsewhere / "tmp", elsewhere / "home"])
    args = " ".join(bwrap_prefix([tmp_path / "work"]))
    assert f"--ro-bind {alias} {alias}" not in args
    assert f"--ro-bind {real} {real}" in args
    monkeypatch.setattr(sandbox, "_hidden", lambda: [elsewhere, tmp_path / "opt"])  # $HOME
    args = " ".join(bwrap_prefix([tmp_path / "work"]))
    assert f"--ro-bind {alias} {alias}" in args and f"--ro-bind {real} {real}" in args


def test_symlink_hops_follow_the_whole_chain(tmp_path: Path) -> None:
    from tracefix.sandbox import _symlink_hops

    real = tmp_path / "real-python"
    real.write_text("")
    link = tmp_path / "alias"
    try:
        link.symlink_to(real)
    except OSError:
        pytest.skip("creating symlinks needs extra rights on this machine")
    assert _symlink_hops(link) == [link, real]
