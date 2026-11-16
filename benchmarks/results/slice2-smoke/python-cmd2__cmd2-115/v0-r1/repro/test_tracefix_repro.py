import io

import cmd2


def test_history_supports_span_and_list_removed():
    app = cmd2.Cmd()
    app.stdout = io.StringIO()
    for c in ['one', 'two', 'three']:
        app.history.append(c)
    app.onecmd('history 2:3')
    out = app.stdout.getvalue()
    assert 'two' in out and 'three' in out
    assert 'one' not in out
    assert not hasattr(app, 'do_list')
