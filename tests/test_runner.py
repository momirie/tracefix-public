"""M2: the pytest runner and the environment check."""

import json
import shutil
import time
from pathlib import Path

import make_fixtures
import pytest
from conftest import old_python, write_files

from tracefix.runner import (
    BOOTSTRAP,
    OUT_LIMIT,
    EnvStatus,
    JUnitDetails,
    Outcome,
    Probe,
    check_environment,
    failed_tests,
    junit_details,
    outcome_for,
    run_pytest,
)
from tracefix.sandbox import write_module
from tracefix.workspace import Workspace

CASES = sorted(make_fixtures.CASES)
EXPECT = {"pass": Outcome.PASSED, "fail": Outcome.FAILED, "error": Outcome.ERROR}


def suite_expectations(case: str) -> dict[str, Outcome]:
    data = json.loads((make_fixtures.FIXTURES_DIR / case / "expected.json").read_text("utf-8"))
    return {c["ref"]: EXPECT[c["expect"]] for c in data["checks"] if c["tests"] == "suite"}


# --- fixtures through real worktrees ---------------------------------------------------------


@pytest.mark.parametrize("case", CASES)
def test_suite_outcome_matches_expected_json(case: str, built: dict[str, Path]) -> None:
    expected = suite_expectations(case)
    assert set(expected) == {"base", "head"}
    with Workspace(built[case], "base", "head") as ws:
        for ref, tree in (("base", ws.base), ("head", ws.head)):
            result = run_pytest(tree, timeout_s=120)
            assert result.outcome is expected[ref], f"{case}@{ref}\n{result.first.output[-3000:]}"


@pytest.mark.parametrize("case", CASES)
def test_environment_check(case: str, built: dict[str, Path]) -> None:
    with Workspace(built[case], "base", "head") as ws:
        check = check_environment(ws.base, timeout_s=120)
    if case == "env_broken":
        assert check.status is EnvStatus.ENVIRONMENT_ERROR
        assert check.error == "ModuleNotFoundError"
        assert check.module == "acme_metrics"
        assert "acme_metrics" in check.reason
    else:
        assert check.status is EnvStatus.OK, check.reason


def test_oracle_repro_fails_consistently_on_base_and_passes_on_head(
    built: dict[str, Path],
) -> None:
    oracle = make_fixtures.FIXTURES_DIR / "partial_fix" / "oracle" / "test_repro.py"
    with Workspace(built["partial_fix"], "base", "head") as ws:
        for tree in (ws.base, ws.head):
            shutil.copyfile(oracle, tree / "test_oracle_repro.py")
        base = run_pytest(ws.base, ["test_oracle_repro.py"], timeout_s=120, reruns=2)
        head = run_pytest(ws.head, ["test_oracle_repro.py"], timeout_s=120, reruns=2)
    assert base.outcome is Outcome.FAILED
    assert len(base.attempts) == 3  # first run + 2 reruns, all failing the same tests
    assert base.first.failed and all(a.failed == base.first.failed for a in base.attempts)
    assert head.outcome is Outcome.PASSED and len(head.attempts) == 1


def test_runs_leave_no_files_in_the_worktree(built: dict[str, Path]) -> None:
    # M3.5: copies have no .git, so compare full content snapshots instead of `git status`.
    from tracefix.snapshots import content_snapshot

    with Workspace(built["good_fix"], "base", "head") as ws:
        before = content_snapshot(ws.head)
        run_pytest(ws.head, timeout_s=120)
        after = content_snapshot(ws.head)
    assert after == before


# --- small synthetic projects -----------------------------------------------------------------


def test_pass_fail_and_no_tests(tmp_path: Path) -> None:
    ok = write_files(tmp_path / "ok", {"test_a.py": "def test_a():\n    assert True\n"})
    bad = write_files(tmp_path / "bad", {"test_b.py": "def test_b():\n    assert 1 == 2\n"})
    empty = write_files(tmp_path / "empty", {"README.md": "no tests\n"})
    assert run_pytest(ok).outcome is Outcome.PASSED
    failed = run_pytest(bad, reruns=1)
    assert failed.outcome is Outcome.FAILED
    assert failed.first.exit_code == 1
    assert failed.first.failed == ("test_b::test_b",)
    assert "assert 1 == 2" in failed.first.output
    assert run_pytest(empty).outcome is Outcome.NO_TESTS


def test_collection_error_is_error_and_not_rerun(tmp_path: Path) -> None:
    tree = write_files(tmp_path, {"test_x.py": "import not_a_real_module_xyz\n"})
    result = run_pytest(tree)
    assert result.outcome is Outcome.ERROR
    assert len(result.attempts) == 1


FLAKY_TEST = """\
from pathlib import Path


def test_flaky():
    counter = Path(__file__).with_name("count.txt")
    n = int(counter.read_text()) if counter.exists() else 0
    counter.write_text(str(n + 1))
    assert n >= 1
"""


def test_flaky_test_is_detected_by_rerun(tmp_path: Path) -> None:
    result = run_pytest(write_files(tmp_path, {"test_flaky.py": FLAKY_TEST}))
    assert result.outcome is Outcome.FLAKY
    assert [a.exit_code for a in result.attempts] == [1, 0]


# Generous on purpose: the heartbeat catches a survivor however long the processes take to start
# (a 3 s budget failed on a busy machine, NOTES).
TREE_TIMEOUT_S = 10


def heartbeat(marker: Path) -> str:
    """Code for a process that marks its start, then appends to `marker` every 0.1 s until killed.
    A survivor keeps the file growing, so no timing guess decides the test."""
    m = str(marker)
    return (
        f"import time\nopen({m!r} + '.started', 'w').close()\n"
        f"while True:\n    with open({m!r}, 'a') as f:\n        f.write('.')\n    time.sleep(0.1)\n"
    )


def assert_killed(marker: Path) -> None:
    assert Path(f"{marker}.started").exists(), "the child never started"
    time.sleep(0.5)  # let a write that was in flight at the kill land

    def size() -> int:
        return marker.stat().st_size if marker.exists() else 0

    before = size()
    time.sleep(2)  # a survivor writes ~20 more times in this window
    assert size() == before, "a process survived the kill"


HANGING_TEST = """\
import subprocess
import sys
import time


def test_hangs():
    subprocess.Popen([sys.executable, "-c", {code!r}])
    time.sleep(60)
"""


def test_timeout_kills_the_whole_process_tree(tmp_path: Path) -> None:
    marker = (
        tmp_path / "proj" / "grandchild-heartbeat"
    )  # M3.5: in the run folder, writable when sandboxed
    test = HANGING_TEST.format(code=heartbeat(marker))
    tree = write_files(tmp_path / "proj", {"test_hang.py": test})
    start = time.monotonic()
    result = run_pytest(tree, timeout_s=TREE_TIMEOUT_S)
    assert result.outcome is Outcome.TIMEOUT
    assert result.first.exit_code is None
    assert time.monotonic() - start < TREE_TIMEOUT_S + 17  # same slack as with the old 3 s / 20 s
    assert_killed(marker)


ENV_TEST = """\
import os


def test_env():
    assert "ANTHROPIC_API_KEY" not in os.environ
    assert "TRACEFIX_TEST_SECRET" not in os.environ
    assert "PATH" in os.environ
"""


def test_environment_is_allowlisted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-not-leak")
    monkeypatch.setenv("TRACEFIX_TEST_SECRET", "nope")
    monkeypatch.setenv("PYTEST_ADDOPTS", "--this-flag-does-not-exist")
    assert run_pytest(write_files(tmp_path, {"test_env.py": ENV_TEST})).outcome is Outcome.PASSED


def test_stdin_is_closed(tmp_path: Path) -> None:
    test = "import sys\n\n\ndef test_stdin():\n    assert sys.stdin.read() == ''\n"
    result = run_pytest(write_files(tmp_path, {"test_in.py": test}), ["-s"], timeout_s=30)
    assert result.outcome is Outcome.PASSED, result.first.output


def test_environment_check_on_syntax_error_and_failures(tmp_path: Path) -> None:
    broken = write_files(tmp_path / "broken", {"test_s.py": "def test_s(:\n    pass\n"})
    failing = write_files(tmp_path / "failing", {"test_f.py": "def test_f():\n    assert 0\n"})
    check = check_environment(broken)
    assert check.status is EnvStatus.ENVIRONMENT_ERROR
    assert check.module is None
    # Failing tests on base are expected (that is the bug); they are not an environment problem.
    assert check_environment(failing).status is EnvStatus.OK


def test_environment_check_timeout(tmp_path: Path) -> None:
    slow = "import time\n\n\ndef test_s():\n    time.sleep(30)\n"
    check = check_environment(write_files(tmp_path, {"test_slow.py": slow}), timeout_s=2)
    assert check.status is EnvStatus.ENVIRONMENT_ERROR
    assert check.error == "Timeout"


def test_outcome_mapping() -> None:
    assert outcome_for(0) is Outcome.PASSED
    assert outcome_for(1) is Outcome.FAILED
    assert outcome_for(5) is Outcome.NO_TESTS
    assert outcome_for(None) is Outcome.TIMEOUT
    for code in (2, 3, 4, -9, 137):
        assert outcome_for(code) is Outcome.ERROR


def test_unreadable_junit_report_gives_no_failed_ids(tmp_path: Path) -> None:
    assert failed_tests(tmp_path / "missing.xml") == ()
    (tmp_path / "bad.xml").write_text("<testsuites><testcase")
    assert failed_tests(tmp_path / "bad.xml") == ()


def test_a_junit_report_declaring_entities_is_unreadable(tmp_path: Path) -> None:
    # The report is written inside the process under test, so it is untrusted XML (bandit B314):
    # entity declarations (the base of "billion laughs" and external-entity tricks) are refused.
    report = tmp_path / "report.xml"
    report.write_text(
        '<?xml version="1.0"?>\n<!DOCTYPE t [<!ENTITY e "x">]>\n'
        '<testsuites><testsuite><testcase classname="t" name="a&e;"><failure message="m"/>'
        "</testcase></testsuite></testsuites>\n",
        encoding="utf-8",
    )
    assert failed_tests(report) == ()
    assert not junit_details(report).readable


# --- regressions from the M2 verifier review --------------------------------------------------


def test_repo_file_named_pytest_cannot_replace_the_runner(tmp_path: Path) -> None:
    fake = "import sys\nprint('1 passed')\nsys.exit(0)\n"
    tree = write_files(
        tmp_path, {"pytest.py": fake, "test_bug.py": "def test_bug():\n    assert 1 == 2\n"}
    )
    result = run_pytest(tree, reruns=0)
    assert result.outcome is Outcome.FAILED
    assert "assert 1 == 2" in result.first.output


@pytest.mark.parametrize("version", ["3.9", "3.10"])
def test_without_dash_p_a_repo_file_named_pytest_still_cannot_replace_the_runner(
    tmp_path: Path, version: str
) -> None:
    """3.9 and 3.10 have no -P: pytest starts through BOOTSTRAP, which takes the copy off
    sys.path first."""
    fake = "import sys\nprint('1 passed')\nsys.exit(0)\n"
    tree = write_files(
        tmp_path, {"pytest.py": fake, "test_bug.py": "def test_bug():\n    assert 1 == 2\n"}
    )
    result = run_pytest(tree, reruns=0, python=str(old_python(version)), safe_path=False)
    assert result.command[1:3] == ("-c", BOOTSTRAP)
    assert result.outcome is Outcome.FAILED
    assert "assert 1 == 2" in result.first.output


LEFTOVER_HOLDS_OUTPUT = """\
import subprocess
import sys


def test_starts_background_child():
    print("visible output")
    subprocess.Popen([sys.executable, "-c", "import time; time.sleep(25)"])
"""


def test_child_holding_the_output_does_not_turn_a_pass_into_a_timeout(tmp_path: Path) -> None:
    tree = write_files(tmp_path, {"test_bg.py": LEFTOVER_HOLDS_OUTPUT})
    start = time.monotonic()
    result = run_pytest(tree, ["-s"], timeout_s=15)
    assert result.outcome is Outcome.PASSED
    assert result.first.exit_code == 0
    assert "visible output" in result.first.output
    assert time.monotonic() - start < 15


BACKGROUND_CHILD = """\
import subprocess
import sys

MARKER = {marker!r}


def test_leaves_a_child_behind():
    code = (
        f"open({{MARKER!r}} + '.started', 'w').close(); "
        f"import time; time.sleep(4); open({{MARKER!r}}, 'w').close()"
    )
    subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.DEVNULL)
    # M3.5: wait until the child is really running, so the test never races Python's start-up
    # (slower now that runs read no cached bytecode); it must still be alive when pytest exits.
    import os
    import time
    deadline = time.monotonic() + 10
    while not os.path.exists(MARKER + ".started") and time.monotonic() < deadline:
        time.sleep(0.05)
"""


def test_children_left_after_a_normal_exit_are_killed(tmp_path: Path) -> None:
    marker = tmp_path / "p" / "child-survived"  # M3.5: in the run folder, writable when sandboxed
    tree = write_files(tmp_path / "p", {"test_bg.py": BACKGROUND_CHILD.format(marker=str(marker))})
    assert run_pytest(tree).outcome is Outcome.PASSED
    time.sleep(6)
    assert Path(f"{marker}.started").exists(), "the child never started"
    assert not marker.exists()


ORPHANED_GRANDCHILD = """\
import subprocess
import sys
import time

GRANDCHILD = {code!r}


def test_middle_process_exits_then_hang():
    middle = f"import subprocess, sys; subprocess.Popen([sys.executable, '-c', {{GRANDCHILD!r}}])"
    subprocess.run([sys.executable, "-c", middle], check=True)
    time.sleep(60)
"""


def test_timeout_kills_grandchildren_whose_parent_already_exited(tmp_path: Path) -> None:
    marker = (
        tmp_path / "p" / "grandchild-heartbeat"
    )  # M3.5: in the run folder, writable when sandboxed
    test = ORPHANED_GRANDCHILD.format(code=heartbeat(marker))
    tree = write_files(tmp_path / "p", {"test_orphan.py": test})
    assert run_pytest(tree, timeout_s=TREE_TIMEOUT_S).outcome is Outcome.TIMEOUT
    assert_killed(marker)


# --- M3: failure details for signatures ---------------------------------------------------------


def test_junit_details_give_type_location_and_counts(tmp_path: Path) -> None:
    tree = write_files(
        tmp_path,
        {
            "pkg/test_mix.py": (
                "import pytest\n\n"
                "def test_assert():\n    assert 1 == 2\n\n"
                "def test_raise():\n    {}['k']\n\n"
                "@pytest.fixture\ndef broken():\n    raise RuntimeError('setup')\n\n"
                "def test_setup(broken):\n    pass\n\n"
                "@pytest.mark.skip\ndef test_skipped():\n    pass\n\n"
                "def test_ok():\n    pass\n"
            )
        },
    )
    result = run_pytest(tree, reruns=0, timeout_s=120)
    attempt = result.first
    assert (attempt.tests, attempt.skipped) == (5, 1)
    assert [t.rsplit("::", 1)[1] for t in attempt.passed] == ["test_ok"]  # not skipped, not failed
    by_name = {f.test.rsplit("::", 1)[1]: f for f in attempt.failures}
    assert set(by_name) == {"test_assert", "test_raise", "test_setup"}
    assert (by_name["test_assert"].kind, by_name["test_assert"].exc_type) == (
        "failure",
        "AssertionError",
    )
    assert by_name["test_assert"].location == "pkg/test_mix.py:4"
    assert (by_name["test_raise"].exc_type, by_name["test_raise"].location) == (
        "KeyError",
        "pkg/test_mix.py:7",
    )
    assert by_name["test_setup"].kind == "error"
    assert by_name["test_setup"].exc_type == "RuntimeError"


def test_junit_details_of_an_unreadable_report_are_empty(tmp_path: Path) -> None:
    assert junit_details(tmp_path / "missing.xml") == JUnitDetails(0, 0, (), readable=False)


def test_a_repo_traceback_setting_cannot_hide_crash_locations(tmp_path: Path) -> None:
    tree = write_files(
        tmp_path,
        {
            "pyproject.toml": '[tool.pytest.ini_options]\naddopts = "--tb=line"\n',
            "test_a.py": "def test_a():\n    assert 1 == 2\n",
            "test_b.py": "import json\n\ndef test_b():\n    json.no_such_name()\n",
        },
    )
    failures = {f.test: f for f in run_pytest(tree, reruns=0, timeout_s=120).first.failures}
    a, b = failures["test_a::test_a"], failures["test_b::test_b"]
    assert (a.exc_type, a.location, a.message) == ("AssertionError", "test_a.py:2", "assert 1 == 2")
    assert (b.exc_type, b.location) == ("AttributeError", "test_b.py:4")
    assert b.message == "AttributeError: module 'json' has no attribute 'no_such_name'"


# --- M6: Tracefix's own code in a run (Probe) --------------------------------------------------

PROBE_TEST = """\
import os

import tracefix_probe_mod


def test_probe():
    assert tracefix_probe_mod.VALUE == 42
    assert os.environ["TRACEFIX_EXTRA"] == "yes"
    with open(os.environ["TRACEFIX_OUT"], "a", encoding="utf-8") as f:
        f.write("from the test\\n")
"""

PROBE_PLUGIN = """\
import os


def pytest_configure(config):
    with open(os.environ["TRACEFIX_OUT"], "a", encoding="utf-8") as f:
        f.write("from the plugin\\n")
"""


LINES = ["from the plugin", "from the test"]


def probe() -> Probe:
    return Probe({"tracefix_probe_mod": "VALUE = 42\n", "tracefix_probe_plugin": PROBE_PLUGIN},
                 ("tracefix_probe_plugin",), {"TRACEFIX_EXTRA": "yes"})  # fmt: skip


def out_lines(out: str | None) -> list[str]:
    assert out is not None, "the run's out file was not read"
    return out.splitlines()  # Windows text mode writes \r\n


def test_a_probe_brings_modules_plugins_and_env_and_reads_its_out_file(tmp_path: Path) -> None:
    tree = write_files(tmp_path / "proj", {"test_p.py": PROBE_TEST})
    result = run_pytest(tree, probe=probe(), timeout_s=120)
    assert result.outcome is Outcome.PASSED, result.first.output
    assert out_lines(result.first.out) == LINES
    # The modules live in the run's scratch folder, never in the copy under test.
    assert sorted(p.name for p in tree.iterdir()) == ["test_p.py"]


def test_without_a_probe_there_is_no_out_file_and_nothing_is_read(tmp_path: Path) -> None:
    test = "import os\n\n\ndef test_no_out():\n    assert 'TRACEFIX_OUT' not in os.environ\n"
    result = run_pytest(write_files(tmp_path, {"test_n.py": test}), timeout_s=120)
    assert result.outcome is Outcome.PASSED, result.first.output
    assert result.first.out is None


def test_the_out_file_is_read_after_every_attempt_and_after_a_timeout(tmp_path: Path) -> None:
    failing = PROBE_TEST.replace("f.write(\"from the test\\n\")",
                                 "f.write(\"from the test\\n\")\n    assert False")  # fmt: skip
    assert "assert False" in failing  # precondition: the replace above matched
    result = run_pytest(write_files(tmp_path / "f", {"test_p.py": failing}), probe=probe(),
                        reruns=1, timeout_s=120)  # fmt: skip
    assert result.outcome is Outcome.FAILED
    assert [out_lines(a.out) for a in result.attempts] == [LINES] * 2
    hangs = PROBE_TEST + "\n\ndef test_then_hang():\n    import time\n    time.sleep(60)\n"
    result = run_pytest(write_files(tmp_path / "h", {"test_p.py": hangs}), probe=probe(),
                        timeout_s=10)  # fmt: skip
    assert result.outcome is Outcome.TIMEOUT
    assert out_lines(result.first.out) == LINES  # written before the hang


def test_only_a_plain_out_file_is_read_and_only_up_to_the_limit(tmp_path: Path) -> None:
    folder = "import os\n\n\ndef test_dir():\n    os.mkdir(os.environ['TRACEFIX_OUT'])\n"
    result = run_pytest(write_files(tmp_path / "d", {"test_d.py": folder}),
                        probe=Probe(), timeout_s=120)  # fmt: skip
    assert result.outcome is Outcome.PASSED, result.first.output
    assert result.first.out is None
    big = (
        "import os\n\n\ndef test_big():\n"
        f"    open(os.environ['TRACEFIX_OUT'], 'w').write('x' * {OUT_LIMIT + 10})\n"
    )
    result = run_pytest(write_files(tmp_path / "b", {"test_b.py": big}), probe=Probe(),
                        timeout_s=120)  # fmt: skip
    assert result.outcome is Outcome.PASSED, result.first.output
    assert result.first.out == "x" * OUT_LIMIT


def test_probe_module_names_must_be_plain_identifiers(tmp_path: Path) -> None:
    for bad in ("../evil", "a.b", "", "x y"):
        with pytest.raises(ValueError, match="not a module name"):
            write_module(tmp_path, bad, "")
    assert list(tmp_path.iterdir()) == []


def test_tracefix_modules_give_hypothesis_no_constants(tmp_path: Path) -> None:
    # Verifier round 7: Hypothesis seeds its draws with string constants from the run's source
    # files, except test files. Tracefix's runtime must not be read as project code: its strings
    # are not the project's, and every edit to it changed the draws (and the recorded requests).
    from hypothesis.internal.constants_ast import is_local_module_file

    from tracefix.sandbox import MODULES_DIR

    write_module(tmp_path, "tracefix_rt_x", "WORD = 'model'\n")
    path = tmp_path / MODULES_DIR / "tracefix_rt_x.py"
    assert path.is_file()
    assert not is_local_module_file(str(path))
    assert is_local_module_file(str(tmp_path / "pkg" / "module.py"))  # a project file still is
