from stats.buckets import bucket_of, histogram


def test_bucket_of_large_value_exact() -> None:
    assert bucket_of(100000000000000015, 10) == 100000000000000010


def test_bucket_of_large_value_on_boundary() -> None:
    assert bucket_of(100000000000000019, 10) == 100000000000000010


def test_histogram_large_values() -> None:
    assert histogram([100000000000000015], 10) == {100000000000000010: 1}
