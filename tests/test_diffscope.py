"""M2: diff scope over the fixtures and small synthetic repos."""

from pathlib import Path

import make_fixtures
import pytest
from conftest import make_repo

from tracefix.diffscope import (
    ChangeKind,
    DiffScope,
    FileKind,
    Hunk,
    classify,
    compute_scope,
    function_spans,
    parse_hunks,
    parse_name_status,
)
from tracefix.workspace import resolve_ref

A, M, R = ChangeKind.ADDED, ChangeKind.MODIFIED, ChangeKind.REMOVED

# Per fixture: changed source functions, changed test functions, and .py files with
# module-level changes. Read off each case's base/ vs head/ diff.
EXPECTED: dict[str, dict[str, set[tuple[str, str, ChangeKind]] | set[str]]] = {
    "env_broken": {
        "source": {("src/metrics/report.py", "iso_week", M)},
        "test": set(),
        "module_level": {"src/metrics/report.py"},  # `timedelta` import dropped
    },
    "good_fix": {
        "source": {("src/pager/pagination.py", "total_pages", M)},
        "test": {("tests/test_pagination.py", "test_total_pages_partial_last_page", A)},
        "module_level": set(),
    },
    "method_good": {
        "source": {("src/vtools/version.py", "Version.bump", M)},
        "test": {("tests/test_version.py", "test_bump_minor_resets_patch", A)},
        "module_level": set(),
    },
    "method_partial": {
        "source": {("src/gateway/listener.py", "Listener.port", M)},
        "test": {("tests/test_listener.py", "test_port_defaults_when_unset", A)},
        "module_level": set(),
    },
    "no_fix": {
        "source": {("src/crm/contacts.py", "dedupe_emails", M)},
        "test": {("tests/test_contacts.py", "test_dedupe_ignores_surrounding_whitespace", A)},
        "module_level": set(),
    },
    "partial_fix": {
        "source": {("src/svc/config.py", "parse_port", M)},
        "test": {("tests/test_config.py", "test_parse_port_defaults_when_unset", A)},
        "module_level": set(),
    },
    "special_cased": {
        "source": {("src/billing/calendar.py", "days_in_month", M)},
        "test": set(),
        "module_level": set(),
    },
    "test_weakened": {
        "source": {("src/blog/slug.py", "slugify", M)},
        "test": {("tests/test_slug.py", "test_slugify_lowercases_and_joins_words", M)},
        "module_level": {"src/blog/slug.py"},  # _SEPARATORS regex replaced by _UNSAFE
    },
    "unguarded_test": {
        "source": {("src/textutil/trunc.py", "truncate", M)},
        "test": {("tests/test_trunc.py", "test_truncate_adds_ellipsis", A)},
        "module_level": set(),
    },
    "wrong_but_green": {
        "source": {("src/stats/buckets.py", "bucket_of", M)},
        "test": {("tests/test_buckets.py", "test_bucket_of_large_values", A)},
        "module_level": set(),
    },
}


def scope_of(repo: Path, base: str, head: str) -> DiffScope:
    return compute_scope(repo, resolve_ref(repo, base), resolve_ref(repo, head))


def test_every_fixture_has_an_expectation() -> None:
    assert set(EXPECTED) == set(make_fixtures.CASES)


@pytest.mark.parametrize("case", sorted(EXPECTED))
def test_fixture_scope(case: str, built: dict[str, Path]) -> None:
    scope = scope_of(built[case], "base", "head")
    want = EXPECTED[case]
    assert {(f.path, f.qualname, f.change) for f in scope.source_functions} == want["source"]
    assert {(f.path, f.qualname, f.change) for f in scope.test_functions} == want["test"]
    assert set(scope.module_level) == want["module_level"]
    assert scope.unparseable == ()
    # The test/source split covers every changed file, and each file has its hunks.
    for change in scope.files:
        assert change.status == "M"
        assert change.hunks
    assert {f.path for f in scope.source_files} == {p for p, _, _ in want["source"]}
    assert {f.path for f in scope.test_files} == {p for p, _, _ in want["test"]}


def test_partial_fix_hunk_is_the_two_inserted_lines(built: dict[str, Path]) -> None:
    scope = scope_of(built["partial_fix"], "base", "head")
    (source,) = scope.source_files
    assert source.hunks == (Hunk(base_start=33, base_len=0, head_start=34, head_len=2),)
    (fn,) = scope.source_functions
    assert fn.head_span is not None and fn.head_span[0] <= 34 and fn.head_span[1] >= 35


# --- synthetic repos --------------------------------------------------------------------------

BASE_SRC = """\
import functools


class Parser:
    def parse(self, text):
        return text.split()

    def unchanged(self):
        return 1


@functools.cache
def decorated(x):
    return x + 1


def outer():
    def inner():
        return 1
    return inner()


def going_away():
    return 0
"""

HEAD_SRC = """\
import functools


class Parser:
    def parse(self, text):
        return text.split(",")

    def unchanged(self):
        return 1


@functools.lru_cache(maxsize=None)
def decorated(x):
    return x + 1


def outer():
    def inner():
        return 2
    return inner()


def brand_new():
    return 3
"""


def test_methods_decorators_nested_added_and_removed(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "r", [{"pkg/mod.py": BASE_SRC}, {"pkg/mod.py": HEAD_SRC}])
    scope = scope_of(repo, "c0", "c1")
    changes = {(f.qualname, f.change) for f in scope.functions}
    assert changes == {
        ("Parser.parse", M),
        ("decorated", M),  # only its decorator line changed
        ("outer.inner", M),  # innermost function gets the change, not `outer`
        ("going_away", R),
        ("brand_new", A),
    }
    assert scope.module_level == ()
    removed = next(f for f in scope.functions if f.change is R)
    assert removed.head_span is None and removed.base_span is not None


def test_added_deleted_renamed_and_non_python_files(tmp_path: Path) -> None:
    body = "def f():\n    return 1\n\n\ndef g():\n    return 2\n" + "# padding\n" * 20
    repo = make_repo(
        tmp_path / "r",
        [
            {"old_name.py": body, "gone.py": "def bye():\n    pass\n", "README.md": "a\n"},
            {
                "old_name.py": None,
                "new_name.py": body.replace("return 2", "return 3"),
                "gone.py": None,
                "added.py": "def hi():\n    pass\n",
                "README.md": "b\n",
            },
        ],
    )
    scope = scope_of(repo, "c0", "c1")
    by_path = {f.path: f for f in scope.files}
    assert by_path["new_name.py"].status == "R"
    assert by_path["new_name.py"].old_path == "old_name.py"
    assert by_path["gone.py"].status == "D"
    assert by_path["added.py"].status == "A"
    assert by_path["README.md"].kind is FileKind.OTHER
    assert {(f.path, f.qualname, f.change) for f in scope.functions} == {
        ("new_name.py", "g", M),  # a rename with one edited line, not a whole new file
        ("gone.py", "bye", R),
        ("added.py", "hi", A),
    }


def test_syntax_error_side_is_reported_not_raised(tmp_path: Path) -> None:
    repo = make_repo(
        tmp_path / "r",
        [{"a.py": "def f():\n    return 1\n"}, {"a.py": "def f(:\n    return 1\n"}],
    )
    scope = scope_of(repo, "c0", "c1")
    assert scope.unparseable == ("a.py",)
    assert scope.functions == ()
    assert [f.path for f in scope.files] == ["a.py"]


def test_module_level_change_outside_functions(tmp_path: Path) -> None:
    repo = make_repo(
        tmp_path / "r",
        [
            {"a.py": "LIMIT = 1\n\n\ndef f():\n    return LIMIT\n"},
            {"a.py": "LIMIT = 2\n\n\ndef f():\n    return LIMIT\n"},
        ],
    )
    scope = scope_of(repo, "c0", "c1")
    assert scope.module_level == ("a.py",)
    assert scope.functions == ()


def test_unicode_and_spaces_in_paths(tmp_path: Path) -> None:
    repo = make_repo(
        tmp_path / "r",
        [{"src/dir with space/modulé.py": "def f():\n    return 'é'\n"},
         {"src/dir with space/modulé.py": "def f():\n    return 'è'\n"}],
    )  # fmt: skip
    scope = scope_of(repo, "c0", "c1")
    assert [(f.path, f.qualname) for f in scope.functions] == [
        ("src/dir with space/modulé.py", "f")
    ]


# --- pure helpers -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "kind"),
    [
        ("src/pkg/mod.py", FileKind.SOURCE),
        ("test_mod.py", FileKind.TEST),
        ("src/pkg/mod_test.py", FileKind.TEST),
        ("conftest.py", FileKind.TEST),
        ("src/pkg/conftest.py", FileKind.TEST),
        ("tests/helpers.py", FileKind.TEST),
        ("pkg/tests/data/input.json", FileKind.TEST),
        ("tests.py", FileKind.SOURCE),
        ("src/testing_utils.py", FileKind.SOURCE),
        ("src/contest.py", FileKind.SOURCE),
        ("README.md", FileKind.OTHER),
        ("pyproject.toml", FileKind.OTHER),
    ],
)
def test_classify(path: str, kind: FileKind) -> None:
    assert classify(path) is kind


def test_parse_name_status() -> None:
    raw = "M\0a.py\0R087\0old.py\0new.py\0D\0gone.py\0A\0dir with space/x.py\0"
    assert parse_name_status(raw) == [
        ("M", None, "a.py"),
        ("R", "old.py", "new.py"),
        ("D", None, "gone.py"),
        ("A", None, "dir with space/x.py"),
    ]
    assert parse_name_status("") == []


def test_parse_hunks_defaults_length_to_one() -> None:
    diff = "@@ -5 +5 @@ def f():\n-a\n+b\n@@ -10,0 +11,3 @@\n+x\n+y\n+z\n@@ -20,2 +23,0 @@\n"
    assert parse_hunks(diff) == (Hunk(5, 1, 5, 1), Hunk(10, 0, 11, 3), Hunk(20, 2, 23, 0))


def test_function_spans_include_decorators() -> None:
    spans = function_spans(
        b"@d\n@e\ndef f():\n    pass\n\nclass C:\n    async def g(self):\n        pass\n"
    )
    assert spans == {("f", 0): (1, 4), ("C.g", 0): (7, 8)}


def test_blank_and_comment_lines_are_not_module_level_changes(tmp_path: Path) -> None:
    before = "X = 1\n\n\ndef f():\n    return X\n"
    after = "# a new comment\nX = 1\n\n\n\ndef f():\n    return X\n"
    repo = make_repo(tmp_path / "r", [{"a.py": before}, {"a.py": after}])
    scope = scope_of(repo, "c0", "c1")
    assert scope.module_level == ()
    assert scope.functions == ()


# --- regressions from the M2 verifier review --------------------------------------------------


def test_users_git_config_does_not_change_the_hunks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lines = [f"def {n}():\n    return {i}\n\n\n" for i, n in enumerate("fgh")]
    before = "".join(lines)
    after = before.replace("return 0", "return 10").replace("return 2", "return 12")
    repo = make_repo(tmp_path / "r", [{"a.py": before}, {"a.py": after}])
    home = tmp_path / "home"
    home.mkdir()
    (home / ".gitconfig").write_text("[diff]\n\tinterHunkContext = 10\n\tnoprefix = true\n")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    make_fixtures.git(repo, "config", "diff.interHunkContext", "10")  # repo-local too
    scope = scope_of(repo, "c0", "c1")
    assert {f.qualname for f in scope.functions} == {"f", "h"}


def test_binary_attribute_cannot_hide_a_python_change(tmp_path: Path) -> None:
    repo = make_repo(
        tmp_path / "r",
        [
            {"a.py": "def f():\n    return 1\n"},
            {"a.py": "def f():\n    return 2\n", ".gitattributes": "*.py -diff\n"},
        ],
    )
    scope = scope_of(repo, "c0", "c1")
    assert [(f.qualname, f.change) for f in scope.functions] == [("f", M)]


PROPERTY_BASE = """\
class C:
    @property
    def x(self):
        return self._x

    @x.setter
    def x(self, value):
        self._x = value
"""


def test_property_setter_change_is_found(tmp_path: Path) -> None:
    after = PROPERTY_BASE.replace("self._x = value", "self._x = int(value)")
    repo = make_repo(tmp_path / "r", [{"a.py": PROPERTY_BASE}, {"a.py": after}])
    scope = scope_of(repo, "c0", "c1")
    assert [(f.qualname, f.occurrence, f.change) for f in scope.functions] == [("C.x", 1, M)]
    assert scope.module_level == ()


def test_second_definition_in_if_else_is_found(tmp_path: Path) -> None:
    before = (
        "import sys\n\nif sys.platform == 'win32':\n    def f():\n        return 1\n"
        "else:\n    def f():\n        return 2\n"
    )
    after = before.replace("return 2", "return 3")
    repo = make_repo(tmp_path / "r", [{"a.py": before}, {"a.py": after}])
    scope = scope_of(repo, "c0", "c1")
    assert [(f.qualname, f.occurrence, f.change) for f in scope.functions] == [("f", 1, M)]


TWO_TESTS = "def test_a():\n    assert 1\n\n\ndef test_b():\n    assert 2\n"


def test_test_file_renamed_to_non_python_is_a_test_change(tmp_path: Path) -> None:
    repo = make_repo(
        tmp_path / "r",
        [
            {"tests/test_x.py": TWO_TESTS},
            {"tests/test_x.py": None, "disabled/test_x.txt": TWO_TESTS},
        ],
    )
    scope = scope_of(repo, "c0", "c1")
    (change,) = scope.files
    assert (change.status, change.old_path, change.kind) == ("R", "tests/test_x.py", FileKind.TEST)
    assert {(f.path, f.qualname, f.change) for f in scope.test_functions} == {
        ("tests/test_x.py", "test_a", R),
        ("tests/test_x.py", "test_b", R),
    }


def test_test_file_moved_into_source_is_still_a_test_change(tmp_path: Path) -> None:
    repo = make_repo(
        tmp_path / "r",
        [{"tests/test_x.py": TWO_TESTS}, {"tests/test_x.py": None, "src/helper.py": TWO_TESTS}],
    )
    scope = scope_of(repo, "c0", "c1")
    assert [f.kind for f in scope.files] == [FileKind.TEST]


def test_utf8_bom_file_is_parsed(tmp_path: Path) -> None:
    before = "﻿def f():\n    return 1\n"
    repo = make_repo(tmp_path / "r", [{"a.py": before}, {"a.py": before.replace("1", "2")}])
    scope = scope_of(repo, "c0", "c1")
    assert scope.unparseable == ()
    assert [f.qualname for f in scope.functions] == ["f"]


def test_form_feed_does_not_shift_line_numbers(tmp_path: Path) -> None:
    before = "\x0c\nX = 1\n# old comment\n\n\ndef f():\n    return X\n"
    after = before.replace("# old comment", "# new comment")
    repo = make_repo(tmp_path / "r", [{"a.py": before}, {"a.py": after}])
    scope = scope_of(repo, "c0", "c1")
    assert scope.module_level == ()


def test_bare_cr_line_endings_are_unparseable(tmp_path: Path) -> None:
    before = "def f():\r    return 1\r\rX = 1\r"
    repo = make_repo(tmp_path / "r", [{"a.py": before}, {"a.py": before.replace("X = 1", "X = 2")}])
    scope = scope_of(repo, "c0", "c1")
    assert scope.unparseable == ("a.py",)
