"""Documented contract the partial fix misses: a blank value also gives the default port."""

from gateway.listener import Listener


def test_blank_port_gives_default() -> None:
    assert Listener().port("") == 8080
