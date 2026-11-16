import pytest

from svc.config import DEFAULT_HOST, ConfigError, Settings, load_settings, parse_port


def test_parse_port_plain() -> None:
    assert parse_port("9000") == 9000


def test_parse_port_ignores_whitespace() -> None:
    assert parse_port(" 443\n") == 443


def test_parse_port_rejects_out_of_range() -> None:
    with pytest.raises(ConfigError):
        parse_port("0")
    with pytest.raises(ConfigError):
        parse_port("70000")


def test_load_settings_reads_host_and_port() -> None:
    env = {"HOST": "127.0.0.1", "PORT": "5000"}
    assert load_settings(env) == Settings(host="127.0.0.1", port=5000)


def test_parse_port_defaults_when_unset() -> None:
    assert parse_port(None) == 8080
    assert load_settings({}).port == 8080


def test_load_settings_default_host() -> None:
    assert load_settings({"PORT": "8000"}).host == DEFAULT_HOST
