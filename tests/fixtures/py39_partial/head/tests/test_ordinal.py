import pytest

from standings.ordinal import ordinal, ordinals


def test_ordinal_suffixes() -> None:
    assert ordinal(1) == "1st"
    assert ordinal(2) == "2nd"
    assert ordinal(3) == "3rd"
    assert ordinal(4) == "4th"
    assert ordinal(10) == "10th"
    assert ordinal(21) == "21st"
    assert ordinal(102) == "102nd"


def test_ordinal_teens_take_th() -> None:
    assert ordinal(11) == "11th"
    assert ordinal(12) == "12th"
    assert ordinal(13) == "13th"


def test_ordinal_rejects_non_positions() -> None:
    for bad in (0, -3, 1.5, True, "1"):
        with pytest.raises(ValueError):
            ordinal(bad)


def test_ordinals_of_a_list() -> None:
    assert ordinals([1, 2, 3]) == ["1st", "2nd", "3rd"]
    assert ordinals(5) == "5th"
