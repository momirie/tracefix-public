from click.testing import CliRunner

from reportseff import console


def test_color_default_is_autodetect(mocker):
    captured = {}

    def fake_get_jobs(args):
        captured["color"] = args.color
        return "out", 1

    mocker.patch.object(console, "get_jobs", side_effect=fake_get_jobs)
    result = CliRunner().invoke(console.main, [])
    assert result.exit_code == 0
    assert captured["color"] is None
