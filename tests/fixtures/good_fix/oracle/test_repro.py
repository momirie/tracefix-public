"""ISSUE: 10 orders at 3 per page -> order #10 never shown, page 4 raises."""

from pager.pagination import page_slice, total_pages


def test_last_partial_page_is_reachable() -> None:
    items = [f"order-{i}" for i in range(1, 11)]
    assert total_pages(10, 3) == 4
    assert page_slice(items, 4, 3) == [items[9]]
