"""ISSUE: week number off by one on Mondays."""

from datetime import date

from metrics.report import iso_week


def test_monday_week_number() -> None:
    assert iso_week(date(2026, 3, 30)) == 14
