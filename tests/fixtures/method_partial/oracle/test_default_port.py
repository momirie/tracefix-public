"""Documented contract the partial fix misses: the default is the object's default_port."""

from gateway.listener import Listener


def test_unset_port_gives_the_object_default_port() -> None:
    assert Listener(default_port=9000).port(None) == 9000
