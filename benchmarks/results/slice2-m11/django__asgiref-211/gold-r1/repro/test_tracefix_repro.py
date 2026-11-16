import asyncio

import pytest

from asgiref.server import StatelessServer


class MyServer(StatelessServer):
    def __init__(self, application):
        super().__init__(application)
        self.sent = []

    async def handle(self):
        pass

    async def application_send(self, scope, message):
        self.sent.append(message)


async def single_app(scope, receive, send):
    msg = await receive()
    await send({"scope": scope["value"], "message": msg})


@pytest.mark.asyncio
async def test_stateless_server_single_callable():
    server = MyServer(single_app)
    queue = server.get_or_create_application_instance("id1", {"value": "x"})
    queue.put_nowait(1)
    for _ in range(20):
        await asyncio.sleep(0)
        if server.sent:
            break
    future = server.application_instances["id1"]["future"]
    if future.done():
        future.result()
    assert server.sent == [{"scope": "x", "message": 1}]
