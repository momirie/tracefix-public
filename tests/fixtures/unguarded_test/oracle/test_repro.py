"""ISSUE: truncate() returns more than max_len characters."""

from textutil.trunc import truncate


def test_result_fits_max_len() -> None:
    result = truncate("hello world", 5)
    assert len(result) <= 5
    assert result == "hell…"
