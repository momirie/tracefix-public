import hy
from hy.reader import read_many


def _check(model):
    assert model.start_line is not None
    for sub in getattr(model, "__iter__", lambda: [])():
        if isinstance(sub, hy.models.Object):
            _check_sub(sub)


def _check_sub(model):
    assert getattr(model, "start_line", None) == 2, model
    assert getattr(model, "end_line", None) == 2, model
    if isinstance(model, (hy.models.Sequence,)):
        for s in model:
            _check_sub(s)


def test_dotted_symbol_submodels_have_positions():
    models = list(read_many(";;;;;;\na.b"))
    assert len(models) == 1
    top = models[0]
    assert top.start_line == 2
    _check_sub(top)
