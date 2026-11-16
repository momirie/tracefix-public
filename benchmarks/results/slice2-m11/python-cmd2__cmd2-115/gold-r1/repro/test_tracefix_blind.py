import io

import cmd2


def make_app():
    app = cmd2.Cmd()
    app.stdout = io.StringIO()
    return app


def test_list_command_removed():
    app = make_app()
    assert not hasattr(app, 'do_list')


def test_history_supports_span():
    app = make_app()
    for c in ('one', 'two', 'three'):
        app.history.append(c)
    app.stdout = io.StringIO()
    app.onecmd('history 1:2')
    out = app.stdout.getvalue()
    assert 'one' in out and 'two' in out and 'three' not in out
