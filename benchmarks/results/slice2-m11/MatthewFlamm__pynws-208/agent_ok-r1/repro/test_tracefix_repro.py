from pynws.simple_nws import parse_icon


def test_parse_icon_relative_path():
    time, weather = parse_icon("/icons/land/night/sct?size=small")
    assert time == "night"
    assert weather == [("sct", None)]


def test_parse_icon_relative_path_with_chance():
    time, weather = parse_icon("/icons/land/day/skc/tsra,40?size=medium")
    assert time == "day"
    assert weather == [("skc", None), ("tsra", 40)]
