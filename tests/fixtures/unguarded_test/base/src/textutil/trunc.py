"""Shorten text so it fits fixed-width columns."""

DEFAULT_ELLIPSIS = "…"


def truncate(text: str, max_len: int, ellipsis: str = DEFAULT_ELLIPSIS) -> str:
    """Shorten `text` to fit in `max_len` characters, marking the cut with `ellipsis`.

    Text that already fits is returned unchanged. Raises ValueError if max_len is negative.
    """
    if max_len < 0:
        raise ValueError(f"max_len must not be negative, got {max_len}")
    if len(text) <= max_len:
        return text
    return text[:max_len] + ellipsis
