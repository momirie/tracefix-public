"""Weekly metrics report, built on the internal acme_metrics client."""

from datetime import date

import acme_metrics


def iso_week(day: date) -> int:
    """ISO 8601 week number of `day`: weeks start on Monday, week 1 holds 4 January."""
    return day.isocalendar().week


def weekly_report(day: date) -> str:
    """Render the metrics for the week containing `day` as plain text."""
    week = iso_week(day)
    totals = acme_metrics.weekly_totals(year=day.year, week=week)
    lines = [f"Week {week}, {day.year}"]
    for name in sorted(totals):
        lines.append(f"  {name}: {totals[name]}")
    return "\n".join(lines)
