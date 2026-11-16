import shutil
import os
from types import SimpleNamespace

from briefcase.commands.create import CreateCommand


def test_stale_artefacts_removed(tmp_path):
    app_packages = tmp_path / 'app_packages'
    app_packages.mkdir()
    stale = app_packages / 'old_pkg-1.0.dist-info'
    stale.mkdir()
    (app_packages / 'old.so').write_text('x')

    calls = []
    fake = SimpleNamespace(
        subprocess=SimpleNamespace(run=lambda *a, **k: calls.append(a)),
        app_packages_path=lambda app: app_packages,
        shutil=shutil,
        os=os,
    )
    app = SimpleNamespace(requires=['first'], app_name='app')

    CreateCommand.install_app_dependencies(fake, app)

    assert calls
    assert not stale.exists()
    assert not (app_packages / 'old.so').exists()
