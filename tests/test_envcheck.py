"""M8 step 4: the run environment. Package roots, the paths plugin that puts the copy's code ahead
of installed packages, the origin check, project pytest plugins and the suite timeout."""

import os
import shutil
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

import make_fixtures
import pytest
from conftest import make_repo
from hypothesis import given
from hypothesis import strategies as st

from tracefix.diffscope import compute_scope
from tracefix.envcheck import changed_modules, module_name, origin_check
from tracefix.isolation import check_environment, run_checked
from tracefix.runner import EnvStatus, Outcome
from tracefix.workspace import MAX_IMPORT_ROOTS, RunSettings, Workspace, package_roots

FIXTURE = (make_fixtures.tag_ref("base"), make_fixtures.tag_ref("head"))

# --- package roots -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("files", "roots"),
    [
        (["src/pkg/__init__.py", "src/pkg/m.py"], ["src"]),
        (["pkg/__init__.py", "pkg/sub/__init__.py"], ["."]),
        (["lib/a/__init__.py", "pkg/__init__.py", "x/y/b/__init__.py"], [".", "lib", "x/y"]),
        (["tests/__init__.py", "tests/helpers/__init__.py", "src/tests/__init__.py"], []),
        ([".venv/lib/site-packages/dep/__init__.py", ".hidden/p/__init__.py"], []),
        (["env2/pyvenv.cfg", "env2/Lib/x/dep/__init__.py"], []),
        (["build/lib/pkg/__init__.py", "dist/pkg/__init__.py", "venv/dep/__init__.py"], []),
        (["src/nspkg/m.py"], []),  # a namespace package: no __init__.py, no root
        (["__init__.py", "m.py"], []),
        # Single-module layouts: the copy or src holds a top-level module.
        (["slug.py", "tests/test_slug.py"], ["."]),
        (["src/slug.py", "setup.py", "README.md"], ["src"]),
        (["src/__init__.py", "src/m.py"], ["."]),  # src is a package here
        (["setup.py", "conftest.py", "noxfile.py", "test_x.py", "x_test.py", "docs/conf.py"], []),
    ],
)
def test_package_roots(files: list[str], roots: list[str]) -> None:
    assert package_roots(files) == roots


_NAME = st.sampled_from(["a", "b", "src", "tests", ".v", "build", "__init__.py", "pyvenv.cfg"])


@given(st.sets(st.lists(_NAME, min_size=1, max_size=4).map("/".join), max_size=12))
def test_package_roots_follow_the_rule(files: set[str]) -> None:
    """Every root holds a top-level package outside the skipped folders; every such package's
    folder is a root; shallowest first."""
    roots = package_roots(files)

    def skipped(folder: str) -> bool:
        parts = folder.split("/")
        return any(
            p.startswith(".") or p in ("build", "tests")
            or "/".join([*parts[: i + 1], "pyvenv.cfg"]) in files
            for i, p in enumerate(parts)
        )  # fmt: skip

    top_level = set()
    for f in files:
        folder, _, name = f.rpartition("/")
        if name != "__init__.py" or not folder or skipped(folder):
            continue
        parent = folder.rpartition("/")[0]
        if f"{parent}/__init__.py".lstrip("/") not in files:
            top_level.add(parent or ".")
    assert set(roots) == top_level
    depths = [0 if r == "." else r.count("/") + 1 for r in roots]
    assert depths == sorted(depths)


@pytest.mark.parametrize(
    ("path", "roots", "name"),
    [
        ("src/pkg/m.py", ["src"], "pkg.m"),
        ("src/pkg/__init__.py", ["src"], "pkg"),
        ("src/pkg/m.py", [".", "src"], "pkg.m"),  # the deepest root that holds it
        ("pkg/m.py", ["."], "pkg.m"),
        ("scripts/run.py", ["src"], None),  # not under a root
        ("src/pkg/__main__.py", ["src"], None),  # importing it would run the program
        ("src/pkg/my-mod.py", ["src"], None),
        ("src/pkg/data.txt", ["src"], None),
    ],
)
def test_module_name(path: str, roots: list[str], name: str | None) -> None:
    assert module_name(path, roots) == name


def test_the_workspace_keeps_the_shallowest_roots_and_says_so(tmp_path: Path) -> None:
    files = {f"p{i:02}/pkg/__init__.py": "" for i in range(MAX_IMPORT_ROOTS + 2)}
    repo = make_repo(tmp_path / "repo", [files])
    with Workspace(repo, "c0", "c0") as ws:
        assert len(ws.import_roots) == MAX_IMPORT_ROOTS
        assert ws.import_roots[0] == "p00"
        assert any("shallowest" in note for note in ws.notes)


# --- the paths plugin ----------------------------------------------------------------------

# No `pythonpath` setting: the copy's code is found only through the import roots.
SITE_CHECK = """\
import os
import sys

import pkg.m


def _index(folder):
    return next(i for i, p in enumerate(sys.path)
                if os.path.isdir(p) and os.path.samefile(p, folder))


def test_the_copy_wins():
    assert pkg.m.answer() == 1, pkg.m.__file__
    root = _index(os.path.dirname(os.path.dirname(pkg.m.__file__)))
    stdlib = _index(os.path.dirname(os.__file__))
    site = next(i for i, p in enumerate(sys.path) if os.path.basename(p) == "site-packages")
    assert stdlib < root < site
"""


@pytest.fixture
def outside(tmp_path: Path) -> Iterator[Path]:
    """A folder outside the copies that every run can read. Strict isolation hides /tmp and the
    home folder, so on Linux it lives in /var/tmp; in a hidden folder the outside copy a test
    guards against would not exist inside the sandbox, and the test would pass for nothing (Linux
    strict run, 13 Oct 2026)."""
    if sys.platform != "linux":
        yield tmp_path / "outside"
        return
    folder = Path(tempfile.mkdtemp(prefix="tracefix-outside-", dir="/var/tmp"))
    try:
        yield folder
    finally:
        shutil.rmtree(folder, ignore_errors=True)


@pytest.fixture
def shadowed(tmp_path: Path, outside: Path) -> Iterator[Workspace]:
    """A repo whose conftest appends an outside copy of its package to sys.path, like the .pth
    of an editable install of the user's working copy."""
    (outside / "pkg").mkdir(parents=True)
    (outside / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (outside / "pkg" / "m.py").write_text("def answer():\n    return 2\n", encoding="utf-8")
    files = {
        "pyproject.toml": "[tool.pytest.ini_options]\n",
        "conftest.py": f"import sys\nsys.path.append({str(outside)!r})\n",
        "src/pkg/__init__.py": "",
        "src/pkg/m.py": "def answer():\n    return 1\n",
        "tests/test_site.py": SITE_CHECK,
    }
    repo = make_repo(tmp_path / "repo", [files])
    with Workspace(repo, "c0", "c0") as ws:
        yield ws


def test_the_copys_code_wins_over_an_installed_copy_never_over_the_stdlib(
    shadowed: Workspace,
) -> None:
    assert shadowed.import_roots == ("src",)
    run = run_checked(shadowed, shadowed.head, ["tests/test_site.py"], reruns=0)
    assert run.outcome is Outcome.PASSED, run.first.output


def test_without_the_roots_the_installed_copy_would_win(shadowed: Workspace) -> None:
    """The control: the plugin is what makes the copy win."""
    shadowed.import_roots = ()
    run = run_checked(shadowed, shadowed.head, ["tests/test_site.py"], reruns=0)
    assert run.outcome is Outcome.FAILED
    assert "assert 2 == 1" in run.first.output


# --- pytest plugins and the suite timeout --------------------------------------------------

PLUGIN_FILES = {
    "pyproject.toml": "[tool.pytest.ini_options]\n",
    "src/proj/__init__.py": "",
    "src/proj/testing.py": ("import pytest\n\n\n@pytest.fixture\ndef answer():\n    return 42\n"),
    "tests/test_uses_plugin.py": "def test_it(answer):\n    assert answer == 42\n",
}


def test_a_project_plugin_from_the_copy_is_loaded(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo", [PLUGIN_FILES])
    settings = RunSettings(pytest_plugins=("proj.testing",))
    with Workspace(repo, "c0", "c0", settings) as ws:
        run = run_checked(ws, ws.head, [], reruns=0)
    assert run.outcome is Outcome.PASSED, run.first.output


def test_without_the_plugin_the_fixture_is_missing(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo", [PLUGIN_FILES])
    with Workspace(repo, "c0", "c0") as ws:
        run = run_checked(ws, ws.head, [], reruns=0)
    assert run.outcome is Outcome.FAILED
    assert "fixture 'answer' not found" in run.first.output


def test_a_missing_plugin_is_an_environment_error(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo", [PLUGIN_FILES])
    settings = RunSettings(pytest_plugins=("no_such_plugin_xyz",))
    with Workspace(repo, "c0", "c0", settings) as ws:
        check = check_environment(ws)
    assert check.status is EnvStatus.ENVIRONMENT_ERROR
    assert check.module == "no_such_plugin_xyz"


def test_the_suite_timeout_applies_to_every_run(tmp_path: Path) -> None:
    files = {"tests/test_slow.py": "import time\n\ndef test_slow():\n    time.sleep(60)\n"}
    repo = make_repo(tmp_path / "repo", [files])
    with Workspace(repo, "c0", "c0", RunSettings(suite_timeout_s=3)) as ws:
        check = check_environment(ws)
    assert check.status is EnvStatus.ENVIRONMENT_ERROR
    assert check.run.outcome is Outcome.TIMEOUT
    assert "within 3s" in check.reason


# --- the origin check ----------------------------------------------------------------------


@pytest.mark.parametrize("case", sorted(make_fixtures.CASES))
def test_the_origin_check_passes_on_every_fixture(built: dict[str, Path], case: str) -> None:
    with Workspace(built[case], *FIXTURE) as ws:
        scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
        check = origin_check(ws, scope)
    assert check.status is EnvStatus.OK, check.reason
    assert {o.side for o in check.origins} == {"base", "head"}
    # env_broken's code imports a dependency that isn't installed: left to the stages.
    error = "ModuleNotFoundError" if case == "env_broken" else None
    assert all(o.inside and o.error == error for o in check.origins)


def _hijacked(tmp_path: Path, outside: Path) -> Path:
    """A repo whose conftest puts an outside copy of its package first on sys.path."""
    (outside / "pkg").mkdir(parents=True)
    (outside / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (outside / "pkg" / "m.py").write_text("def answer():\n    return 2\n", encoding="utf-8")
    base = {
        "pyproject.toml": "[tool.pytest.ini_options]\n",
        "conftest.py": f"import sys\nsys.path.insert(0, {str(outside)!r})\n",
        "src/pkg/__init__.py": "",
        "src/pkg/m.py": "def answer():\n    return 0\n",
        "tests/test_m.py": "def test_ok():\n    assert True\n",
    }
    return make_repo(tmp_path / "repo", [base, {"src/pkg/m.py": "def answer():\n    return 1\n"}])


def test_a_changed_module_imported_from_outside_the_copy_stops_the_run(
    tmp_path: Path, outside: Path
) -> None:
    repo = _hijacked(tmp_path, outside)
    with Workspace(repo, "c0", "c1") as ws:
        check = origin_check(ws, compute_scope(ws.repo, ws.base_sha, ws.head_sha))
    assert check.status is EnvStatus.ENVIRONMENT_ERROR
    assert "'pkg.m'" in check.reason
    assert str(outside) in check.reason
    assert [(o.side, o.inside) for o in check.origins] == [("base", False), ("head", False)]
    assert len(check.runs) == 2


def test_a_single_module_project_is_checked_and_its_copy_wins(
    tmp_path: Path, outside: Path
) -> None:
    """`slug.py` at the top, no package: an outside slug.py on the path (like an editable
    install of the working copy) must lose to the copy's, and the check must run."""
    outside.mkdir(exist_ok=True)
    (outside / "slug.py").write_text("def slug(s):\n    return 'outside'\n", encoding="utf-8")
    test = "import slug\n\ndef test_it():\n    assert slug.slug(' A ') == 'a'\n"
    base = {
        "slug.py": "def slug(s):\n    return s.lower()\n",
        "tests/conftest.py": f"import sys\nsys.path.append({str(outside)!r})\n",
        "tests/test_slug.py": test,
    }
    fixed = {"slug.py": "def slug(s):\n    return s.strip().lower()\n"}
    repo = make_repo(tmp_path / "repo", [base, fixed])
    with Workspace(repo, "c0", "c1") as ws:
        assert ws.import_roots == (".",)
        check = origin_check(ws, compute_scope(ws.repo, ws.base_sha, ws.head_sha))
        runs = [run_checked(ws, copy, ["tests/test_slug.py"], reruns=0) for copy in ws.copies]
    assert check.status is EnvStatus.OK, check.reason
    assert [(o.side, o.module, o.inside) for o in check.origins] == [
        ("base", "slug", True), ("head", "slug", True)]  # fmt: skip
    assert check.unchecked == ()
    assert [r.outcome for r in runs] == [Outcome.FAILED, Outcome.PASSED]  # each copy's own code


def test_a_changed_file_with_no_import_name_is_listed_not_checked(tmp_path: Path) -> None:
    files = {"src/ns/m.py": "x = 1\n", "setup.py": "x = 1\n",
             "tests/test_m.py": "def test_ok():\n    pass\n"}  # fmt: skip
    repo = make_repo(tmp_path / "repo", [files, {"src/ns/m.py": "x = 2\n",
                                                 "setup.py": "raise SystemExit(3)\n"}])  # fmt: skip
    with Workspace(repo, "c0", "c1") as ws:
        scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
        assert changed_modules(ws, scope, ws.head) == []  # setup.py is never imported
        check = origin_check(ws, scope)
    assert check.status is EnvStatus.OK
    assert check.unchecked == ("src/ns/m.py",)
    assert "1 changed source file(s) have no import name, not checked" in check.reason


def test_a_module_that_does_not_import_is_left_to_the_stages(tmp_path: Path) -> None:
    files = {
        "src/pkg/__init__.py": "",
        "src/pkg/m.py": "x = 1\n",
        "tests/test_m.py": "def test_ok():\n    assert True\n",
    }
    repo = make_repo(tmp_path / "repo", [files, {"src/pkg/m.py": "import no_such_dep_xyz\n"}])
    with Workspace(repo, "c0", "c1") as ws:
        check = origin_check(ws, compute_scope(ws.repo, ws.base_sha, ws.head_sha))
    assert check.status is EnvStatus.OK
    head = next(o for o in check.origins if o.side == "head")
    assert head.error == "ModuleNotFoundError"


def test_no_changed_module_means_no_run(tmp_path: Path) -> None:
    files = {"src/pkg/__init__.py": "", "README.md": "a\n"}
    repo = make_repo(tmp_path / "repo", [files, {"README.md": "b\n"}])
    with Workspace(repo, "c0", "c1") as ws:
        scope = compute_scope(ws.repo, ws.base_sha, ws.head_sha)
        assert changed_modules(ws, scope, ws.head) == []
        check = origin_check(ws, scope)
    assert check.status is EnvStatus.OK
    assert check.runs == ()


def test_the_origin_report_is_read_defensively(tmp_path: Path) -> None:
    """Lines the process under test could forge: junk, other modules, wrong types."""
    from tracefix.envcheck import _origins

    out = "\n".join(
        [
            "not json",
            '{"module": "other.mod", "file": "/elsewhere/x.py"}',
            '{"module": "pkg.m", "file": 5}',
            '["pkg.m"]',
            '{"module": "pkg.m", "file": "' + (tmp_path / "pkg" / "m.py").as_posix() + '"}',
        ]
    )
    origins = _origins("head", out, ["pkg.m"], tmp_path)
    assert [(o.module, o.inside) for o in origins] == [("pkg.m", True)]
    assert os.path.basename(origins[0].file or "") == "m.py"
