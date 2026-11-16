import os
import sys

import pytest

sys.path.append(os.path.abspath("."))

import lbuild


def test_nonexistent_module_raises(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "repo.lb").write_text(
        "def init(repo):\n"
        "    repo.name = 'repo'\n"
        "def prepare(repo, options):\n"
        "    repo.add_modules_recursive('.')\n"
    )
    (repo_dir / "module.lb").write_text(
        "def init(module):\n"
        "    module.name = 'mod'\n"
        "def prepare(module, options):\n"
        "    return True\n"
        "def build(env):\n"
        "    pass\n"
    )
    parser = lbuild.parser.Parser()
    parser.parse_repository(str(repo_dir / "repo.lb"))
    parser.prepare_repositories()

    with pytest.raises(lbuild.exception.LbuildException):
        parser.find_modules(["This does not exist and is bullshit"])
