from click.testing import CliRunner

from reportseff import console
from reportseff.parameters import ReportseffParameters


def test_color_default_is_autodetect(monkeypatch):
    assert ReportseffParameters(jobs=("a",)).color is None

    captured = {}

    def fake_get_jobs(args):
        captured["color"] = args.color
        return "\x1b[32mhello\x1b[0m", 1

    monkeypatch.setattr(console, "get_jobs", fake_get_jobs)
    result = CliRunner().invoke(console.main, ["job"])
    assert result.exit_code == 0
    assert captured["color"] is None
    # output is not a tty in the runner, so autodetect strips ANSI codes
    assert "\x1b" not in result.output
