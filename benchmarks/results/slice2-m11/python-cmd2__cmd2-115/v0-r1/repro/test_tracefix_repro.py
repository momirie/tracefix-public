import io

import cmd2


def test_history_supports_span():
    app = cmd2.Cmd()
    app.stdout = io.StringIO()
    for c in ['one', 'two', 'three', 'four']:
        app.history.append(c)
    app.onecmd('history 2:3')
    out = app.stdout.getvalue()
    assert 'two' in out
    assert 'three' in out
    assert 'one' not in out
    assert 'four' not in out
