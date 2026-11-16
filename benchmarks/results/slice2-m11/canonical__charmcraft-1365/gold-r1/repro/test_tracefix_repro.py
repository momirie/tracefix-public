from charmcraft.utils.package import get_pypi_packages, get_requirements_file_package_names


def test_get_pypi_packages_empty_lines():
    result = get_pypi_packages(["", "  ", "requests==2.0", "", "# comment"])
    assert result == {"requests==2.0"}


def test_requirements_file_with_blank_lines(tmp_path):
    req = tmp_path / "requirements.txt"
    req.write_text("ops\n\n\npyyaml==6.0\n\n")
    assert get_requirements_file_package_names(req) == {"ops", "pyyaml"}
