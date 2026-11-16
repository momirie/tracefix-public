import asyncio

import pytest

from asgiref.server import StatelessServer


class DummyServer(StatelessServer):
    async def handle(self):
        pass

    async def application_send(self, scope, message):
        pass


@pytest.mark.asyncio
async def test_stateless_server_runs_single_callable_application():
    called = []

    async def app(scope, receive, send):
        message = await receive()
        called.append((scope, message))

    server = DummyServer(app)
    scope = {"type": "test"}
    queue = server.get_or_create_application_instance("id1", scope)
    queue.put_nowait({"hello": 1})
    await asyncio.wait_for(server.application_instances["id1"]["future"], timeout=2)
    assert called == [(scope, {"hello": 1})]
