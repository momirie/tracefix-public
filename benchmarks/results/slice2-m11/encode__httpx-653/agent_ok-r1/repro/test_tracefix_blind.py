from httpx import URL


def test_url_params_merge_with_existing_query():
    url = URL("https://example.org:123/path/to/somewhere?b=456", params={"a": "123"})
    assert str(url) == "https://example.org:123/path/to/somewhere?b=456&a=123"
