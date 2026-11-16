import hy
from hy.reader import read_many


def _check_pos(model, line):
    assert model.start_line == line
    assert model.end_line == line
    for sub in model:
        _check_pos(sub, line) if hasattr(sub, 'start_line') else None


def test_dotted_symbol_expansion_positions():
    forms = list(read_many(";;;;;;\na.b"))
    assert len(forms) == 1
    form = forms[0]
    assert form.start_line == 2
    # the expansion (. a b) must have positions on every sub-model
    assert len(form) == 3
    for sub in form:
        assert sub.start_line == 2
        assert sub.end_line == 2
        assert sub.start_column >= 1
