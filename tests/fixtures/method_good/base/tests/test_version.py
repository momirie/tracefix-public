import pytest

from vtools.version import Version


def test_bump_major_resets_minor_and_patch() -> None:
    assert Version(1, 2, 3).bump("major") == Version(2, 0, 0)


def test_bump_patch() -> None:
    assert Version(1, 2, 3).bump("patch") == Version(1, 2, 4)


def test_bump_unknown_part() -> None:
    with pytest.raises(ValueError):
        Version(1, 2, 3).bump("build")


def test_negative_parts_rejected() -> None:
    with pytest.raises(ValueError):
        Version(1, -1, 0)


def test_defaults() -> None:
    assert Version(3) == Version(3, 0, 0)
