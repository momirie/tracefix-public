"""Fixed-width histogram buckets for integer measurements."""

from collections import Counter
from collections.abc import Iterable


def bucket_of(value: int, width: int) -> int:
    """Return the start of the bucket of size `width` that contains `value`.

    Buckets truncate toward zero so the histogram is symmetric around 0:
    bucket_of(-5, 10) == 0, bucket_of(-15, 10) == -10.
    """
    if width <= 0:
        raise ValueError(f"width must be positive, got {width}")
    return value // width * width


def histogram(values: Iterable[int], width: int) -> dict[int, int]:
    """Count values per bucket, keyed by bucket start, in ascending bucket order."""
    if width <= 0:
        raise ValueError(f"width must be positive, got {width}")
    counts = Counter(bucket_of(value, width) for value in values)
    return dict(sorted(counts.items()))
