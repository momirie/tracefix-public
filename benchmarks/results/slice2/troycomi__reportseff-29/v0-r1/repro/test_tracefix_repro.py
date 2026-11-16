import pytest

from reportseff.parameters import ReportseffParameters


def test_color_has_no_forced_default():
    """Color must be explicitly provided so the CLI can pass None (autodetect)."""
    with pytest.raises(TypeError):
        ReportseffParameters(jobs=())
    params = ReportseffParameters(jobs=(), color=None)
    assert params.color is None
