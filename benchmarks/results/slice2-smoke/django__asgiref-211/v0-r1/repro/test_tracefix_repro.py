import asyncio

import pytest

from asgiref.server import StatelessServer


class DummyServer(StatelessServer):
    def __init__(self, application):
        super().__init__(application, max_applications=10)
        self.sent = []

    async def handle(self):
        pass

    async def application_send(self, scope, message):
        self.sent.append(message)


@pytest.mark.asyncio
async def test_stateless_server_runs_single_callable_app():
    calls = []

    async def app(scope, receive, send):
        msg = await receive()
        calls.append((scope, msg))
        await send({"echo": msg})

    server = DummyServer(app)
    queue = server.get_or_create_application_instance("id1", {"type": "test"})
    queue.put_nowait({"hello": 1})
    for _ in range(10):
        await asyncio.sleep(0)
    future = server.application_instances["id1"]["future"]
    await asyncio.wait_for(future, 1)
    assert calls == [({"type": "test"}, {"hello": 1})]
    assert server.sent == [{"echo": {"hello": 1}}]
