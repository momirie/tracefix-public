"""Exhaustive small-range check of the documented pagination contract.

Passing on head is our evidence that good_fix has no counterexample: any Break My Fix
finding on good_fix is a false alarm.
"""

import pytest
from pager.pagination import PageOutOfRange, page_slice, total_pages

MAX_ITEMS = 60
MAX_PER_PAGE = 15


def test_total_pages_is_ceiling_division() -> None:
    for n in range(MAX_ITEMS):
        for per_page in range(1, MAX_PER_PAGE):
            assert total_pages(n, per_page) == -(-n // per_page), (n, per_page)


def test_pages_partition_items_in_order() -> None:
    for n in range(1, MAX_ITEMS):
        items = list(range(n))
        for per_page in range(1, MAX_PER_PAGE):
            last = total_pages(n, per_page)
            pages = [page_slice(items, p, per_page) for p in range(1, last + 1)]
            assert all(pages), (n, per_page)
            assert [x for page in pages for x in page] == items, (n, per_page)
            for bad in (0, last + 1):
                with pytest.raises(PageOutOfRange):
                    page_slice(items, bad, per_page)


def test_empty_collection_has_an_empty_first_page() -> None:
    for per_page in range(1, MAX_PER_PAGE):
        assert total_pages(0, per_page) == 0
        assert page_slice([], 1, per_page) == []
        with pytest.raises(PageOutOfRange):
            page_slice([], 2, per_page)
