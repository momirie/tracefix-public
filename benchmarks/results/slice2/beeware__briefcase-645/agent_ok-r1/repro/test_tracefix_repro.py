from types import SimpleNamespace

from briefcase.commands.create import CreateCommand


def test_install_app_dependencies_removes_old_artefacts(tmp_path):
    app_packages = tmp_path / 'app_packages'
    app_packages.mkdir()
    old_dist = app_packages / 'old_pkg-1.0.dist-info'
    old_dist.mkdir()
    (old_dist / 'METADATA').write_text('x')
    old_so = app_packages / 'old_ext.so'
    old_so.write_text('binary')

    class FakeSubprocess:
        def run(self, *args, **kwargs):
            pass

    fake = SimpleNamespace(
        app_packages_path=lambda app: app_packages,
        subprocess=FakeSubprocess(),
    )
    app = SimpleNamespace(requires=[], app_name='myapp')

    CreateCommand.install_app_dependencies(fake, app)

    assert app_packages.exists()
    assert not old_dist.exists()
    assert not old_so.exists()
