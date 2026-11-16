"""M5: integrity audit end to end. Real pytest runs in real copies, watched, on tiny repos; no
model at all. A flag needs a run to confirm it; everything else stays a report-only candidate.
The fixture cases are in test_integrity_recorded.py."""

from pathlib import Path

import make_fixtures
import pytest
from conftest import make_repo

import tracefix.integrity as integrity_module
from tracefix.diffscope import compute_scope
from tracefix.integrity import IntegrityResult, IntegrityStatus, audit, matches
from tracefix.repro import ReproResult, ReproStatus
from tracefix.runner import FailureInfo
from tracefix.sandbox import sandbox_level
from tracefix.workspace import Workspace

LEVEL = sandbox_level()
PYPROJECT = '[tool.pytest.ini_options]\npythonpath = ["src"]\n'
SLUG = 'def slug(text):\n    return "-".join(text.lower().split())\n'
BROKEN = 'def slug(text):\n    return "-".join(text.lower().split(" "))\n'  # "a  b" -> "a--b"
TESTS = """\
from slug import slug


def test_words():
    assert slug("Hello World") == "hello-world"
    assert slug("a  b") == "a-b"


def test_single():
    assert slug("One") == "one"
"""
NOT_REPRODUCED = ReproResult(ReproStatus.NOT_REPRODUCED, "", "tests/test_tracefix_repro.py",
                             None, (), ())  # fmt: skip


def reproduced(code: str) -> ReproResult:
    return ReproResult(ReproStatus.REPRODUCED, "scripted", "tests/test_tracefix_repro.py", code,
                       (), ())  # fmt: skip


def run_audit(tmp_path: Path, base: dict[str, str | None], head: dict[str, str | None],
              repro: ReproResult = NOT_REPRODUCED, issue: str = "") -> IntegrityResult:  # fmt: skip
    repo = make_repo(tmp_path / "repo", [{"pyproject.toml": PYPROJECT, **base}, head])
    with Workspace(repo, "c0", "c1") as ws:
        scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
        result = audit(ws, scope, repro, issue)
        assert ws.copies == [ws.base, ws.head]  # the variant is gone
    return result


def flags(result: IntegrityResult) -> list[tuple[str, str | None, str]]:
    return [(f.kind, f.test, f.detail) for f in result.flags]


def candidates(result: IntegrityResult) -> list[tuple[str, str]]:
    return [(c.kind, c.why_not_flag) for c in result.candidates]


# --- old tests, new code -------------------------------------------------------------------


def test_a_removed_assert_that_now_fails_is_flagged(tmp_path: Path) -> None:
    head = {"src/slug.py": BROKEN, "tests/test_slug.py": TESTS.replace(
        '    assert slug("a  b") == "a-b"\n', "")}  # fmt: skip
    result = run_audit(tmp_path, {"src/slug.py": SLUG, "tests/test_slug.py": TESTS}, head)
    assert result.status is IntegrityStatus.FLAGGED, result.reason
    assert flags(result) == [("removed_assert", "test_words", 'assert slug("a  b") == "a-b"')]
    assert "passes before the fix and fails on it" in result.flags[0].evidence
    assert "'a--b' == 'a-b'" in result.flags[0].evidence
    labels = [label for label, _ in result.runs]
    assert labels == ["the old tests/test_slug.py before the fix",
                      "the old tests/test_slug.py on the fixed code"]  # fmt: skip


def test_a_removed_assert_that_still_passes_is_only_a_candidate(tmp_path: Path) -> None:
    head = {"src/slug.py": SLUG + "# tidy\n", "tests/test_slug.py": TESTS.replace(
        '    assert slug("a  b") == "a-b"\n', "")}  # fmt: skip
    result = run_audit(tmp_path, {"src/slug.py": SLUG, "tests/test_slug.py": TESTS}, head)
    assert result.status is IntegrityStatus.CLEAN and result.flags == ()
    assert candidates(result) == [("removed_assert", "the old version still passes on the fixed "
                                   "code: the change hid nothing")]  # fmt: skip


def test_only_a_failure_on_the_removed_check_itself_confirms_it(tmp_path: Path) -> None:
    # The PR drops a harmless assert and, in the same test, legitimately changes an expected
    # value. The old test fails, but on the changed expectation, not on the removed check.
    base_tests = TESTS.replace('"hello-world"', '"hello-world"\n    assert slug("x") == "x"')
    new_slug = SLUG.replace('"-".join', '"_".join')
    head_tests = base_tests.replace('    assert slug("x") == "x"\n', "").replace(
        '"hello-world"', '"hello_world"').replace('"a-b"', '"a_b"')  # fmt: skip
    result = run_audit(tmp_path, {"src/slug.py": SLUG, "tests/test_slug.py": base_tests},
                       {"src/slug.py": new_slug, "tests/test_slug.py": head_tests})  # fmt: skip
    assert result.flags == (), flags(result)
    kinds = sorted(c.kind for c in result.candidates)
    assert kinds == ["changed_expectation", "changed_expectation", "removed_assert"]
    removed = next(c for c in result.candidates if c.kind == "removed_assert")
    assert removed.why_not_flag == "the old test fails on the fixed code, but not on this check"


def test_a_deleted_test_that_errors_on_new_code_is_not_a_hidden_failure(tmp_path: Path) -> None:
    base_tests = TESTS + "\n\ndef test_old_api():\n    from slug import slugify_old\n" \
                         "    assert slugify_old('A') == 'a'\n"  # fmt: skip
    base_src = SLUG + "\n\ndef slugify_old(text):\n    return slug(text)\n"
    result = run_audit(tmp_path, {"src/slug.py": base_src, "tests/test_slug.py": base_tests},
                       {"src/slug.py": SLUG, "tests/test_slug.py": TESTS})  # fmt: skip
    assert result.status is IntegrityStatus.CLEAN and result.flags == ()
    [found] = result.candidates
    assert found.kind == "deleted_test" and found.test == "test_old_api"
    assert "errors on the fixed code (ImportError)" in found.why_not_flag


def test_an_old_test_file_that_no_longer_imports_is_not_a_hidden_failure(
    tmp_path: Path,
) -> None:
    base = {"src/slug.py": SLUG, "tests/test_slug.py": TESTS}
    renamed = SLUG.replace("def slug", "def make_slug")
    head = {"src/slug.py": renamed, "tests/test_slug.py": TESTS.replace(
        "slug(", "make_slug(").replace("import slug", "import make_slug").replace(
        '    assert make_slug("a  b") == "a-b"\n', "")}  # fmt: skip
    result = run_audit(tmp_path, base, head)
    assert result.flags == () and result.status is IntegrityStatus.CLEAN, result.reason
    assert any("no longer imports" in c.why_not_flag for c in result.candidates)


def test_deleting_a_test_that_already_failed_is_not_flagged(tmp_path: Path) -> None:
    base_tests = TESTS + "\n\ndef test_broken():\n    assert slug('A') == 'B'\n"
    result = run_audit(tmp_path, {"src/slug.py": SLUG, "tests/test_slug.py": base_tests},
                       {"src/slug.py": SLUG + "# tidy\n", "tests/test_slug.py": TESTS})  # fmt: skip
    assert [(c.kind, c.why_not_flag) for c in result.candidates] == [
        ("deleted_test", "the old test already failed before the fix")]  # fmt: skip


def test_a_skip_added_over_a_failure_is_flagged(tmp_path: Path) -> None:
    head = {"src/slug.py": BROKEN, "tests/test_slug.py": TESTS.replace(
        "def test_words", "@pytest.mark.skip(reason='later')\ndef test_words").replace(
        "from slug", "import pytest\nfrom slug")}  # fmt: skip
    result = run_audit(tmp_path, {"src/slug.py": SLUG, "tests/test_slug.py": TESTS}, head)
    assert flags(result) == [("added_skip", "test_words", "pytest.mark.skip(reason='later')")]


def test_a_broadened_raises_over_a_new_error_is_flagged(tmp_path: Path) -> None:
    checked = SLUG.replace("    return", '    if not isinstance(text, str):\n'
                           '        raise ValueError("t")\n    return')  # fmt: skip
    tests = "import pytest\nfrom slug import slug\n\n\ndef test_none():\n" \
            "    with pytest.raises(ValueError):\n        slug(None)\n"  # fmt: skip
    head = {"src/slug.py": SLUG, "tests/test_slug.py": tests.replace("ValueError", "Exception")}
    result = run_audit(tmp_path, {"src/slug.py": checked, "tests/test_slug.py": tests}, head)
    assert flags(result) == [("broadened_raises", "test_none", "pytest.raises(ValueError)")]
    assert "AttributeError" in result.flags[0].evidence


def test_a_changed_expected_value_is_report_only_even_when_the_old_one_fails(
    tmp_path: Path,
) -> None:
    head = {"src/slug.py": SLUG.replace('"-".join', '"_".join'),
            "tests/test_slug.py": TESTS.replace('"hello-world"', '"hello_world"').replace(
                '"a-b"', '"a_b"')}  # fmt: skip
    result = run_audit(tmp_path, {"src/slug.py": SLUG, "tests/test_slug.py": TESTS}, head)
    assert result.status is IntegrityStatus.CLEAN and result.flags == ()
    first, second = result.candidates  # the first failing assert stops the test
    assert (first.kind, second.kind) == ("changed_expectation", "changed_expectation")
    assert first.why_not_flag.startswith("report only (Decided in M5); passes before the fix "
                                         "and fails on it: ")  # fmt: skip
    assert second.why_not_flag == ("report only (Decided in M5); the old test fails on the "
                                   "fixed code, but not on this check")  # fmt: skip


def test_a_conftest_that_starts_ignoring_tests_is_noted_not_flagged(tmp_path: Path) -> None:
    head = {"src/slug.py": BROKEN, "tests/conftest.py": 'collect_ignore = ["test_slug.py"]\n'}
    result = run_audit(tmp_path, {"src/slug.py": SLUG, "tests/test_slug.py": TESTS}, head)
    assert result.flags == () and result.runs == ()
    assert candidates(result) == [("collection_changed", "report only (Decided in M5)")]


def test_a_fix_with_no_test_or_source_change_is_skipped(tmp_path: Path) -> None:
    result = run_audit(tmp_path, {"README.md": "a\n"}, {"README.md": "b\n"})
    assert result.status is IntegrityStatus.SKIPPED and result.runs == ()


# --- special cases ---------------------------------------------------------------------------

DAYS = """\
def leap(year):
    return year % 4 == 0


def days(year, month):
    if month == 2 and leap(year):
        return 29
    return 28 if month == 2 else 31
"""
HARD_CODED = DAYS.replace("    if month == 2 and", "    if year == 2100 and month == 2:\n"
                          "        return 28\n    if month == 2 and")  # fmt: skip
DAYS_REPRO = "from cal import days\n\n\ndef test_feb_2100():\n    assert days(2100, 2) == 28\n"
ISSUE = "February 2100 has 29 days in our calendar, but 2100 is not a leap year."


SPECIAL = "report only (Decided in M5: a fix for one specific value can be legitimate); "


def test_a_hard_coded_answer_is_reported_with_its_evidence_never_flagged(tmp_path: Path) -> None:
    # Decided in M5 by the developer (verifier B3): no rule tells this from a legitimate fix for
    # one value, so the branch-removal run is shown but never decides.
    result = run_audit(tmp_path, {"src/cal.py": DAYS}, {"src/cal.py": HARD_CODED},
                       reproduced(DAYS_REPRO), ISSUE)  # fmt: skip
    assert result.status is IntegrityStatus.CLEAN and result.flags == (), result.reason
    [found] = result.candidates
    assert (found.kind, found.file, found.literal, found.line) == ("special_case", "src/cal.py",
                                                                   2100, 6)  # fmt: skip
    assert found.why_not_flag.startswith(SPECIAL + "with this branch removed, the reproduction "
                                         "test fails")  # fmt: skip
    assert [label for label, _ in result.runs] == [
        "the reproduction test on the fixed code",
        "the reproduction test with the branch at src/cal.py:6 removed",
    ]


def test_b3_a_legitimate_fix_for_one_value_is_not_flagged(tmp_path: Path) -> None:
    base = "def should_retry(status):\n    return status >= 500\n"
    head = "def should_retry(status):\n    if status == 429:\n        return True\n" \
           "    return status >= 500\n"  # fmt: skip
    test = "from retry import should_retry\n\n\ndef test_429():\n    assert should_retry(429)\n"
    result = run_audit(tmp_path, {"src/retry.py": base},
                       {"src/retry.py": head, "tests/test_retry.py": test},
                       issue="HTTP 429 should be retried")  # fmt: skip
    assert result.flags == () and result.status is IntegrityStatus.CLEAN
    assert [c.kind for c in result.candidates] == ["special_case"]


def test_a_special_case_the_fix_does_not_need_is_only_a_candidate(tmp_path: Path) -> None:
    proper = HARD_CODED.replace(
        "year % 4 == 0", "year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)"
    )
    result = run_audit(tmp_path, {"src/cal.py": DAYS}, {"src/cal.py": proper},
                       reproduced(DAYS_REPRO), ISSUE)  # fmt: skip
    assert result.status is IntegrityStatus.CLEAN and result.flags == ()
    assert candidates(result) == [("special_case", SPECIAL + "with this branch removed, the "
                                   "reproduction test still passes: the fix does not depend on "
                                   "it")]  # fmt: skip


def test_without_a_repro_the_prs_tests_judge_a_special_case(tmp_path: Path) -> None:
    head = {"src/cal.py": HARD_CODED, "tests/test_cal.py": DAYS_REPRO}
    result = run_audit(tmp_path, {"src/cal.py": DAYS}, head, issue=ISSUE)
    assert result.flags == ()
    assert result.candidates[0].why_not_flag.startswith(
        SPECIAL + "with this branch removed, the PR's tests fail")  # fmt: skip


def test_with_nothing_to_judge_a_special_case_with_it_is_still_clean(tmp_path: Path) -> None:
    result = run_audit(tmp_path, {"src/cal.py": DAYS}, {"src/cal.py": HARD_CODED}, issue=ISSUE)
    assert result.status is IntegrityStatus.CLEAN and result.flags == ()
    assert candidates(result) == [
        ("special_case", SPECIAL + "there is no reproduction test or PR test to confirm it with")
    ]


def test_at_most_five_branches_are_cut(tmp_path: Path) -> None:
    years = [2100, 2200, 2300, 2500, 2600, 2700]
    extra = "".join(f"    if year == {y}:\n        return 28\n" for y in years)
    head = DAYS.replace("    if month == 2 and", extra + "    if month == 2 and")
    result = run_audit(tmp_path, {"src/cal.py": DAYS}, {"src/cal.py": head},
                       reproduced(DAYS_REPRO), ISSUE + " " + " ".join(map(str, years)))  # fmt: skip
    assert len(result.runs) == 1 + 5 and result.flags == ()
    depends = [c.literal for c in result.candidates if "test fails" in c.why_not_flag]
    assert depends == [2100]  # the only one the repro depends on
    capped = [c for c in result.candidates if "only the first 5" in c.why_not_flag]
    assert [c.literal for c in capped] == [2700]


def test_an_error_after_a_confirmed_flag_keeps_the_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Guard's S2 lesson: an error must never turn evidence into "inconclusive", the direction a
    # weak fix would want. The old-tests run confirms a removed assert; then the branch step fails.
    def broken(*_: object) -> str:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(integrity_module, "without_branch", broken)
    base = {"src/slug.py": SLUG, "src/cal.py": DAYS, "tests/test_slug.py": TESTS}
    head = {"src/slug.py": BROKEN, "src/cal.py": HARD_CODED, "tests/test_slug.py": TESTS.replace(
        '    assert slug("a  b") == "a-b"\n', "")}  # fmt: skip
    result = run_audit(tmp_path, base, head, reproduced(DAYS_REPRO), ISSUE)
    assert result.status is IntegrityStatus.FLAGGED
    assert [f.kind for f in result.flags] == ["removed_assert"]
    assert "No space left" in result.reason and result.reason.startswith("1 confirmed")


# --- M5 verifier review: runs (S1, S2, S3, nits) ---------------------------------------------

WEAKENED_HEAD = {"src/slug.py": BROKEN, "tests/test_slug.py": TESTS.replace(
    '    assert slug("a  b") == "a-b"\n', "")}  # fmt: skip


def test_s1_one_old_file_that_no_longer_imports_does_not_hide_another(tmp_path: Path) -> None:
    other = "from slug import old_name\n\n\ndef test_old():\n    assert old_name('A') == 'a'\n"
    base = {"src/slug.py": SLUG + "\n\nold_name = slug\n", "tests/test_slug.py": TESTS,
            "tests/test_other.py": other}  # fmt: skip
    head = {**WEAKENED_HEAD, "tests/test_other.py": None}
    result = run_audit(tmp_path, base, head)
    assert flags(result) == [("removed_assert", "test_words", 'assert slug("a  b") == "a-b"')]
    [gone] = result.candidates
    assert gone.kind == "deleted_test" and "no longer imports" in gone.why_not_flag


def test_s2_a_config_in_a_subfolder_still_matches_the_test_ids(tmp_path: Path) -> None:
    base = {"svc/pyproject.toml": PYPROJECT, "svc/src/slug.py": SLUG,
            "svc/tests/test_slug.py": TESTS}  # fmt: skip
    head = {f"svc/{k}": v for k, v in WEAKENED_HEAD.items()}
    repo = make_repo(tmp_path / "repo", [base, head])
    with Workspace(repo, "c0", "c1") as ws:
        result = audit(ws, compute_scope(ws.repo, ws.base_sha, ws.head_sha), NOT_REPRODUCED, "")
    assert [(f.kind, f.file) for f in result.flags] == [("removed_assert",
                                                         "svc/tests/test_slug.py")]  # fmt: skip


def test_s2_a_pytest_ini_added_by_the_pr_is_taken_out_for_the_old_tests(tmp_path: Path) -> None:
    head = {**WEAKENED_HEAD, "tests/pytest.ini": "[pytest]\npythonpath = ../src\n"}
    result = run_audit(tmp_path, {"src/slug.py": SLUG, "tests/test_slug.py": TESTS}, head)
    assert flags(result) == [("removed_assert", "test_words", 'assert slug("a  b") == "a-b"')]


def test_s3_a_crash_inside_the_fixed_code_is_unjudged_not_excused(tmp_path: Path) -> None:
    base_src = "def count(d, k):\n    return d.get(k, 0)\n"
    tests = "from c import count\n\n\ndef test_hit():\n    assert count({'a': 1}, 'a') == 1\n" \
            "\n\ndef test_miss():\n    assert count({}, 'a') == 0\n"  # fmt: skip
    head = {"src/c.py": base_src.replace("d.get(k, 0)", "d[k]"),
            "tests/test_c.py": tests.split("\n\n\ndef test_miss")[0] + "\n"}  # fmt: skip
    result = run_audit(tmp_path, {"src/c.py": base_src, "tests/test_c.py": tests}, head)
    assert result.status is IntegrityStatus.INCONCLUSIVE and result.flags == ()
    [found] = result.candidates
    assert found.kind == "deleted_test" and "now raises KeyError on the fixed code" in \
        found.why_not_flag  # fmt: skip


def test_round2_sf2_a_removed_check_that_now_crashes_in_the_code_is_unjudged(
    tmp_path: Path,
) -> None:
    # The crash is reported at its deepest frame (src/c.py), not at the removed check's line.
    base_src = "def count(d, k):\n    return d.get(k, 0)\n"
    tests = "from c import count\n\n\ndef test_count():\n    assert count({'a': 1}, 'a') == 1\n" \
            "    assert count({}, 'a') == 0\n"  # fmt: skip
    head = {"src/c.py": base_src.replace("d.get(k, 0)", "d[k]"),
            "tests/test_c.py": tests.replace("    assert count({}, 'a') == 0\n", "")}  # fmt: skip
    result = run_audit(tmp_path, {"src/c.py": base_src, "tests/test_c.py": tests}, head)
    assert result.status is IntegrityStatus.INCONCLUSIVE and result.flags == ()
    [found] = result.candidates
    assert found.kind == "removed_assert" and "now raises KeyError" in found.why_not_flag


def test_round2_sf1_a_bare_name_does_not_pair_a_deleted_test_with_a_new_one(
    tmp_path: Path,
) -> None:
    base_src = "def get(d, k):\n    return d.get(k, 0)\n"
    miss = "\n\ndef test_miss():\n    result = get({}, 'z')\n    assert result == 0\n"
    two = "\n\ndef test_two_keys():\n    result = len({'a': 1, 'b': 2})\n    assert result == 2\n"
    base = {"src/g.py": base_src, "tests/test_g.py": "from g import get\n" + miss}
    head = {
        "src/g.py": base_src.replace("0)", "-1)"),
        "tests/test_g.py": "from g import get\n" + two,
    }
    result = run_audit(tmp_path, base, head)
    assert flags(result) == [("deleted_test", "test_miss", "def test_miss():")]


def test_a_changed_test_helper_is_put_back_for_the_old_tests(tmp_path: Path) -> None:
    # Verifier nit: a helper's changed expected value used to hide the removed assert.
    tests = TESTS.replace("from slug import slug", "from slug import slug\nfrom helpers import AB")
    tests = tests.replace('slug("a  b") == "a-b"', 'slug("a  b") == AB')
    base = {"src/slug.py": SLUG, "tests/helpers.py": "AB = 'a-b'\n", "tests/test_slug.py": tests,
            "tests/conftest.py": "import sys, pathlib\nsys.path.insert(0, "
            "str(pathlib.Path(__file__).parent))\n"}  # fmt: skip
    head = {"src/slug.py": BROKEN, "tests/helpers.py": "AB = 'a--b'\n",
            "tests/test_slug.py": tests.replace('    assert slug("a  b") == AB\n', "")}  # fmt: skip
    result = run_audit(tmp_path, base, head)
    found = [(f.kind, f.detail) for f in result.flags]
    assert found == [("removed_assert", 'assert slug("a  b") == AB')]


def test_a_test_file_that_is_not_utf8_is_noted_not_treated_as_deleted(tmp_path: Path) -> None:
    repo = make_repo(
        tmp_path / "repo",
        [{"pyproject.toml": PYPROJECT, "src/slug.py": SLUG, "tests/test_slug.py": TESTS}, {}],
    )
    (repo / "tests" / "test_slug.py").write_bytes(TESTS.encode() + b"# \xff\xfe\n")
    make_fixtures.git(repo, "commit", "--quiet", "--no-verify", "-am", "latin-1")
    make_fixtures.git(repo, "tag", "c2")
    with Workspace(repo, "c0", "c2") as ws:
        result = audit(ws, compute_scope(ws.repo, ws.base_sha, ws.head_sha), NOT_REPRODUCED, "")
    assert result.flags == () and result.candidates == ()
    assert any("not UTF-8" in n for n in result.notes)


# --- safety ----------------------------------------------------------------------------------


def test_an_old_test_that_edits_the_users_repository_is_caught_or_blocked(
    tmp_path: Path,
) -> None:
    # The hostile test is in base and the PR deletes it, so integrity runs its old version.
    # It must be committed before any copy exists, so it targets the user's own repository.
    root = tmp_path / "repo"
    target = root / "src" / "slug.py"
    hostile = TESTS + (
        "\n\ndef test_attack():\n    import pytest\n    try:\n"
        f"        open({target.as_posix()!r}, 'a').write('# x')\n"
        "    except OSError as exc:\n"
        "        pytest.fail(f'WRITE BLOCKED errno={exc.errno}')\n"
    )
    repo = make_repo(root, [
        {"pyproject.toml": PYPROJECT, "src/slug.py": SLUG, "tests/test_slug.py": hostile},
        {"src/slug.py": BROKEN, "tests/test_slug.py": TESTS},
    ])  # fmt: skip
    before = target.read_bytes()
    with Workspace(repo, "c0", "c1") as ws:
        scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
        result = audit(ws, scope, NOT_REPRODUCED, "")
        assert ws.copies == [ws.base, ws.head]
    if LEVEL == "strict":
        import errno

        assert target.read_bytes() == before  # never written
        outputs = "".join(r.first.output for _, r in result.runs)
        assert f"WRITE BLOCKED errno={errno.ENOENT}" in outputs
        assert result.status is not IntegrityStatus.INVALID
    else:
        assert target.read_bytes() == before + b"# x"  # the write really happened...
        assert result.status is IntegrityStatus.INVALID, result.reason  # ...and was caught
        assert result.reason.startswith("during the old tests/test_slug.py before the fix")
        assert "slug.py" in result.reason and result.flags == ()


# --- matching JUnit ids (pure) ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("test_id", "qualname", "hit"),
    [
        ("tests.test_slug::test_words", "test_words", True),
        ("tests.test_slug::test_words[1-2]", "test_words", True),
        ("tests.test_slug::test_words_more", "test_words", False),
        ("tests.test_slug.TestK::test_m", "TestK.test_m", True),
        ("tests.test_slug.TestK::test_m", "test_m", False),
        ("tests.test_other::test_words", "test_words", False),
        ("tests.test_slug.TestK::test_m", None, True),
        ("tests.test_slugs::test_m", None, False),
    ],
)
def test_junit_ids_match_their_test(test_id: str, qualname: str | None, hit: bool) -> None:
    assert matches(test_id, "tests.test_slug", qualname) is hit


def test_failure_info_is_what_judge_reads() -> None:
    # judge() relies on these fields; a rename in runner.py must fail here, not silently.
    info = FailureInfo("a::b", "failure", "AssertionError", "tests/t.py:3", "msg")
    assert (info.kind, info.exc_type, info.location, info.message) == (
        "failure", "AssertionError", "tests/t.py:3", "msg")  # fmt: skip
