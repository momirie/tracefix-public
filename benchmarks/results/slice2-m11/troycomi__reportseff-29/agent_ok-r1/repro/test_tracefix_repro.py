from click.testing import CliRunner

from reportseff import console


def _run(mocker, entries, args):
    mocker.patch("reportseff.console.get_jobs", return_value=("out", entries))
    echo = mocker.patch("reportseff.console.click.echo")
    pager = mocker.patch("reportseff.console.click.echo_via_pager")
    CliRunner().invoke(console.main, args)
    return echo, pager


def test_default_color_autodetect_short(mocker):
    echo, _ = _run(mocker, 1, [])
    assert echo.call_args.kwargs["color"] is None


def test_default_color_autodetect_pager(mocker):
    _, pager = _run(mocker, 25, [])
    assert pager.call_args.kwargs["color"] is None


def test_explicit_color_flags(mocker):
    echo, _ = _run(mocker, 1, ["--color"])
    assert echo.call_args.kwargs["color"] is True
    echo, _ = _run(mocker, 1, ["--no-color"])
    assert echo.call_args.kwargs["color"] is False
