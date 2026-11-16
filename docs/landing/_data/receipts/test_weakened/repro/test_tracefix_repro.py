from blog.slug import slugify


def test_slugify_no_trailing_dash_for_trailing_punctuation() -> None:
    assert slugify("Hello World!") == "hello-world"
