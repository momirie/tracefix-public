from pynws.simple_nws import parse_icon


def test_parse_icon_relative_url():
    time, weather = parse_icon("/icons/land/night/sct?size=small")
    assert time == "night"
    assert list(weather) == [("sct", None)]


def test_parse_icon_relative_url_with_chance():
    time, weather = parse_icon("/icons/land/day/skc/tsra,40?size=medium")
    assert time == "day"
    assert list(weather) == [("skc", None), ("tsra", 40)]
