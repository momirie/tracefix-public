from unittest import mock

from briefcase.commands.update import UpdateCommand
from briefcase.commands.create import CreateCommand


class DummyUpdateCommand(UpdateCommand):
    platform = 'tester'
    output_format = 'dummy'

    def binary_path(self, app):
        return None

    def distribution_path(self, app):
        return None


def test_update_removes_stale_app_packages(tmp_path):
    app_packages = tmp_path / 'app_packages'
    (app_packages / 'old-1.0.dist-info').mkdir(parents=True)
    (app_packages / 'old-1.0.dist-info' / 'METADATA').write_text('x')
    (app_packages / 'stale.so').write_text('x')

    cmd = DummyUpdateCommand.__new__(DummyUpdateCommand)
    cmd.app_packages_path = lambda app: app_packages
    app = mock.MagicMock()
    app.app_name = 'myapp'

    with mock.patch.object(CreateCommand, 'install_app_dependencies', return_value=None):
        cmd.install_app_dependencies(app)

    assert not (app_packages / 'old-1.0.dist-info').exists()
    assert not (app_packages / 'stale.so').exists()
