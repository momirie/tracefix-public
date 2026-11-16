import asyncio

import pytest

from asgiref.server import StatelessServer


class Server(StatelessServer):
    def __init__(self, application):
        super().__init__(application, max_applications=10)
        self.sent = []

    async def handle(self):
        pass

    async def application_send(self, scope, message):
        self.sent.append(message)


async def single_app(scope, receive, send):
    msg = await receive()
    await send({"scope": scope["value"], "msg": msg})


@pytest.mark.asyncio
async def test_stateless_server_single_callable():
    server = Server(single_app)
    queue = server.get_or_create_application_instance("id1", {"value": 1})
    queue.put_nowait("hello")
    future = server.application_instances["id1"]["future"]
    await asyncio.wait_for(future, timeout=2)
    assert server.sent == [{"scope": 1, "msg": "hello"}]
