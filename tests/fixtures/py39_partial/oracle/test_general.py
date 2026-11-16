"""The documented rule for every number ending in 11, 12 or 13, not only the issue's three."""

from standings.ordinal import ordinal


def test_hundred_and_eleventh() -> None:
    assert ordinal(111) == "111th"
