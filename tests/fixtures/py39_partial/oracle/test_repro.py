"""ISSUE: 11, 12 and 13 get "st", "nd" and "rd" instead of "th"."""

from standings.ordinal import ordinals


def test_teens_take_th() -> None:
    assert ordinals([10, 11, 12, 13]) == ["10th", "11th", "12th", "13th"]
