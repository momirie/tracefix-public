import pytest

from a2a.client.transports.base import ClientTransport


def _make_transport_class():
    ns = {}
    for name in ClientTransport.__abstractmethods__:
        ns[name] = lambda self, *a, **k: None

    async def close(self):
        self.closed = True

    ns['close'] = close
    return type('Dummy', (ClientTransport,), ns)


@pytest.mark.asyncio
async def test_async_with_closes_transport():
    t = _make_transport_class()()
    t.closed = False
    async with t as entered:
        assert entered is t
        assert t.closed is False
    assert t.closed is True


@pytest.mark.asyncio
async def test_async_with_closes_on_exception():
    t = _make_transport_class()()
    t.closed = False
    with pytest.raises(ValueError):
        async with t:
            raise ValueError('boom')
    assert t.closed is True
