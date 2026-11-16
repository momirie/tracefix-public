import asyncio

from a2a.client.transports.base import ClientTransport


def _make_transport():
    abstract = set(ClientTransport.__abstractmethods__)

    async def _noop(self, *a, **k):
        return None

    attrs = {name: _noop for name in abstract}
    attrs['closed'] = 0

    async def close(self):
        self.closed += 1

    attrs['close'] = close
    cls = type('FakeTransport', (ClientTransport,), attrs)
    return cls()


def test_async_with_calls_close():
    async def run():
        t = _make_transport()
        async with t as entered:
            assert entered is t
            assert t.closed == 0
        return t

    t = asyncio.run(run())
    assert t.closed == 1


def test_async_with_calls_close_on_exception():
    async def run():
        t = _make_transport()
        try:
            async with t:
                raise ValueError('boom')
        except ValueError:
            pass
        return t

    t = asyncio.run(run())
    assert t.closed == 1
