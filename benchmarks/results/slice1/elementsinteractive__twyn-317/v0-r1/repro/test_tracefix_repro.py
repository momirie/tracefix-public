from twyn.trusted_packages.references.top_pypi_reference import TopPyPiReference
from twyn.trusted_packages.references.top_npm_reference import TopNpmReference


def test_default_sources_are_vendored_in_repo():
    for cls in (TopPyPiReference, TopNpmReference):
        assert "github" in cls.DEFAULT_SOURCE and "elementsinteractive/twyn" in cls.DEFAULT_SOURCE
