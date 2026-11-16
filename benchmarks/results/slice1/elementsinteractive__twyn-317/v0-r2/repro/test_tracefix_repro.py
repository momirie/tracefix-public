from unittest.mock import patch, Mock

from twyn.trusted_packages.references.top_pypi_reference import TopPyPiReference
from twyn.trusted_packages.references.top_npm_reference import TopNpmReference


def test_pypi_default_source_is_vendored_in_repo():
    assert "elementsinteractive/twyn" in TopPyPiReference.DEFAULT_SOURCE


def test_npm_default_source_is_vendored_in_repo():
    assert "elementsinteractive/twyn" in TopNpmReference.DEFAULT_SOURCE


def test_vendored_format_is_parsed():
    ref = TopPyPiReference(source="https://example.com/x.json", cache_handler=None)
    resp = Mock()
    resp.json.return_value = {"packages": ["requests", "flask"]}
    with patch("twyn.trusted_packages.references.base.requests.get", return_value=resp):
        assert ref.get_packages() == {"requests", "flask"}
