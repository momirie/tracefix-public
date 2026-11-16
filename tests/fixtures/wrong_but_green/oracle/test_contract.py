"""Documented contract: buckets truncate toward zero (holds on base, broken by head)."""

from stats.buckets import bucket_of


def test_negative_values_truncate_toward_zero() -> None:
    assert bucket_of(-5, 10) == 0
    assert bucket_of(-15, 10) == -10
