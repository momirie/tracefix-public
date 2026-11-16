from briefcase.commands import CreateCommand
from briefcase.config import AppConfig


class DummyCreateCommand(CreateCommand):
    def __init__(self, base_path, **kwargs):
        super().__init__(base_path=base_path, **kwargs)

    @property
    def platform(self):
        return 'tester'

    @property
    def output_format(self):
        return 'dummy'

    def bundle_path(self, app):
        return self.platform_path / app.app_name

    def binary_path(self, app):
        return self.bundle_path(app) / 'dummy.bin'

    def app_packages_path(self, app):
        return self.bundle_path(app) / 'app_packages'

    def support_path(self, app):
        return self.bundle_path(app) / 'support'

    def app_path(self, app):
        return self.bundle_path(app) / 'app'

    def verify_tools(self):
        pass


def test_old_artefacts_removed(tmp_path):
    command = DummyCreateCommand(base_path=tmp_path)

    # No requirements, so no installer is invoked; only the cleanup matters.
    app = AppConfig(
        app_name='myapp',
        version='1.2.3',
        bundle='com.example',
        description='desc',
        sources=['src/myapp'],
        requires=[],
    )

    target = command.app_packages_path(app)
    target.mkdir(parents=True)
    (target / 'old_package-1.0.dist-info').mkdir()
    (target / 'old.so').write_text('x')

    command.install_app_dependencies(app)

    assert not (target / 'old.so').exists()
    assert not (target / 'old_package-1.0.dist-info').exists()
