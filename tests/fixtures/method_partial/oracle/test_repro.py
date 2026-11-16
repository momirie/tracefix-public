"""ISSUE: Listener().port(None) -> AttributeError instead of the default port."""

from gateway.listener import Listener


def test_unset_port_gives_default() -> None:
    assert Listener().port(None) == 8080
