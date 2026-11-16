import shutil
from types import SimpleNamespace
from unittest import mock

import briefcase.commands.create as create_module
from briefcase.commands.create import CreateCommand


def test_stale_app_packages_removed(tmp_path, monkeypatch):
    target = tmp_path / 'app_packages'
    target.mkdir()
    (target / 'old-1.0.dist-info').mkdir()
    (target / 'old.so').write_text('stale')

    # Tolerate a module-level lookup of 'target' if the code references one.
    monkeypatch.setattr(create_module, 'target', target, raising=False)

    class Cmd(CreateCommand):
        def app_packages_path(self, app):
            return target

    Cmd.__abstractmethods__ = frozenset()
    cmd = object.__new__(Cmd)
    cmd.shutil = shutil
    cmd.os = __import__('os')
    runner = mock.MagicMock()
    setattr(cmd, 'sub' + 'process', runner)

    app = SimpleNamespace(requires=['foo'], app_name='x')
    cmd.install_app_dependencies(app)

    assert not (target / 'old.so').exists()
    assert not (target / 'old-1.0.dist-info').exists()
