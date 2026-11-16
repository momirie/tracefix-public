import os
import sys

sys.path.append(os.path.abspath("."))

import lbuild


REPO = '''
def init(repo):
    repo.name = 'repo'

def prepare(repo, options):
    for n in ('add_modules_recursive', 'find_modules_recursive', 'find_modules_recursively'):
        f = getattr(repo, n, None)
        if f is not None:
            f('.')
            break
    else:
        raise RuntimeError('no recursive module finder')

def build(env):
    pass
'''

MODULE = '''
def init(module):
    module.name = 'mod'

def prepare(module, options):
    module.depends('repo:doesnotexist')
    return True

def build(env):
    pass
'''


def test_unresolved_dependency_does_not_print_to_stdout(tmp_path, capsys):
    (tmp_path / "repo.lb").write_text(REPO)
    (tmp_path / "mod").mkdir()
    (tmp_path / "mod" / "module.lb").write_text(MODULE)
    parser = lbuild.parser.Parser()
    parser.parse_repository(str(tmp_path / "repo.lb"))
    capsys.readouterr()
    parser.prepare_repositories()
    out = capsys.readouterr().out
    assert "ignoring" not in out
