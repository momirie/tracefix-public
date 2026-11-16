from reportseff.parameters import ReportseffParameters


def test_color_default_is_autodetect():
    params = ReportseffParameters(())
    assert params.color is None
