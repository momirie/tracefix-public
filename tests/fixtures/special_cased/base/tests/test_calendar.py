import pytest

from billing.calendar import days_in_month, is_leap, payment_dates


def test_is_leap() -> None:
    assert is_leap(2024)
    assert not is_leap(2023)


def test_days_in_month() -> None:
    assert days_in_month(2024, 2) == 29
    assert days_in_month(2023, 2) == 28
    assert days_in_month(2023, 4) == 30
    assert days_in_month(2023, 12) == 31


def test_days_in_month_rejects_bad_month() -> None:
    with pytest.raises(ValueError):
        days_in_month(2023, 13)


def test_payment_dates_clamp_to_month_end() -> None:
    assert payment_dates(2023, 1, 31, 3) == ["2023-01-31", "2023-02-28", "2023-03-31"]


def test_payment_dates_roll_over_year() -> None:
    assert payment_dates(2023, 11, 15, 3) == ["2023-11-15", "2023-12-15", "2024-01-15"]
