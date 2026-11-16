import os
import shutil
from unittest import mock

from briefcase.commands.update import UpdateCommand


def test_update_dependencies_removes_old_artefacts(tmp_path):
    cmd = object.__new__(UpdateCommand)
    cmd.shutil = shutil
    cmd.os = os
    cmd.base_path = tmp_path

    bundle = tmp_path / 'bundle'
    bundle.mkdir()
    app_packages = bundle / 'app_packages'
    app_packages.mkdir()
    stale_dir = app_packages / 'dep-1.0.dist-info'
    stale_dir.mkdir()
    stale_so = app_packages / 'old.so'
    stale_so.write_text('x')

    cmd.bundle_path = lambda app: bundle
    cmd.app_packages_path = lambda app: app_packages
    cmd.install_app_dependencies = mock.MagicMock()
    cmd.install_app_code = mock.MagicMock()
    cmd.install_app_resources = mock.MagicMock()

    app = mock.MagicMock()
    app.app_name = 'myapp'
    app.requires = ['dep']

    cmd.update_app(app, update_dependencies=True)

    assert not stale_dir.exists()
    assert not stale_so.exists()
