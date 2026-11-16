from vtools.version import Version


def test_bump_minor_resets_patch() -> None:
    assert Version(1, 2, 3).bump("minor") == Version(1, 3, 0)
