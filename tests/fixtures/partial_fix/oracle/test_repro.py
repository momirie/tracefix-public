"""ISSUE: PORT unset -> AttributeError instead of falling back to 8080."""

from svc.config import load_settings, parse_port


def test_unset_port_falls_back_to_default() -> None:
    assert parse_port(None) == 8080
    assert load_settings({}).port == 8080
