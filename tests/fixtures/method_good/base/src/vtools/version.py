"""Semantic version numbers."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Version:
    """A major.minor.patch version. Parts must not be negative."""

    major: int
    minor: int = 0
    patch: int = 0

    def __post_init__(self) -> None:
        if self.major < 0 or self.minor < 0 or self.patch < 0:
            raise ValueError("version parts must not be negative")

    def bump(self, part: str) -> "Version":
        """Return the next version.

        Bumping "major" resets minor and patch, "minor" resets patch, and "patch" increments
        patch. Any other part raises ValueError.

        >>> Version(1, 2, 3).bump("minor")
        Version(major=1, minor=3, patch=0)
        """
        if part == "major":
            return Version(self.major + 1, 0, 0)
        if part == "minor":
            return Version(self.major, self.minor + 1, self.patch)
        if part == "patch":
            return Version(self.major, self.minor, self.patch + 1)
        raise ValueError(f"unknown version part: {part!r}")
