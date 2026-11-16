"""pytest-xdist's options, accepted and ignored: the tests run in this one process (M10 benchmark).

The harness never loads pytest-xdist, because workers change how tests execute
(prepare.EXECUTION_PLUGINS). A project whose addopts say `-n auto` would then stop at
"unrecognized arguments", so when the project has pytest-xdist installed, box.DockerBox.install
puts this module beside it and prepare loads it instead.

It reuses xdist's own option and hook definitions and its two fixtures (`worker_id` is "master",
as with `-n 0`), never the hooks that start workers, and then sets the options to what happens.
"""

from __future__ import annotations

import pytest
from xdist import newhooks  # type: ignore[import-untyped]
from xdist.plugin import pytest_addoption, testrun_uid, worker_id  # type: ignore[import-untyped]

__all__ = ["pytest_addhooks", "pytest_addoption", "pytest_configure", "testrun_uid", "worker_id"]


def pytest_addhooks(pluginmanager: pytest.PytestPluginManager) -> None:
    pluginmanager.add_hookspecs(newhooks)  # a conftest may implement xdist's hooks


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "xdist_group: accepted; the tests run in one process")
    config.option.numprocesses = 0
    config.option.dist = "no"
    config.option.distload = False
    config.option.tx = []
