from gateway.listener import Listener


def test_port_none_does_not_crash_and_gives_default() -> None:
    listener = Listener()
    result = listener.port(None)
    assert result == listener.default_port
