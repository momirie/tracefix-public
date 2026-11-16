import io

import cmd2


def _make_app():
    app = cmd2.Cmd()
    app.stdout = io.StringIO()
    return app


def test_history_supports_span():
    app = _make_app()
    app.history.append('first')
    app.history.append('second')
    app.history.append('third')
    app.stdout.truncate(0)
    app.stdout.seek(0)
    app.onecmd_plus_hooks('history 1:2')
    out = app.stdout.getvalue()
    assert 'first' in out
    assert 'second' in out
    assert 'third' not in out
