"""M8: the no-regression check. Real pytest runs in real copies, watched, on tiny repos; no model
at all. A regression needs the head suite and two confirmation runs to agree; anything flaky or
unfinished stays inconclusive."""

from dataclasses import replace
from pathlib import Path

import pytest
from conftest import make_repo

from tracefix.diffscope import compute_scope
from tracefix.isolation import check_environment
from tracefix.regressions import (
    Candidate,
    Compared,
    Regression,
    RegressionResult,
    RegressionStatus,
    Unconfirmed,
    check,
    confirm,
)
from tracefix.runner import Attempt, EnvironmentCheck, EnvStatus, FailureInfo, Outcome, RunResult
from tracefix.sandbox import sandbox_level
from tracefix.workspace import RunSettings, Workspace

LEVEL = sandbox_level()
PYPROJECT = '[tool.pytest.ini_options]\npythonpath = ["src"]\n'
SLUG = 'def slug(text):\n    return "-".join(text.lower().split(" "))\n'
FIXED = 'def slug(text):\n    return "-".join(text.lower().split())\n'
NO_LOWER = 'def slug(text):\n    return "-".join(text.split())\n'  # fixes spaces, breaks case
TESTS = """\
import pytest

from slug import slug


def test_spaces():
    assert slug("a b") == "a-b"


class TestSlug:
    @pytest.mark.parametrize("text, want", [("One", "one"), ("x", "x")])
    def test_case(self, text, want):
        assert slug(text) == want
"""
OTHER = 'from slug import slug\n\n\ndef test_other():\n    assert slug("b") == "b"\n'
NEW_TEST = 'from slug import slug\n\n\ndef test_double_space():\n    assert slug("a  b") == "a-b"\n'
BASE = {"src/slug.py": SLUG, "tests/test_slug.py": TESTS, "tests/test_other.py": OTHER}


def run_check(tmp_path: Path, base: dict[str, str | None], head: dict[str, str | None],
              settings: RunSettings | None = None) -> RegressionResult:  # fmt: skip
    repo = make_repo(tmp_path / "repo", [{"pyproject.toml": PYPROJECT, **base}, head])
    with Workspace(repo, "c0", "c1", settings) as ws:
        scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
        env = check_environment(ws)
        assert env.status is EnvStatus.OK, env.reason
        return check(ws, scope, env)


def found(result: RegressionResult) -> list[tuple[str, str | None]]:
    return [(r.file, r.test) for r in result.regressions]


# --- found ---------------------------------------------------------------------------------------


def test_a_fix_that_breaks_an_untouched_test_is_found(tmp_path: Path) -> None:
    result = run_check(tmp_path, BASE, {"src/slug.py": NO_LOWER, "tests/test_fix.py": NEW_TEST})
    assert result.status is RegressionStatus.FOUND, result.reason
    assert found(result) == [("tests/test_slug.py", "TestSlug.test_case[One-one]")]
    assert result.regressions[0].line == 12  # its def line (below the decorator): annotated
    evidence = result.regressions[0].evidence
    assert "fails after it in all 4 attempts" in evidence and "'One' == 'one'" in evidence
    assert result.compared == 4 and result.not_run == 0 and result.unconfirmed == ()
    assert [label for label, _ in result.runs] == [
        "the whole suite on the fixed code",
        "the candidates' files before the fix",
        "the candidates' files on the fixed code",
    ]
    assert result.reason == "1 confirmed: tests/test_slug.py::TestSlug.test_case[One-one]"


def test_a_good_fix_finds_nothing_with_one_suite_run(tmp_path: Path) -> None:
    result = run_check(tmp_path, BASE, {"src/slug.py": FIXED, "tests/test_fix.py": NEW_TEST})
    assert result.status is RegressionStatus.NONE_FOUND, result.reason
    assert result.compared == 4 and len(result.runs) == 1
    assert result.reason == ("none of the 4 untouched tests that passed before the fix fails "
                             "after it")  # fmt: skip


def test_a_renamed_untouched_test_file_is_still_compared(tmp_path: Path) -> None:
    head = {"src/slug.py": NO_LOWER, "tests/test_slug.py": None, "tests/test_slugs.py": TESTS}
    result = run_check(tmp_path, BASE, head)
    assert result.status is RegressionStatus.FOUND, result.reason
    assert found(result) == [("tests/test_slugs.py", "TestSlug.test_case[One-one]")]


def test_a_file_that_stops_collecting_is_found_and_the_rest_still_runs(tmp_path: Path) -> None:
    renamed = FIXED.replace("def slug", "def make_slug")
    head = {"src/slug.py": renamed,
            "tests/test_fix.py": "from slug import make_slug\n\n\ndef test_new():\n"
                                 "    assert make_slug('a  b') == 'a-b'\n"}  # fmt: skip
    result = run_check(tmp_path, {**BASE, "tests/test_kept.py": "def test_kept():\n    pass\n"},
                       head)  # fmt: skip
    assert result.status is RegressionStatus.FOUND, result.reason
    assert found(result) == [("tests/test_other.py", None), ("tests/test_slug.py", None)]
    assert [r.line for r in result.regressions] == [None, None]  # a whole file has no def line
    evidence = result.regressions[1].evidence
    assert "collected and its 3 test(s) passed before the fix" in evidence
    assert "fails to collect in all 4 attempts" in evidence
    head_run = result.runs[0][1]
    assert "tests.test_kept::test_kept" in head_run.first.passed  # not hidden by the error
    assert "ImportError: cannot import name 'slug'" in evidence  # pytest's own words, not
    # only "collection failure"


def test_a_fix_needing_a_dependency_this_environment_lacks_is_inconclusive(
    tmp_path: Path,
) -> None:
    """An environment problem, not a counterexample (developer, 13 Oct 2026, verifier S2)."""
    head = {"src/slug.py": "import not_installed_dep_xyz\n" + FIXED}
    result = run_check(tmp_path, BASE, head)
    assert result.status is RegressionStatus.INCONCLUSIVE, result.reason
    assert result.regressions == ()
    assert [u.file for u in result.unconfirmed] == ["tests/test_other.py", "tests/test_slug.py"]
    assert all(u.why_not.startswith("the fixed code imports not_installed_dep_xyz, which is not "
                                    "installed") for u in result.unconfirmed)  # fmt: skip


LOADER = """import importlib


class PluginError(Exception):
    pass


def load(name):
    try:
        return importlib.import_module(name)
    except ImportError as exc:
        raise PluginError(name) from exc
"""
LOADER_TEST = """import pytest
from loader import PluginError, load


def test_missing_plugin():
    with pytest.raises(PluginError):
        load("nope_plugin")
"""


def test_a_missing_module_the_fix_did_not_import_is_still_a_regression(tmp_path: Path) -> None:
    """The fix stops wrapping importlib's error: the head failure says "No module named
    'nope_plugin'", but no import statement the fix added names it and the test passes on base
    in the same environment, so it is the fix's doing (verifier round 2, blocker)."""
    unwrapped = LOADER.split("def load")[0]
    unwrapped += "def load(name):\n    return importlib.import_module(name)\n"
    base = {**BASE, "src/loader.py": LOADER, "tests/test_loader.py": LOADER_TEST}
    result = run_check(tmp_path, base, {"src/loader.py": unwrapped, "src/slug.py": FIXED})
    assert result.status is RegressionStatus.FOUND, result.reason
    assert found(result) == [("tests/test_loader.py", "test_missing_plugin")]
    assert "No module named 'nope_plugin'" in result.regressions[0].evidence


def test_a_project_module_the_fix_removed_is_still_a_regression(tmp_path: Path) -> None:
    base = {**BASE, "src/slug_words.py": "SEP = '-'\n"}
    head = {"src/slug_words.py": None, "src/slug.py": "import slug_words\n" + FIXED}
    result = run_check(tmp_path, base, head)
    assert result.status is RegressionStatus.FOUND, result.reason
    assert "No module named 'slug_words'" in result.regressions[0].evidence


# --- not compared --------------------------------------------------------------------------------


def test_a_test_the_pr_changed_is_not_compared(tmp_path: Path) -> None:
    changed = TESTS.replace("assert slug(text) == want", 'assert slug(text) == want, "case"')
    result = run_check(tmp_path, BASE, {"src/slug.py": NO_LOWER, "tests/test_slug.py": changed})
    assert result.status is RegressionStatus.NONE_FOUND, result.reason
    assert result.compared == 2  # test_spaces and test_other only


def test_code_the_pr_changed_around_tests_leaves_none_of_them_compared(tmp_path: Path) -> None:
    around = TESTS.replace("from slug import slug\n", "from slug import slug\n\nLIMIT = 3\n")
    result = run_check(tmp_path, BASE, {"src/slug.py": NO_LOWER, "tests/test_slug.py": around})
    assert result.status is RegressionStatus.NONE_FOUND, result.reason
    assert result.compared == 1  # test_other only


def test_a_changed_conftest_leaves_the_tests_below_it_uncompared(tmp_path: Path) -> None:
    head = {"src/slug.py": NO_LOWER, "tests/conftest.py": "# fixtures\n"}
    result = run_check(tmp_path, BASE, head)
    assert result.status is RegressionStatus.SKIPPED and result.runs == ()
    assert result.reason == "no test the fix left untouched passed before it"


def test_changed_pytest_options_skip_the_check(tmp_path: Path) -> None:
    head = {"src/slug.py": NO_LOWER, "pyproject.toml": PYPROJECT + 'addopts = "-q"\n'}
    result = run_check(tmp_path, BASE, head)
    assert result.status is RegressionStatus.SKIPPED and result.runs == ()
    assert "changes pytest's options (pyproject.toml)" in result.reason


def test_a_config_change_outside_pytest_does_not_skip(tmp_path: Path) -> None:
    head = {"src/slug.py": NO_LOWER, "pyproject.toml": '[project]\nname = "slug"\n\n' + PYPROJECT}
    result = run_check(tmp_path, BASE, head)
    assert result.status is RegressionStatus.FOUND, result.reason


def test_an_unreadable_base_report_skips_the_check(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo", [{"pyproject.toml": PYPROJECT, **BASE},
                                         {"src/slug.py": NO_LOWER}])  # fmt: skip
    attempt = Attempt(1, 0.1, (), "", report_ok=False)
    env = EnvironmentCheck(EnvStatus.OK, "", None, None,
                           RunResult(Outcome.ERROR, ("python",), (attempt,)))  # fmt: skip
    with Workspace(repo, "c0", "c1") as ws:
        result = check(ws, compute_scope(ws.repo, ws.base_sha, ws.head_sha), env)
    assert result.status is RegressionStatus.SKIPPED and result.runs == ()
    assert result.reason == "the base suite's run left no readable report"


# --- never a regression --------------------------------------------------------------------------

FLAKY_TEST = """\
from dataclasses import replace
from pathlib import Path

from slug import FLAKY


def test_sometimes():
    if FLAKY:  # fails on the first attempt after the fix, passes on the rerun
        count = Path(__file__).parent / "count.txt"
        n = int(count.read_text()) + 1 if count.exists() else 1
        count.write_text(str(n))
        assert n % 2 == 0
"""


def test_a_test_that_flakes_after_the_fix_is_not_counted(tmp_path: Path) -> None:
    base = {**BASE, "src/slug.py": SLUG + "\nFLAKY = False\n", "tests/test_flaky.py": FLAKY_TEST}
    result = run_check(tmp_path, base, {"src/slug.py": FIXED + "\nFLAKY = True\n"})
    assert result.status is RegressionStatus.NONE_FOUND, result.reason
    head_run = result.runs[0][1]
    assert head_run.outcome is Outcome.FLAKY and len(result.runs) == 1


STATEFUL = SLUG + "\nSEEN = []\n"
FIRST = "from slug import SEEN\n\n\ndef test_a_first():\n    SEEN.append(1)\n"
SECOND = 'from slug import slug\n\n\ndef test_b_second():\n    assert slug("One") == "one"\n'


def test_a_failure_only_in_the_whole_suite_is_inconclusive(tmp_path: Path) -> None:
    base = {"src/slug.py": STATEFUL, "tests/test_a.py": FIRST, "tests/test_b.py": SECOND}
    # After the fix, slug depends on state test_a_first leaves behind: test_b_second fails in
    # the whole suite but passes when its file runs alone.
    head = {"src/slug.py": "SEEN = []\n\n\n" + FIXED.replace(
        "def slug(text):\n", "def slug(text):\n    if SEEN:\n        return text\n")}  # fmt: skip
    result = run_check(tmp_path, base, head)
    assert result.status is RegressionStatus.INCONCLUSIVE, result.reason
    assert result.regressions == ()
    assert [(u.file, u.test, u.why_not) for u in result.unconfirmed] == [
        ("tests/test_b.py", "test_b_second", "it passes when its file runs again on the fixed code")
    ]


def test_a_head_suite_that_times_out_is_inconclusive(tmp_path: Path) -> None:
    slow = FIXED.replace("def slug(text):\n", "def slug(text):\n    import time\n"
                                              "    time.sleep(120)\n")  # fmt: skip
    result = run_check(tmp_path, BASE, {"src/slug.py": slow}, RunSettings(suite_timeout_s=15))
    assert result.status is RegressionStatus.INCONCLUSIVE, result.reason
    assert result.reason == "the suite on the fixed code ended with timeout"
    assert result.regressions == ()


def test_tampering_by_the_fixed_code_makes_the_check_invalid(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    target = root / "src" / "slug.py"
    hostile = FIXED.replace("def slug(text):\n", "def slug(text):\n"
                            f"    open({target.as_posix()!r}, 'a').write('# x')\n")  # fmt: skip
    result = run_check(tmp_path, BASE, {"src/slug.py": hostile})
    if LEVEL == "strict":  # the write is blocked, so every compared test fails on head instead
        assert result.status is RegressionStatus.FOUND, result.reason
    else:
        assert result.status is RegressionStatus.INVALID, result.reason
        assert result.reason.startswith("during the whole suite on the fixed code")
        assert result.regressions == ()


# --- confirming a candidate (pure) ---------------------------------------------------------------

TEST = Compared("tests/test_x.py", "tests/test_x.py", "tests.test_x::test_a",
                "tests.test_x::test_a", "test_a")  # fmt: skip
CANDIDATE = Candidate("tests/test_x.py", "test_a", (TEST,), TEST.head_id, "AssertionError")
FAILURE = FailureInfo(TEST.head_id, "failure", "AssertionError", None, "assert 1 == 2")


def attempt(*, passed: tuple[str, ...] = (), failed: tuple[str, ...] = (),
            report_ok: bool = True) -> Attempt:  # fmt: skip
    failures = (FAILURE,) if TEST.head_id in failed else ()
    return Attempt(1 if failed else 0, 0.1, failed, "", tests=len(passed) + len(failed),
                   failures=failures, report_ok=report_ok, passed=passed)  # fmt: skip


def run(outcome: Outcome, *attempts: Attempt) -> RunResult:
    return RunResult(outcome, ("python",), attempts)


BASE_PASS = run(Outcome.PASSED, attempt(passed=(TEST.base_id,)))
HEAD_FAIL = run(Outcome.FAILED, *[attempt(failed=(TEST.head_id,))] * 4)


def test_a_candidate_confirmed_by_both_runs_is_a_regression() -> None:
    outcome = confirm(CANDIDATE, BASE_PASS, HEAD_FAIL)
    assert isinstance(outcome, Regression)
    assert outcome.line is None  # TEST was compared without a def line
    with_line = replace(CANDIDATE, tests=(replace(TEST, line=7),))
    assert confirm(with_line, BASE_PASS, HEAD_FAIL) == replace(outcome, line=7)
    assert outcome.evidence == ("passed before the fix (also when its file ran alone); fails "
                                "after it in all 4 attempts: assert 1 == 2")  # fmt: skip


@pytest.mark.parametrize(
    ("base", "head", "why"),
    [
        (run(Outcome.FAILED, *[attempt(failed=(TEST.base_id,))] * 4), HEAD_FAIL,
         "it does not pass again before the fix when its file runs alone"),
        (run(Outcome.FLAKY, attempt(failed=("other::t",), passed=(TEST.base_id,)),
             attempt(passed=(TEST.base_id,), report_ok=False)), HEAD_FAIL,
         "it does not pass again before the fix when its file runs alone"),
        (run(Outcome.TIMEOUT, attempt(report_ok=False)), HEAD_FAIL,
         "the confirmation run before the fix ended with timeout"),
        (BASE_PASS, run(Outcome.FLAKY, attempt(failed=(TEST.head_id,)), attempt()),
         "its file's results on the fixed code changed between reruns (flaky)"),
        (BASE_PASS, run(Outcome.PASSED, attempt(passed=(TEST.head_id,))),
         "it passes when its file runs again on the fixed code"),
        (BASE_PASS, run(Outcome.FAILED, *[attempt(failed=("other::t",))] * 4),
         "it passes when its file runs again on the fixed code"),
        (BASE_PASS, run(Outcome.ERROR, attempt(report_ok=False)),
         "the confirmation run on the fixed code ended with error"),
    ],
)  # fmt: skip
def test_a_candidate_is_unconfirmed_unless_both_runs_agree(base: RunResult, head: RunResult,
                                                           why: str) -> None:  # fmt: skip
    outcome = confirm(CANDIDATE, base, head)
    assert isinstance(outcome, Unconfirmed) and outcome.why_not == why
