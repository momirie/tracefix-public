import pytest

from stats.buckets import bucket_of, histogram


def test_bucket_of_small_values() -> None:
    assert bucket_of(0, 10) == 0
    assert bucket_of(9, 10) == 0
    assert bucket_of(10, 10) == 10
    assert bucket_of(25, 10) == 20


def test_bucket_of_large_values() -> None:
    assert bucket_of(100000000000000015, 10) == 100000000000000010


def test_bucket_of_width_one() -> None:
    assert bucket_of(7, 1) == 7


def test_bucket_of_rejects_bad_width() -> None:
    with pytest.raises(ValueError):
        bucket_of(5, 0)
    with pytest.raises(ValueError):
        bucket_of(5, -10)


def test_histogram_counts_per_bucket() -> None:
    assert histogram([1, 2, 11, 25, 29], 10) == {0: 2, 10: 1, 20: 2}


def test_histogram_empty() -> None:
    assert histogram([], 5) == {}
