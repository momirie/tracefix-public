import os
import sys

sys.path.append(os.path.abspath("."))

import lbuild


def test_unresolvable_dependency_not_printed_to_stdout(tmp_path, capsys):
    (tmp_path / "repo.lb").write_text(
        "def init(repo):\n    repo.name = 'repo'\n"
        "def prepare(repo, options):\n"
        "    repo.add_modules('mod/module.lb')\n")
    (tmp_path / "mod").mkdir()
    (tmp_path / "mod" / "module.lb").write_text(
        "def init(module):\n    module.name = 'mod'\n"
        "def prepare(module, options):\n    module.depends(':doesnotexist')\n    return True\n"
        "def build(env):\n    pass\n")
    parser = lbuild.parser.Parser()
    parser.parse_repository(str(tmp_path / "repo.lb"))
    parser.prepare_repositories()
    out = capsys.readouterr().out
    assert "ignoring" not in out
