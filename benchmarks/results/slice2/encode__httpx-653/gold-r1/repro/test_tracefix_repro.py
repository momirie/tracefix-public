import httpx
from httpx import URL, QueryParams


def test_params_merge_with_url_query_string():
    url = URL("https://example.org/get?a=1", params={"b": "2"})
    q = QueryParams(url.query)
    assert q["a"] == "1"
    assert q["b"] == "2"


def test_request_params_merge_with_url_query_string():
    request = httpx.Request("GET", "https://example.org/get?a=1", params={"b": "2"})
    q = QueryParams(request.url.query)
    assert q["a"] == "1"
    assert q["b"] == "2"
