import httpx


async def asgi_app(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/plain")]})
    await send({"type": "http.response.body", "body": b"hello"})


def test_sync_client_with_asgi_app():
    with httpx.Client(app=asgi_app) as client:
        response = client.get("http://www.example.com/users/foo")
    assert response.status_code == 200
    assert response.text == "hello"
