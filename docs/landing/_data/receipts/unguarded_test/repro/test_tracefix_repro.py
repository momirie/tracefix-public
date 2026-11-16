from textutil.trunc import truncate


def test_truncate_never_exceeds_max_len() -> None:
    result = truncate("hello world", 5)
    assert len(result) <= 5


def test_truncate_with_custom_ellipsis_within_max_len() -> None:
    result = truncate("hello world", 8, "...")
    assert len(result) <= 8
    assert result.endswith("...")
