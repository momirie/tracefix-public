import pytest

from pager.pagination import PageOutOfRange, page_slice, total_pages


def test_total_pages_exact_multiple() -> None:
    assert total_pages(9, 3) == 3
    assert total_pages(20, 10) == 2


def test_total_pages_empty() -> None:
    assert total_pages(0, 5) == 0


def test_page_slice_returns_requested_page() -> None:
    items = list(range(1, 10))
    assert page_slice(items, 1, 3) == [1, 2, 3]
    assert page_slice(items, 3, 3) == [7, 8, 9]


def test_page_slice_empty_collection_first_page() -> None:
    assert page_slice([], 1, 10) == []


def test_page_slice_out_of_range() -> None:
    items = list(range(6))
    with pytest.raises(PageOutOfRange):
        page_slice(items, 3, 3)
    with pytest.raises(PageOutOfRange):
        page_slice(items, 0, 3)


def test_invalid_sizes() -> None:
    with pytest.raises(ValueError):
        total_pages(5, 0)
    with pytest.raises(ValueError):
        total_pages(-1, 3)
    with pytest.raises(ValueError):
        page_slice([1, 2], 1, -1)
