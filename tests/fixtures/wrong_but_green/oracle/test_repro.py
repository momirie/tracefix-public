"""ISSUE: large values land in the wrong bucket."""

from stats.buckets import bucket_of


def test_large_value_bucket() -> None:
    assert bucket_of(100000000000000015, 10) == 100000000000000010
