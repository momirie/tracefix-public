"""M6: executable lines and fix-line coverage of the guarding tests (report only, 6 Oct 2026)."""

from pathlib import Path

import make_fixtures
from conftest import make_repo

from tracefix.diffscope import compute_scope
from tracefix.linetrace import executable_lines, fix_line_coverage
from tracefix.repro import ReproResult, ReproStatus
from tracefix.workspace import Workspace

CODE = '''\
"""Module docstring."""

LIMIT = 3


def f(x: int) -> int:
    """Docstring."""
    # a comment
    if x > LIMIT:
        return LIMIT

    return x


class C:
    size = 2

    def g(self) -> int:
        return self.size
'''


def test_executable_lines_skip_comments_blank_lines_and_docstrings() -> None:
    every = executable_lines(CODE, "m.py")
    bodies = executable_lines(CODE, "m.py", bodies_only=True)
    assert bodies == {9, 10, 12, 19}  # what a call can run; no `def` lines, nothing at import
    assert {3, 6, 15, 16, 18} <= every and bodies <= every  # import-time lines too
    assert not every & {7, 8, 11}  # docstring, comment, blank
    assert executable_lines("def broken(:\n", "m.py") == frozenset()


def reproduced(code: str) -> ReproResult:
    return ReproResult(ReproStatus.REPRODUCED, "", "tests/test_tracefix_repro.py", code, (), ())


def test_good_fixs_repro_and_pr_tests_both_run_its_one_fix_line(built: dict[str, Path]) -> None:
    oracle = make_fixtures.FIXTURES_DIR / "good_fix" / "oracle" / "test_repro.py"
    with Workspace(built["good_fix"], "base", "head") as ws:
        scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
        coverage = fix_line_coverage(ws, scope, reproduced(oracle.read_text(encoding="utf-8")))
        assert ws.copies == [ws.base, ws.head]
    assert coverage.lines == {"src/pager/pagination.py": frozenset({27})}
    assert coverage.summary("repro") == (1, 1) and coverage.summary("pr_test") == (1, 1)
    assert [name for name, _ in coverage.runs] == ["repro", "pr_test"]
    assert not coverage.notes


def test_a_fix_line_no_test_reaches_is_reported(tmp_path: Path) -> None:
    base = {
        "pyproject.toml": '[tool.pytest.ini_options]\npythonpath = ["."]\n',
        "m.py": "def f(x: int) -> int:\n    return x\n",
        "tests/test_m.py": "from m import f\n\n\ndef test_f():\n    assert f(1) == 1\n",
    }
    head = {
        "m.py": "def f(x: int) -> int:\n    if x < 0:\n        return 0\n    return x\n",
        "tests/test_m.py": "from m import f\n\n\ndef test_f():\n    assert f(2) == 2\n",
    }
    repo = make_repo(tmp_path / "repo", [base, head])
    with Workspace(repo, "c0", "c1") as ws:
        scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
        not_reproduced = ReproResult(ReproStatus.NOT_REPRODUCED, "", "t.py", None, (), ())
        coverage = fix_line_coverage(ws, scope, not_reproduced)
    assert coverage.lines == {"m.py": frozenset({2, 3})}
    assert coverage.summary("pr_test") == (1, 2)  # `if x < 0` runs, `return 0` never does
    assert "repro" not in coverage.covered  # no reproduction test to run


def test_import_time_value_lines_leave_out_imports_defs_and_docstrings() -> None:
    from tracefix.linetrace import import_time_value_lines

    text = '''\
"""Module docstring."""
import re
from math import pi

PATTERN = re.compile(r"\\d+")


@decorate(1)
def f(x: int = LIMIT * 2) -> int:
    return x


class Box:
    """Doc."""

    SIZE = 4

    def get(self) -> int:
        return self.SIZE
'''
    lines = import_time_value_lines(text)
    assert {5, 8, 9, 16} <= lines  # the constant, the decorator, the default, a class attribute
    assert lines.isdisjoint({1, 2, 3, 10, 13, 14, 18, 19})  # docstrings, imports, def/class, bodies
    assert import_time_value_lines("def (:") == frozenset()


TWYN_BASE = '''\
"""Trusted package references."""
from abc import abstractmethod
from typing import Any

LIMIT = 3


class Reference:
    """A source of trusted packages."""

    DEFAULT_SOURCE: str = "https://example.org/a.json"

    @staticmethod
    @abstractmethod
    def _parse(packages_json: dict[str, Any]) -> set[str]:
        """Parse the packages within the given json structure."""

    @staticmethod
    @abstractmethod
    def normalize_packages(packages: set[str]) -> set[str]:
        """Normalize package names."""

    def get_packages(self) -> set[str]:
        return self.normalize_packages(self._parse({}))
'''
# The twyn-317 fix (M10): `_parse` removed, the caller's body rewritten, an import added.
TWYN_HEAD = (
    TWYN_BASE.replace(
        "from typing import Any\n", "from typing import Any\nfrom json import loads\n"
    )
    .replace(
        "    @staticmethod\n    @abstractmethod\n    def _parse(packages_json: dict[str, Any])"
        ' -> set[str]:\n        """Parse the packages within the given json structure."""\n\n',
        "",
    )
    .replace("self._parse({})", "set(loads('[]'))")
)


def test_m11_a_removed_marked_method_is_all_that_changed_at_import() -> None:
    from tracefix.linetrace import removed_marked_defs

    assert "_parse" not in TWYN_HEAD
    assert removed_marked_defs(TWYN_BASE, TWYN_HEAD) == {"_parse"}
    module_level = (
        "def old(x: int = 1) -> int:\n    return x\n\n\ndef keep() -> int:\n    return 2\n"
    )
    assert removed_marked_defs(module_level, module_level.split("\n\n\n")[1]) == {"old"}


def test_m11_any_other_import_time_change_is_not_only_a_removal() -> None:
    from tracefix.linetrace import removed_marked_defs

    changes = {
        "a constant": TWYN_HEAD.replace("LIMIT = 3", "LIMIT = 4"),
        "a class attribute": TWYN_HEAD.replace("a.json", "b.json"),
        "a kept decorator": TWYN_HEAD.replace(
            "    @abstractmethod\n    def normalize", "    def normalize"
        ),
        "an added function": TWYN_HEAD + "\n\ndef extra() -> None:\n    pass\n",
        "a module statement": TWYN_HEAD + "\nprint(LIMIT)\n",
        "a default": TWYN_HEAD.replace("def get_packages(self)", "def get_packages(self, n=LIMIT)"),
    }
    for what, head in changes.items():
        assert removed_marked_defs(TWYN_BASE, head) == frozenset(), what
    assert removed_marked_defs(TWYN_BASE, TWYN_BASE) == frozenset()  # nothing removed
    assert removed_marked_defs(TWYN_BASE, "def (:") == frozenset()


def test_m11_a_removed_function_that_computed_or_registered_something_is_not_a_marker() -> None:
    from tracefix.linetrace import removed_marked_defs

    keep = "\n\ndef keep() -> int:\n    return 2\n"
    for removed in (
        "@app.route('/x')\ndef old() -> None:\n    pass\n",  # a decorator call registers it
        "@register\ndef old() -> None:\n    pass\n",  # any other decorator may too
        "def old(x: list = make()) -> None:\n    pass\n",  # a default computed at import
        "def old(x: lookup('t')) -> None:\n    pass\n",  # an annotation computed at import
        "class Old:\n    pass\n",  # a class (subclass hooks, registries)
        "OLD = 1\n",
        # Python calls special methods without any source naming them (verifier, M11 early).
        "def __getattr__(name: str) -> int:\n    return 1\n",
        "async def __aenter__() -> None:\n    pass\n",
    ):
        assert removed_marked_defs(removed + keep, keep.lstrip()) == frozenset(), removed


def test_m11_a_removed_special_method_is_not_a_marker() -> None:
    from tracefix.linetrace import removed_marked_defs

    head = "class A:\n    def keep(self):\n        pass\n"
    for dunder in ("__eq__(self, other)", "__post_init__(self)", "__init_subclass__(cls)"):
        base = f"class A:\n    def {dunder}:\n        pass\n\n    def keep(self):\n        pass\n"
        assert removed_marked_defs(base, head) == frozenset(), dunder


def test_m11_dynamic_lookups_are_seen() -> None:
    from tracefix.linetrace import dynamic_lookup

    assert not dynamic_lookup(TWYN_HEAD)
    for code in ("getattr(x, n)", "vars(x)", "x.__dict__", "inspect.getmembers(x)", "dir()",
                 "globals()", "hasattr(x, 'a')"):  # fmt: skip
        assert dynamic_lookup(code + "\n"), code
    assert dynamic_lookup("def (:")
