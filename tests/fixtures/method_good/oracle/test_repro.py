"""ISSUE: Version(1, 2, 3).bump("minor") -> 1.3.3 instead of 1.3.0."""

from vtools.version import Version


def test_minor_bump_resets_patch() -> None:
    assert Version(1, 2, 3).bump("minor") == Version(1, 3, 0)
