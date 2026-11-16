"""The documented bump contract, checked exhaustively on small versions. Head satisfies it."""

import itertools

import pytest

from vtools.version import Version

RANGE = range(6)


def expected(version: Version, part: str) -> Version:
    if part == "major":
        return Version(version.major + 1, 0, 0)
    if part == "minor":
        return Version(version.major, version.minor + 1, 0)
    return Version(version.major, version.minor, version.patch + 1)


def test_bump_follows_the_documented_contract() -> None:
    for major, minor, patch in itertools.product(RANGE, RANGE, RANGE):
        version = Version(major, minor, patch)
        for part in ("major", "minor", "patch"):
            assert version.bump(part) == expected(version, part)


def test_other_parts_raise_value_error() -> None:
    for major, minor, patch in itertools.product(RANGE, RANGE, RANGE):
        for part in ("build", "", "Minor"):
            with pytest.raises(ValueError):
                Version(major, minor, patch).bump(part)
