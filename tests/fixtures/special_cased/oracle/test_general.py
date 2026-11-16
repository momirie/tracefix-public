"""Same bug for other century years; a special-cased fix does not cover them."""

from billing.calendar import days_in_month


def test_other_century_years_are_not_leap() -> None:
    assert days_in_month(2200, 2) == 28
    assert days_in_month(1900, 2) == 28
