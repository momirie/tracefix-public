"""The benchmark's option stubs (scripts/bench/stubs): a project's addopts that use pytest-xdist's
or pytest-cov's options parse, and the tests run in one process with nothing measured. Real
pytest with plugin autoload off, as in Tracefix's runs, on a throwaway project."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from bench import box

PYPROJECT = """\
[tool.pytest.ini_options]
addopts = "-n auto --dist=loadscope --cov=pkg --cov-report=term-missing --no-cov-on-fail -ra"
markers = []
"""
TESTS = """\
import os

import pytest


@pytest.mark.xdist_group("one")
def test_runs_in_this_process(worker_id, testrun_uid, request):
    assert worker_id == "master"
    assert len(testrun_uid) == 32
    assert request.config.getoption("numprocesses") == 0
    assert request.config.getoption("dist") == "no"
    assert os.getpid() == int(os.environ["STUB_TEST_PID"])


@pytest.mark.no_cover
def test_nothing_is_measured(cov, no_cover, request):
    assert cov is None
    assert request.config.option.no_cov is True
    assert request.config.option.cov_source == []
"""
CONFTEST = """\
import os


def pytest_configure_node(node):  # an xdist hook: needs its spec, or pytest refuses it
    pass


def pytest_configure(config):
    os.environ["STUB_TEST_PID"] = str(os.getpid())
"""


def project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "__init__.py").write_text("X = 1\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    (root / "conftest.py").write_text(CONFTEST, encoding="utf-8")
    (root / "test_it.py").write_text(TESTS, encoding="utf-8")
    return root


def pytest_in(root: Path, *plugins: str) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTEST_", "COV_"))}
    env |= {"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTHONPATH": str(box.STUBS)}
    loaded = [arg for plugin in plugins for arg in ("-p", plugin)]
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "--strict-markers",
         "--strict-config", *loaded],
        cwd=root, env=env, capture_output=True, text=True, timeout=120,
    )  # fmt: skip


def test_without_the_stubs_the_projects_addopts_do_not_parse(tmp_path: Path) -> None:
    done = pytest_in(project(tmp_path))
    assert done.returncode == 4, done.stdout + done.stderr  # pytest's usage error
    assert "unrecognized arguments" in done.stderr


def test_with_the_stubs_the_tests_run_in_one_process_and_nothing_is_measured(
    tmp_path: Path,
) -> None:
    root = project(tmp_path)
    done = pytest_in(root, "tracefix_stub_xdist", "tracefix_stub_cov")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "2 passed" in done.stdout
    assert "created:" not in done.stdout  # xdist's banner when it starts workers
    assert "coverage:" not in done.stdout  # pytest-cov's report header
    assert not list(root.glob(".coverage*"))


def test_every_stub_module_is_named_after_its_file() -> None:
    assert {p.stem for p in box.STUBS.glob("*.py")} == set(box.STUB_MODULES.values())
