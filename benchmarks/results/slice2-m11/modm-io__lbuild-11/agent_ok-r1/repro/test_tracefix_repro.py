import os
import sys
import pytest

sys.path.append(os.path.abspath("."))

import lbuild


def test_unknown_module_raises(tmp_path):
    (tmp_path / "repo.lb").write_text("""
def init(repo):
    repo.name = "repo"

def prepare(repo, options):
    repo.add_modules_recursive(".", modulefile="module.lb")
""")
    (tmp_path / "module.lb").write_text("""
def init(module):
    module.name = "mod"

def prepare(module, options):
    return True

def build(env):
    pass
""")
    builder = lbuild.api.Builder(cwd=str(tmp_path))
    builder.load([str(tmp_path / "repo.lb")])
    # valid module resolves without error
    result = builder._filter_modules(["repo:mod"])
    assert len(result) == 1
    # unknown module must be reported
    with pytest.raises(lbuild.exception.LbuildException):
        builder._filter_modules(["this:does:not:exist"])
