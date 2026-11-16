from pager.pagination import page_slice, total_pages


def test_last_partial_page_is_reachable() -> None:
    items = list(range(1, 11))
    assert total_pages(10, 3) == 4
    assert page_slice(items, 4, 3) == [10]


def test_all_orders_appear_across_pages() -> None:
    items = list(range(1, 11))
    seen = []
    for page in range(1, total_pages(len(items), 3) + 1):
        seen.extend(page_slice(items, page, 3))
    assert seen == items
