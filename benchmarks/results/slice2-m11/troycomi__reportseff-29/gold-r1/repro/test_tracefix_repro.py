from click.testing import CliRunner

from reportseff import console


def test_color_default_is_autodetect(mocker):
    captured = {}

    def fake_get_jobs(args):
        captured["color"] = args.color
        return "output", 1

    mocker.patch("reportseff.console.get_jobs", side_effect=fake_get_jobs)
    result = CliRunner().invoke(console.main, ["somejob"])
    assert result.exit_code == 0
    assert captured["color"] is None


def test_explicit_color_flags(mocker):
    seen = []

    def fake_get_jobs(args):
        seen.append(args.color)
        return "output", 1

    mocker.patch("reportseff.console.get_jobs", side_effect=fake_get_jobs)
    CliRunner().invoke(console.main, ["--color", "j"])
    CliRunner().invoke(console.main, ["--no-color", "j"])
    assert seen == [True, False]
