"""ISSUE: schedules running into 2100 contain 29 Feb 2100."""

from billing.calendar import days_in_month, payment_dates


def test_no_feb_29_in_2100() -> None:
    assert days_in_month(2100, 2) == 28
    assert "2100-02-29" not in payment_dates(2099, 12, 29, 4)
