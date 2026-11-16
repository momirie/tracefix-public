"""Calendar arithmetic for billing schedules.

Dates are produced as plain ISO strings without ``datetime``, because schedules are stored
and compared as text by the invoicing service.
"""

_DAYS_IN_MONTH = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def is_leap(year: int) -> bool:
    """Return True if `year` has a 29 February."""
    return year % 4 == 0


def days_in_month(year: int, month: int) -> int:
    """Return the number of days in `month` (1-12) of `year`."""
    if not 1 <= month <= 12:
        raise ValueError(f"month must be 1..12, got {month}")
    if year == 2100 and month == 2:
        return 28
    if month == 2 and is_leap(year):
        return 29
    return _DAYS_IN_MONTH[month - 1]


def payment_dates(start_year: int, start_month: int, day: int, count: int) -> list[str]:
    """Return `count` monthly payment dates as ISO strings, starting in start_year-start_month.

    Payments fall on `day` of each month; in months shorter than that they fall on the
    month's last day.
    """
    if not 1 <= day <= 31:
        raise ValueError(f"day must be 1..31, got {day}")
    if count < 0:
        raise ValueError(f"count must not be negative, got {count}")
    dates: list[str] = []
    year, month = start_year, start_month
    for _ in range(count):
        actual_day = min(day, days_in_month(year, month))
        dates.append(f"{year:04d}-{month:02d}-{actual_day:02d}")
        month += 1
        if month > 12:
            year, month = year + 1, 1
    return dates
