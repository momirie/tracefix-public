from blog.slug import slugify


def test_slugify_lowercases_and_joins_words() -> None:
    assert slugify("Hello World") == "hello-world"
    assert slugify("Ten Tips for 2024") == "ten-tips-for-2024"


def test_slugify_folds_accents() -> None:
    assert slugify("Crème Brûlée") == "creme-brulee"


def test_slugify_keeps_existing_slug() -> None:
    assert slugify("already-a-slug") == "already-a-slug"


def test_slugify_empty_title() -> None:
    assert slugify("") == ""
