import httpx


def test_params_merge_with_existing_query_string():
    url = httpx.URL("https://example.org/get?a=1", params={"b": "2"})
    assert dict(httpx.QueryParams(url.query)) == {"a": "1", "b": "2"}
