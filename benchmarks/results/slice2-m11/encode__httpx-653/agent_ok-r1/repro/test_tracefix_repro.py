from httpx import URL


def test_url_params_merge_with_existing_query():
    url = URL("https://example.org:123/path/to/somewhere?b=456", params={"a": "123"})
    query = url.query
    assert "a=123" in query.split("&")
    assert "b=456" in query.split("&")
