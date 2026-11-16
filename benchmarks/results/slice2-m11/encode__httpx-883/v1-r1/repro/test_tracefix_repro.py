import httpx


async def asgi_app(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"hi"})


def test_client_docstring_says_wsgi():
    doc = httpx.Client.__doc__
    app_lines = [l for l in doc.splitlines() if "**app**" in l]
    assert app_lines
    assert "WSGI" in app_lines[0]
    assert "ASGI" not in app_lines[0]
