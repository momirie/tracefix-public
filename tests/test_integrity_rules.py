"""M5: integrity candidate rules (pure). Each rule has cases that must be found and traps that
must not be: a false candidate costs a confirmation run, a missed one hides a weakened test."""

import ast
from pathlib import Path

import make_fixtures
import pytest

from tracefix.guard import changed_lines
from tracefix.integrity_rules import (
    Candidate,
    SourceText,
    added_pragmas,
    candidates_in_tests,
    config_candidates,
    conftest_candidates,
    in_evidence,
    special_cases,
    without_branch,
)


def scan(base: str, head: str | None, path: str = "tests/test_m.py") -> list[Candidate]:
    return candidates_in_tests(SourceText(path, head, base))


def source(base: str | None, head: str, path: str = "src/m.py") -> SourceText:
    return SourceText(path, head, base, changed_lines(base or "", head))


def summary(found: list[Candidate]) -> list[tuple[str, str | None, str]]:
    return [(c.kind, c.test, c.detail) for c in found]


# --- removed and weakened checks -----------------------------------------------------------

TWO = """\
def test_a():
    assert f(1) == 2
    assert f(2) == 3
"""


def test_a_removed_assert_is_found_with_its_base_line_and_text() -> None:
    found = scan(TWO, "def test_a():\n    assert f(1) == 2\n")
    assert summary(found) == [("removed_assert", "test_a", "assert f(2) == 3")]
    assert (found[0].side, found[0].line, found[0].end_line) == ("base", 3, 3)


def test_reordered_reformatted_or_commented_checks_are_not_removed() -> None:
    reordered = "def test_a():\n    assert f(2) == 3\n    assert f(1)==2  # same check\n"
    assert scan(TWO, reordered) == []
    assert scan(TWO, "# a comment\n" + TWO) == []


def test_a_check_moved_to_another_test_in_the_file_is_not_removed() -> None:
    head = "def test_a():\n    assert f(1) == 2\n\n\ndef test_b():\n    assert f(2) == 3\n"
    assert scan(TWO, head) == []


def test_a_duplicate_check_removed_once_is_found_once() -> None:
    base = "def test_a():\n    assert g()\n    assert g()\n"
    found = scan(base, "def test_a():\n    assert g()\n")
    assert summary(found) == [("removed_assert", "test_a", "assert g()")]


@pytest.mark.parametrize(
    ("old", "new", "kind"),
    [
        ("assert f(1) == 2", "assert f(1)", "weakened_assert"),
        ("assert f(1) == 2", "assert f(1) != 3", "weakened_assert"),
        ("assert f(1) is None", "assert f(1) in (None, 0)", "weakened_assert"),
        ("assert f(1) == 2", "assert f(1) == 3", "changed_expectation"),
        ("assert f(1) < 2", "assert f(1) <= 2", "changed_expectation"),
        ("assert f(1) == approx(2, rel=1e-6)", "assert f(1) == approx(2, rel=0.5)",
         "weakened_assert"),
        ("assert f(1) == approx(2, abs=1e-6)", "assert f(1) == approx(2)", "weakened_assert"),
        ("assert f(1) == approx(2, rel=0.5)", "assert f(1) == approx(2, rel=1e-6)",
         "changed_expectation"),
        ("self.assertEqual(f(1), 2)", "self.assertTrue(f(1))", "weakened_assert"),
        ("self.assertEqual(f(1), 2)", "self.assertEqual(f(1), 5)", "changed_expectation"),
    ],
)  # fmt: skip
def test_a_replaced_check_is_classified(old: str, new: str, kind: str) -> None:
    found = scan(f"def test_a(self):\n    {old}\n", f"def test_a(self):\n    {new}\n")
    assert [(c.kind, c.detail) for c in found] == [(kind, old)]


def test_a_removed_check_with_no_partner_is_removed_even_if_another_check_was_added() -> None:
    found = scan(TWO, "def test_a():\n    assert f(1) == 2\n    assert g(9) == 9\n")
    assert summary(found) == [("removed_assert", "test_a", "assert f(2) == 3")]


def test_checks_in_nested_blocks_count() -> None:
    base = "def test_a():\n    for x in xs:\n        if x:\n            assert f(x) == x\n"
    head = "def test_a():\n    for x in xs:\n        if x:\n            pass\n"
    assert summary(scan(base, head)) == [("removed_assert", "test_a", "assert f(x) == x")]


# --- raises ------------------------------------------------------------------------------------

RAISES = "def test_r():\n    with pytest.raises({}):\n        f(-1)\n"


@pytest.mark.parametrize(
    ("old", "new", "kind"),
    [
        ("ValueError", "Exception", "broadened_raises"),
        ("ValueError", "BaseException", "broadened_raises"),
        ("ValueError", "(ValueError, TypeError)", "broadened_raises"),
        ("ValueError, match='negative'", "ValueError", "broadened_raises"),
        ("ValueError", "KeyError", "changed_expectation"),
        ("ValueError, match='a'", "ValueError, match='b'", "changed_expectation"),
    ],
)
def test_a_changed_raises_is_classified(old: str, new: str, kind: str) -> None:
    found = scan(RAISES.format(old), RAISES.format(new))
    assert [c.kind for c in found] == [kind]


def test_a_removed_raises_block_is_a_removed_check() -> None:
    found = scan(RAISES.format("ValueError"), "def test_r():\n    f(-1)\n")
    assert summary(found) == [("removed_assert", "test_r", "pytest.raises(ValueError)")]


def test_unittest_assert_raises_counts_too() -> None:
    base = "class TestX:\n    def test_r(self):\n        with self.assertRaises(ValueError):\n" \
           "            f(-1)\n"  # fmt: skip
    head = base.replace("ValueError", "Exception")
    assert summary(scan(base, head)) == [
        ("broadened_raises", "TestX.test_r", "self.assertRaises(ValueError)")
    ]


# --- deleted tests -------------------------------------------------------------------------


def test_a_deleted_test_is_found_and_a_renamed_one_is_not() -> None:
    base = TWO + "\n\ndef test_b():\n    assert g() == 1\n"
    found = scan(base, TWO)
    assert summary(found) == [("deleted_test", "test_b", "def test_b():")]
    assert (found[0].line, found[0].end_line) == (6, 7)
    renamed = TWO + "\n\ndef test_g_is_one():\n    assert g() == 1\n"
    assert scan(base, renamed) == []


def test_deleting_a_helper_or_a_non_test_class_is_not_a_deleted_test() -> None:
    base = TWO + "\n\ndef helper():\n    return 1\n\n\nclass Helper:\n    def test_x(self):\n" \
           "        assert 0\n"  # fmt: skip
    assert scan(base, TWO) == []


def test_a_deleted_file_deletes_every_test_in_it_including_class_methods() -> None:
    base = TWO + "\n\nclass TestK:\n    def test_m(self):\n        assert h()\n"
    assert [(c.kind, c.test) for c in scan(base, None)] == [
        ("deleted_test", "test_a"), ("deleted_test", "TestK.test_m")]  # fmt: skip


def test_an_added_test_file_or_unparseable_code_gives_nothing() -> None:
    assert candidates_in_tests(SourceText("tests/test_n.py", TWO, None)) == []
    assert scan("def test_a(:\n", TWO) == []
    assert scan(TWO, "def test_a(:\n") == []


def test_a_dropped_parametrize_case_is_a_removed_check() -> None:
    base = "@pytest.mark.parametrize('n', [1, 2, 3])\ndef test_p(n):\n    assert f(n)\n"
    found = scan(base, base.replace("[1, 2, 3]", "[1, 3]"))
    assert summary(found) == [("removed_assert", "test_p", "parametrize case 2 removed")]
    assert scan(base, base.replace("[1, 2, 3]", "[3, 2, 1, 4]")) == []


# --- skips ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "head",
    [
        "@pytest.mark.skip(reason='flaky')\n" + TWO,
        "@pytest.mark.xfail\n" + TWO,
        "@unittest.skipIf(True, 'x')\n" + TWO,
        "def test_a():\n    pytest.skip('later')\n    assert f(1) == 2\n    assert f(2) == 3\n",
        "pytestmark = [pytest.mark.skipif(True, reason='x')]\n\n\n" + TWO,
    ],
)
def test_a_new_skip_is_found(head: str) -> None:
    assert [c.kind for c in scan(TWO, head)] == ["added_skip"]


def test_a_skip_on_the_class_counts_for_each_of_its_tests() -> None:
    base = "class TestK:\n    def test_m(self):\n        assert h()\n"
    found = scan(base, "@pytest.mark.skip\n" + base)
    assert [(c.kind, c.test) for c in found] == [("added_skip", "TestK.test_m")]


def test_a_skip_that_was_already_there_is_not_new() -> None:
    base = "@pytest.mark.skipif(sys.platform == 'win32', reason='posix')\n" + TWO
    assert scan(base, base + "\n") == []


# --- the fixtures (ground truth) -----------------------------------------------------------


def _fixture_files(case: str, kind: str) -> list[SourceText]:
    root = make_fixtures.FIXTURES_DIR / case
    found = []
    paths = {p.relative_to(root / side).as_posix() for side in ("base", "head")
             for p in (root / side).rglob("*.py")}  # fmt: skip
    for rel in sorted(paths):
        if (rel.startswith("tests/") or "/test_" in rel) != (kind == "test"):
            continue
        base_file, head_file = root / "base" / rel, root / "head" / rel
        base = base_file.read_text("utf-8") if base_file.exists() else None
        head = head_file.read_text("utf-8") if head_file.exists() else None
        if base != head:
            fixed = changed_lines(base or "", head) if head is not None else frozenset()
            found.append(SourceText(rel, head, base, fixed))
    return found


def _evidence(case: str) -> list[str]:
    root = make_fixtures.FIXTURES_DIR / case
    tests = [p.read_text("utf-8") for p in (root / "head" / "tests").rglob("*.py")]
    return [(root / "ISSUE.md").read_text("utf-8"), *tests]


def test_only_test_weakened_has_test_candidates_among_the_fixtures() -> None:
    found = {case: [c for f in _fixture_files(case, "test") for c in candidates_in_tests(f)]
             for case in make_fixtures.CASES}  # fmt: skip
    assert summary(found.pop("test_weakened")) == [(
        "removed_assert", "test_slugify_lowercases_and_joins_words",
        'assert slugify("Rock & Roll") == "rock-roll"',
    )]  # fmt: skip
    assert {case: summary(c) for case, c in found.items() if c} == {}


def test_only_special_cased_has_special_case_candidates_among_the_fixtures() -> None:
    found = {case: [c for f in _fixture_files(case, "source")
                    for c in special_cases(f, _evidence(case))]
             for case in make_fixtures.CASES}  # fmt: skip
    hits = found.pop("special_cased")
    assert [(c.file, c.literal, c.hard_coded, c.detail) for c in hits] == [
        ("src/billing/calendar.py", 2100, True, "year == 2100 and month == 2")
    ]
    assert {case: summary(c) for case, c in found.items() if c} == {}


# --- special-casing ------------------------------------------------------------------------

BASE_SRC = """\
def days(year, month):
    if month == 2 and leap(year):
        return 29
    return 30
"""


def special(head: str, evidence: str = "see 2100 and 'Rock & Roll' and -7 and 404",
            base: str | None = BASE_SRC) -> list[Candidate]:  # fmt: skip
    return special_cases(source(base, head), [evidence])


def test_a_hard_coded_new_literal_from_the_evidence_is_a_special_case() -> None:
    head = BASE_SRC.replace("    if month", "    if year == 2100:\n        return 28\n    if month")
    [found] = special(head)
    assert (found.literal, found.hard_coded, found.detail, found.line) == (
        2100,
        True,
        "year == 2100",
        2,
    )
    assert found.branch == (2, 4)


@pytest.mark.parametrize(
    "condition",
    [
        "year >= 2100",  # ordering: a range check
        "year == 2",  # 2 is already in the base file
        "year == 1999",  # not in the evidence
        "year == 21",  # only part of a token in the evidence
        "year is None",  # trivial
        "year == 0 or year == -1",  # trivial
        "year == ''",  # trivial
        "len(year) == 1",  # trivial
    ],
)
def test_conditions_that_are_not_special_cases(condition: str) -> None:
    head = BASE_SRC.replace("    if month", f"    if {condition}:\n        return 28\n    if month")
    assert special(head) == []


def test_a_condition_outside_the_fixed_lines_is_ignored() -> None:
    base = BASE_SRC.replace("    if month", "    if year == 2100:\n        return 28\n    if month")
    assert special(base + "\n\nX = 1\n", base=base) == []


def test_a_branch_that_does_more_than_return_a_literal_is_not_hard_coded() -> None:
    head = BASE_SRC.replace("    if month", "    if year == 2100:\n        log(year)\n"
                            "        return 28\n    if month")  # fmt: skip
    assert [(c.literal, c.hard_coded) for c in special(head)] == [(2100, False)]


@pytest.mark.parametrize(
    ("snippet", "literal", "hard_coded"),
    [
        ("    if month == 1:\n        pass\n    elif year == 2100:\n        return 28\n",
         2100, True),
        ("    x = 28 if year == 2100 else 29\n", 2100, True),
        ("    if year in (2100, 2300):\n        return (28, 'feb')\n", 2100, True),
        ("    if title == 'Rock & Roll':\n        return 'rock-roll'\n", "Rock & Roll", True),
        ("    if year == -7:\n        return -1\n", -7, True),
        ("    while year != 404:\n        year += 1\n", 404, False),
        ("    xs = [y for y in ys if y != 404]\n", 404, False),
        ("    match year:\n        case 2100:\n            return 28\n", 2100, True),
    ],
)  # fmt: skip
def test_every_kind_of_condition_is_read(snippet: str, literal: object, hard_coded: bool) -> None:
    head = BASE_SRC.replace("    if month", snippet + "    if month")
    found = special(head)
    assert [(c.literal, c.hard_coded) for c in found][:1] == [(literal, hard_coded)]


@pytest.mark.parametrize(
    ("value", "text", "hit"),
    [
        (2100, "29 Feb 2100.", True),
        (2100, "'2100-02-28'", True),
        (2100, "21000", False),
        (2100, "x2100", False),
        (2100, "3.2100", False),
        (2.5, "a 2.5 b", True),
        (-7, "got -7 back", True),
        (-7, "a-7", False),
        ("Rock & Roll", 'slugify("Rock & Roll")', True),
        ("x", "x", False),  # one-character strings are everywhere
        (b"ab", "ab", True),
    ],
)
def test_literals_match_the_evidence_as_whole_tokens(value: object, text: str, hit: bool) -> None:
    assert in_evidence(value, [text]) is hit  # type: ignore[arg-type]


# --- cutting a branch out ------------------------------------------------------------------


def _functions(text: str) -> list[str]:
    return [ast.dump(n) for n in ast.parse(text).body if isinstance(n, ast.FunctionDef)
            and n.name != "days"]  # fmt: skip


@pytest.mark.parametrize(
    ("head", "expected"),
    [
        ("def days(y):\n    if y == 2100:\n        return 28\n    return 29\n",
         "def days(y):\n    pass\n    return 29"),
        ("def days(y):\n    if y == 2100:\n        return 28\n    else:\n        return 29\n",
         "def days(y):\n    return 29"),
        ("def days(y):\n    if y == 1:\n        return 1\n    elif y == 2100:\n        return 28\n"
         "    return 29\n",  # the elif's place keeps an empty else: same behaviour
         "def days(y):\n    if y == 1:\n        return 1\n    else:\n        pass\n    return 29"),
        ("def days(y):\n    return 28 if y == 2100 else 29\n", "def days(y):\n    return 29"),
        ("def days(y):\n    match y:\n        case 2100:\n            return 28\n"
         "        case 1:\n            return 1\n",
         "def days(y):\n    match y:\n        case 1:\n            return 1"),
    ],
)  # fmt: skip
def test_without_branch_removes_exactly_that_branch(head: str, expected: str) -> None:
    [found] = [c for c in special(head, "2100", base=None) if c.literal == 2100]
    assert found.branch is not None
    rest = "\n\ndef other(y):\n    if y == 2100:\n        return 1\n    return 0\n"
    cut = without_branch(head + rest, *found.branch)
    assert cut is not None and cut.startswith(expected)
    assert _functions(cut) == _functions(head + rest)  # nothing else changed


def test_without_branch_gives_none_when_nothing_is_there() -> None:
    assert without_branch("x = 1\n", 1, 0) is None
    assert without_branch("def f(:\n", 1, 0) is None


# --- report only: collection and pragmas ---------------------------------------------------


def test_conftest_and_config_changes_to_collection_are_noted() -> None:
    conf = SourceText("tests/conftest.py", "collect_ignore = ['test_slug.py']\n", "X = 1\n")
    assert [c.kind for c in conftest_candidates(conf)] == ["collection_changed"]
    same = SourceText("tests/conftest.py", "collect_ignore = []\n", "collect_ignore = []\n")
    assert conftest_candidates(same) == []
    hook = "def pytest_collection_modifyitems(items):\n    items.clear()\n"
    assert [c.kind for c in conftest_candidates(SourceText("conftest.py", hook, None))] == [
        "collection_changed"]  # fmt: skip
    toml = '[tool.pytest.ini_options]\naddopts = "-q"\n'
    hiding = toml.replace('"-q"', '"-q --deselect tests/test_slug.py::test_a"')
    assert [c.detail for c in config_candidates(SourceText("pyproject.toml", hiding, toml))] == [
        "pytest option addopts changed"]  # fmt: skip
    assert config_candidates(SourceText("pyproject.toml", toml + "xfail_strict = true\n",
                                        toml)) == []  # fmt: skip
    ini = "[pytest]\ntestpaths = tests\n"
    assert [c.detail for c in config_candidates(
        SourceText("pytest.ini", ini.replace("tests", "tests/unit"), ini))] == [
        "pytest option testpaths changed"]  # fmt: skip
    assert config_candidates(SourceText("pyproject.toml", "[project]\nname='x'\n", None)) == []


def test_a_new_pragma_on_a_fixed_line_is_noted() -> None:
    head = BASE_SRC.replace("return 30", "return 30  # pragma: no cover")
    assert [c.kind for c in added_pragmas(source(BASE_SRC, head))] == ["added_pragma"]
    assert added_pragmas(source(head, head + "\nX = 1\n")) == []


# --- M5 verifier review: false flags (B1, B2) and hiding without a candidate (S4) ------------

RND = "@pytest.mark.parametrize('x, want', [{}, (1.0, 1)])\ndef test_rnd(x, want):\n" \
      "    assert rnd(x) == want\n"  # fmt: skip


@pytest.mark.parametrize(("old", "new"), [("(2.5, 2)", "(2.5, 3)"),
                                          ("pytest.param(2.5, 2, id='half')",
                                           "pytest.param(2.5, 3, id='half')")])  # fmt: skip
def test_b1_a_corrected_parametrize_value_is_a_changed_expectation(old: str, new: str) -> None:
    found = scan(RND.format(old), RND.format(new))
    assert [(c.kind, c.detail) for c in found] == [
        ("changed_expectation", f"parametrize case {old} changed")]  # fmt: skip


def test_b2_a_renamed_test_with_a_corrected_value_is_compared_check_by_check() -> None:
    base = "def test_rnd():\n    assert rnd(2.5) == 2\n    assert rnd(1.0) == 1\n"
    head = "def test_rnd_half_up():\n    assert rnd(2.5) == 3\n    assert rnd(1.0) == 1\n"
    assert summary(scan(base, head)) == [
        ("changed_expectation", "test_rnd", "assert rnd(2.5) == 2")
    ]
    unrelated = "def test_other():\n    assert g() == 1\n"
    assert [c.kind for c in scan(base, unrelated)] == ["deleted_test"]


@pytest.mark.parametrize(
    "head",
    [
        "def test_a():\n    with contextlib.suppress(AssertionError):\n"
        "        assert f(1) == 2\n    assert f(2) == 3\n",
        "def test_a():\n    if False:\n        assert f(1) == 2\n    assert f(2) == 3\n",
        "def test_a():\n    assert f(2) == 3\n    return\n    assert f(1) == 2\n",
        "def test_a():\n    try:\n        assert f(1) == 2\n    except AssertionError:\n"
        "        pass\n    assert f(2) == 3\n",
    ],
)
def test_s4_an_old_check_hidden_by_its_surroundings_is_a_weakened_check(head: str) -> None:
    assert summary(scan(TWO, head)) == [
        ("weakened_assert", "test_a", "assert f(1) == 2 (now inside other code)")
    ]


def test_s4_a_check_moved_into_a_skipped_test_is_still_removed() -> None:
    head = "def test_a():\n    assert f(2) == 3\n\n\n@pytest.mark.skip\ndef test_b():\n" \
           "    assert f(1) == 2\n"  # fmt: skip
    assert summary(scan(TWO, head)) == [("removed_assert", "test_a", "assert f(1) == 2")]


def test_s4_a_skip_through_an_alias_is_a_new_skip() -> None:
    head = "later = pytest.mark.skip\n\n\n@later\n" + TWO
    assert [(c.kind, c.test) for c in scan(TWO, head)] == [("added_skip", "test_a")]


def test_unittest_classes_count_whatever_their_name() -> None:
    base = "class SlugChecks(unittest.TestCase):\n    def test_x(self):\n" \
           "        self.assertEqual(slug('A'), 'a')\n"  # fmt: skip
    found = scan(base, "class SlugChecks(unittest.TestCase):\n    pass\n")
    assert [(c.kind, c.test) for c in found] == [("deleted_test", "SlugChecks.test_x")]


def test_the_fixture_files_exist() -> None:
    # Guards the two fixture tests above against passing on an empty listing.
    assert any(f.path == "tests/test_slug.py" for f in _fixture_files("test_weakened", "test"))
    assert Path(make_fixtures.FIXTURES_DIR / "special_cased" / "ISSUE.md").exists()
