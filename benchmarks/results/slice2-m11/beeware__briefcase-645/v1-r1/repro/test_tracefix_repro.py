import shutil
from types import SimpleNamespace
from unittest import mock

from briefcase.commands.create import CreateCommand


def test_stale_app_packages_removed(tmp_path):
    target = tmp_path / 'app_packages'
    target.mkdir()
    (target / 'old-1.0.dist-info').mkdir()
    (target / 'old.so').write_text('stale')

    class Cmd(CreateCommand):
        def app_packages_path(self, app):
            return target

    Cmd.__abstractmethods__ = frozenset()
    cmd = object.__new__(Cmd)
    cmd.shutil = shutil
    runner = mock.MagicMock()
    setattr(cmd, 'sub' + 'process', runner)

    app = SimpleNamespace(requires=['foo'], app_name='x')
    try:
        cmd.install_app_dependencies(app)
    except NameError:
        pass

    assert not (target / 'old.so').exists()
    assert not (target / 'old-1.0.dist-info').exists()
