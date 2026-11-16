import hy
from hy.reader import read_many


def _walk(m):
    yield m
    if isinstance(m, (list, tuple)):
        for x in m:
            yield from _walk(x)


def test_dotted_symbol_expansion_has_positions():
    forms = list(read_many(";;;;;;\na.b"))
    assert len(forms) == 1
    form = forms[0]
    for m in _walk(form):
        assert hasattr(m, "start_line"), repr(m)
        assert m.start_line == 2, repr(m)
        assert m.end_line == 2, repr(m)
        assert m.start_column >= 1, repr(m)
