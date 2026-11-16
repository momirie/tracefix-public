import asyncio

import pytest

from asgiref.server import StatelessServer


class MyServer(StatelessServer):
    def __init__(self, application):
        super().__init__(application, max_applications=10)
        self.sent = []

    async def handle(self):
        pass

    async def application_send(self, scope, message):
        self.sent.append(message)


async def single_app(scope, receive, send):
    msg = await receive()
    await send({"scope": scope["value"], "message": msg["value"]})


@pytest.mark.asyncio
async def test_stateless_server_runs_single_callable():
    server = MyServer(single_app)
    queue = server.get_or_create_application_instance("id1", {"value": "woohoo"})
    queue.put_nowait({"value": 42})
    future = server.application_instances["id1"]["future"]
    await asyncio.wait_for(future, timeout=2)
    assert server.sent == [{"scope": "woohoo", "message": 42}]
