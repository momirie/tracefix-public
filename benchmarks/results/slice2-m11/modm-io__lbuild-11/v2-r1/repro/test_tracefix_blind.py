import os
import sys
import pytest

sys.path.append(os.path.abspath("."))

import lbuild
import lbuild.parser
import lbuild.exception

REPO = '''
def init(repo):
    repo.name = "repo"

def prepare(repo, options):
    repo.add_modules_recursive(".") if hasattr(repo, "add_modules_recursive") else repo.find_modules_recursive(".")
'''

MODULE = '''
def init(module):
    module.name = "mod"

def prepare(module, options):
    return True

def build(env):
    pass
'''


def test_unknown_requested_module_raises(tmp_path):
    (tmp_path / "repo.lb").write_text(REPO)
    (tmp_path / "module.lb").write_text(MODULE)
    parser = lbuild.parser.Parser()
    parser.parse_repository(str(tmp_path / "repo.lb"))
    parser.prepare_repositories()
    with pytest.raises(lbuild.exception.LbuildException):
        parser.resolve_dependencies(["repo:doesnotexist"])
