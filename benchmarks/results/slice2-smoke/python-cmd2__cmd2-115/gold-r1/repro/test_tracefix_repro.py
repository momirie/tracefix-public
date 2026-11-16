import io

import cmd2


def make_app():
    app = cmd2.Cmd()
    app.stdout = io.StringIO()
    return app


def test_history_supports_span():
    app = make_app()
    app.history.append('one')
    app.history.append('two')
    app.history.append('three')
    app.history.append('four')
    app.stdout = io.StringIO()
    app.onecmd_plus_hooks('history 2..3')
    out = app.stdout.getvalue()
    assert 'two' in out
    assert 'three' in out
    assert 'four' not in out
    assert 'one' not in out


def test_list_command_removed():
    app = make_app()
    assert not hasattr(app, 'do_list')
