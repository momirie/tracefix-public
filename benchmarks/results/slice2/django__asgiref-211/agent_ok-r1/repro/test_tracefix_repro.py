import asyncio

import pytest

from asgiref.server import StatelessServer


class DummyServer(StatelessServer):
    async def handle(self):
        pass

    async def application_send(self, scope, message):
        self.sent = (scope, message)


@pytest.mark.asyncio
async def test_stateless_server_runs_single_callable():
    called = {}

    async def app(scope, receive, send):
        msg = await receive()
        called["scope"] = scope
        called["msg"] = msg
        await send({"ok": 1})

    server = DummyServer(app)
    scope = {"type": "test"}
    queue = server.get_or_create_application_instance("id1", scope)
    queue.put_nowait({"hello": "world"})
    future = server.application_instances["id1"]["future"]
    await asyncio.wait_for(future, timeout=2)
    assert called["scope"] == scope
    assert called["msg"] == {"hello": "world"}
    assert server.sent == (scope, {"ok": 1})
