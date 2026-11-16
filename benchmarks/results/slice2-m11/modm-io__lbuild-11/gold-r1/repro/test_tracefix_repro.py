import os
import sys

import pytest

sys.path.append(os.path.abspath("."))

import lbuild
from lbuild.exception import LbuildException
from lbuild.api import Builder


def test_find_modules_nonexistent_raises(tmp_path):
    repo = tmp_path / "repo.lb"
    repo.write_text(
        "def init(repo):\n"
        "    repo.name = 'repo'\n"
        "def prepare(repo, options):\n"
        "    repo.add_modules_recursive('.')\n"
        "def build(env):\n"
        "    pass\n"
    )
    mod = tmp_path / "module.lb"
    mod.write_text(
        "def init(module):\n"
        "    module.name = 'mod'\n"
        "def prepare(module, options):\n"
        "    return True\n"
        "def build(env):\n"
        "    pass\n"
    )
    builder = Builder()
    builder.load([str(repo)]) if hasattr(builder, "load") else None
    with pytest.raises(LbuildException):
        builder.parser.find_modules("this:does:not:exist")
