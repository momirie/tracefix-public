import pytest

from charmcraft.utils.package import get_pypi_packages, get_requirements_file_package_names


def test_get_pypi_packages_empty_lines():
    assert get_pypi_packages(["abc==1.0.0", "", "   ", "def"]) == {"abc==1.0.0", "def"}


def test_requirements_file_with_empty_lines(tmp_path):
    f = tmp_path / "requirements.txt"
    f.write_text("abc>=1.0\n\ndef==2.0\n\n")
    assert get_requirements_file_package_names(f) == {"abc", "def"}
