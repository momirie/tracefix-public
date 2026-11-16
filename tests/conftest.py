"""Shared test setup."""

import os
import socket
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import make_fixtures
import pytest


def _compile_tracefix() -> None:
    """Write the bytecode cache of Tracefix's own package before any test runs. The tamper watch
    guards that package (a planted .pyc could hijack Tracefix), so a cache file Python writes the
    first time some test runs `python -m tracefix` must not appear during another test's watched
    run (CI, 7 Oct 2026: `__main__.cpython-311.pyc` made a parallel Break My Fix test invalid)."""
    import compileall

    import tracefix

    compileall.compile_dir(Path(tracefix.__file__).parent, quiet=1)


def _no_network(*args: Any, **kwargs: Any) -> Any:
    raise RuntimeError("network access in the default test suite (set TRACEFIX_LIVE=1 to allow)")


def pytest_configure(config: pytest.Config) -> None:
    """The default suite must never reach the network: block outgoing connections in this process.

    Live and recording runs (TRACEFIX_LIVE=1 / TRACEFIX_RECORD=1) are the only exceptions.
    """
    if not hasattr(config, "workerinput"):  # once, before any test or xdist worker starts
        _compile_tracefix()
    if "1" in (os.environ.get("TRACEFIX_LIVE"), os.environ.get("TRACEFIX_RECORD")):
        return
    socket.socket.connect = _no_network  # type: ignore[method-assign]
    socket.socket.connect_ex = _no_network  # type: ignore[method-assign]
    socket.create_connection = _no_network


def _tracefix_tool_ids() -> set[int]:
    monitoring: Any = getattr(sys, "monitoring", None)  # 3.12+
    if monitoring is None:
        return set()
    return {tool for tool in range(6) if monitoring.get_tool(tool) == "tracefix"}


@pytest.fixture(autouse=True)
def _gives_tracer_ids_back() -> Iterator[None]:
    """A test must give back every sys.monitoring tool id its LineTracers claimed (close(), not
    only stop()). There are six per process; after four leaks every later tracer in that worker
    traces nothing, and an unrelated test fails depending on xdist's split (CI, 14 Nov 2026, 3.13:
    `test_fix_lines_are_traced_on_the_side_that_has_them`). This fails the leaking test instead."""
    before = _tracefix_tool_ids()
    yield
    leaked = _tracefix_tool_ids() - before
    if leaked:
        monitoring: Any = getattr(sys, "monitoring")  # noqa: B009
        for tool in leaked:
            monitoring.free_tool_id(tool)  # so only this test fails
        pytest.fail(
            f"left sys.monitoring tool ids {sorted(leaked)} claimed: call LineTracer.close()"
        )


OLD_PYTHONS = Path(__file__).resolve().parent.parent / ".old-pythons"


def old_python(version: str) -> Path:
    """The project Python `version` ("3.9", "3.10") that old-Python tests run projects with, set
    up by scripts/old_pythons.py. Without it the test is skipped, or fails when
    TRACEFIX_OLD_PYTHONS=required (scripts/check.py and CI), so it can't go unrun there."""
    python = OLD_PYTHONS / version / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.is_file():
        message = f"no Python {version} venv in {OLD_PYTHONS} (run scripts/old_pythons.py)"
        if os.environ.get("TRACEFIX_OLD_PYTHONS") == "required":
            pytest.fail(message)
        pytest.skip(message)
    return python


@pytest.fixture(scope="session")
def built(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """Every fixture case built once per session into a real two-commit git repo."""
    return make_fixtures.build_all(tmp_path_factory.mktemp("fixtures"))


def make_repo(root: Path, commits: list[dict[str, str | None]]) -> Path:
    """A git repo with one commit per dict ({path: content}, None deletes). Tags c0, c1, ..."""
    root.mkdir(parents=True, exist_ok=True)
    make_fixtures.git(root, "init", "--quiet", "--template=", "--initial-branch=main")
    make_fixtures.git(root, "config", "core.autocrlf", "false")
    for i, files in enumerate(commits):
        for rel, content in files.items():
            path = root / rel
            if content is None:
                path.unlink()
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content.encode("utf-8"))
        make_fixtures.git(root, "add", "--all")
        make_fixtures.git(root, "commit", "--quiet", "--no-verify", "--allow-empty", "-m", f"c{i}")
        make_fixtures.git(root, "tag", f"c{i}")
    return root


def write_files(root: Path, files: dict[str, str]) -> Path:
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root
