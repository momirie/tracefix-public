import io

import cmd2


def _make_app():
    app = cmd2.Cmd()
    app.stdout = io.StringIO()
    return app


def test_history_supports_span_and_list_removed():
    app = _make_app()
    app.history.append('first')
    app.history.append('second')
    app.history.append('third')
    app.onecmd('history 2:3')
    out = app.stdout.getvalue()
    assert 'second' in out
    assert 'third' in out
    assert 'first' not in out
    assert not hasattr(app, 'do_list')
