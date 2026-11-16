from svc.config import load_settings, parse_port


def test_parse_port_unset_falls_back_to_default() -> None:
    assert parse_port(None) == 8080


def test_load_settings_without_port_uses_default() -> None:
    assert load_settings({}).port == 8080
