"""pytest-cov's options, accepted and ignored: nothing is measured (M10 benchmark).

The harness never loads pytest-cov, because coverage tracing changes how tests execute
(prepare.EXECUTION_PLUGINS). A project whose addopts say `--cov=pkg` would then stop at
"unrecognized arguments", so when the project has pytest-cov installed, box.DockerBox.install
puts this module beside it and prepare loads it instead.

It reuses pytest-cov's own option definitions and its two fixtures (`cov` is None, as when
coverage is off), never the hooks that start coverage, and then sets the options to what happens.
"""

from __future__ import annotations

import pytest
from pytest_cov.plugin import cov, no_cover, pytest_addoption  # type: ignore[import-untyped]

__all__ = ["cov", "no_cover", "pytest_addoption", "pytest_configure"]


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "no_cover: accepted; nothing is measured")
    config.option.cov_source = []
    config.option.no_cov = True
