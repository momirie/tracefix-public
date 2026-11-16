"""The assert head deleted from tests/test_slug.py (passes on base, fails on head)."""

from blog.slug import slugify


def test_rock_and_roll() -> None:
    assert slugify("Rock & Roll") == "rock-roll"
