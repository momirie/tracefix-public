from datetime import date

import pytest

import acme_metrics
from metrics.report import iso_week, weekly_report


@pytest.fixture
def fake_totals(monkeypatch: pytest.MonkeyPatch) -> None:
    def weekly_totals(year: int, week: int) -> dict[str, int]:
        return {"signups": 12, "orders": 30}

    monkeypatch.setattr(acme_metrics, "weekly_totals", weekly_totals)


def test_iso_week_midweek() -> None:
    assert iso_week(date(2026, 4, 1)) == 14


def test_weekly_report_lists_metrics_sorted(fake_totals: None) -> None:
    report = weekly_report(date(2026, 4, 2))
    assert report.splitlines() == ["Week 14, 2026", "  orders: 30", "  signups: 12"]
