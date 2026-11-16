import pytest

from textutil.trunc import truncate


def test_short_text_unchanged() -> None:
    assert truncate("hi", 5) == "hi"


def test_text_of_exact_length_unchanged() -> None:
    assert truncate("hello", 5) == "hello"


def test_empty_text() -> None:
    assert truncate("", 0) == ""


def test_truncate_adds_ellipsis() -> None:
    assert truncate("hello world", 5).endswith("…")


def test_negative_max_len_rejected() -> None:
    with pytest.raises(ValueError):
        truncate("hello", -1)
