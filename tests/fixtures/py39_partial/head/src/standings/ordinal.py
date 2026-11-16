"""Ordinal positions for league tables: 1st, 2nd, 3rd, 4th ..."""

from collections import Iterable

SUFFIXES = {1: "st", 2: "nd", 3: "rd"}


def ordinal(n):
    """Return position n with its English ordinal suffix: "1st", "2nd", "3rd", "4th", "11th",
    "12th", "13th", "21st", "22nd", "101st", "111th", "112th".

    A number ending in 11, 12 or 13 takes "th"; otherwise its last digit picks the suffix.
    n must be a whole number >= 1; anything else raises ValueError.
    """
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise ValueError(f"not a position: {n!r}")
    if n in (11, 12, 13):
        return f"{n}th"
    return f"{n}{SUFFIXES.get(n % 10, 'th')}"


def ordinals(positions):
    """ordinal() of one position, or a list of them for an iterable of positions."""
    if isinstance(positions, Iterable):
        return [ordinal(p) for p in positions]
    return ordinal(positions)
