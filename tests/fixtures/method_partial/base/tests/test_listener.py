import pytest

from gateway.listener import Listener


def test_port_plain() -> None:
    assert Listener().port("9000") == 9000


def test_port_ignores_whitespace_and_default_port() -> None:
    assert Listener(default_port=9000).port(" 443 ") == 443


def test_port_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        Listener().port("0")
    with pytest.raises(ValueError):
        Listener().port("70000")


def test_port_rejects_words() -> None:
    with pytest.raises(ValueError):
        Listener().port("http")
