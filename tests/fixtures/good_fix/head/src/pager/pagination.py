"""Pagination helpers for list views.

Pages are numbered from 1. Asking for page 1 of an empty collection returns an empty
list instead of raising, so list views can render their "nothing here yet" state.
"""

from collections.abc import Sequence
from typing import TypeVar

T = TypeVar("T")


class PageOutOfRange(LookupError):
    """Raised when a caller asks for a page that does not exist."""


def _check_sizes(n_items: int, per_page: int) -> None:
    if per_page <= 0:
        raise ValueError(f"per_page must be positive, got {per_page}")
    if n_items < 0:
        raise ValueError(f"n_items must not be negative, got {n_items}")


def total_pages(n_items: int, per_page: int) -> int:
    """Return how many pages are needed to show n_items, per_page at a time."""
    _check_sizes(n_items, per_page)
    return (n_items + per_page - 1) // per_page


def page_slice(items: Sequence[T], page: int, per_page: int) -> list[T]:
    """Return the items shown on `page` (1-indexed).

    Raises PageOutOfRange if the page does not exist.
    """
    n_items = len(items)
    last_page = total_pages(n_items, per_page)
    if page == 1 and n_items == 0:
        return []
    if page < 1 or page > last_page:
        raise PageOutOfRange(f"page {page} is outside 1..{last_page}")
    start = (page - 1) * per_page
    return list(items[start : start + per_page])
