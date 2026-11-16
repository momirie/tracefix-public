"""Documented contract the partial fix misses: a blank PORT also means 8080."""

from svc.config import parse_port


def test_blank_port_falls_back_to_default() -> None:
    assert parse_port("") == 8080
