"""ISSUE: trailing punctuation leaves a trailing dash."""

from blog.slug import slugify


def test_no_trailing_dash() -> None:
    assert slugify("Hello World!") == "hello-world"
