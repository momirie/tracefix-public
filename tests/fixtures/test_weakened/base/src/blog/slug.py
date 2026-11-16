"""URL slugs for blog post titles."""

import re
import unicodedata

_SEPARATORS = re.compile(r"[^a-z0-9]+")


def _ascii_fold(text: str) -> str:
    """Drop accents so 'Crème Brûlée' becomes 'Creme Brulee'."""
    decomposed = unicodedata.normalize("NFKD", text)
    return decomposed.encode("ascii", "ignore").decode("ascii")


def slugify(title: str) -> str:
    """Turn a post title into a lowercase, dash-separated slug for its URL."""
    return _SEPARATORS.sub("-", _ascii_fold(title).lower())
