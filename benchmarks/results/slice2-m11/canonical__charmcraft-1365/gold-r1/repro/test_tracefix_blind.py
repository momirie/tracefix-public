from charmcraft.utils.package import get_pypi_packages, get_requirements_file_package_names


def test_get_pypi_packages_empty_lines():
    lines = ["", "   ", "foo==1.0", "# comment", "", "bar"]
    assert get_pypi_packages(lines) == {"foo==1.0", "bar"}


def test_requirements_file_with_empty_lines(tmp_path):
    req = tmp_path / "requirements.txt"
    req.write_text("foo==1.0\n\nbar\n\n")
    assert get_requirements_file_package_names(req) == {"foo", "bar"}
