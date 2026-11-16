import os
import sys

import pytest

sys.path.append(os.path.abspath("."))

import lbuild


def test_find_modules_nonexistent_raises():
    repo = lbuild.repository.Repository(".")
    repo.name = "repo"
    m = lbuild.module.ModuleInit(repo, "/m1/module.lb")
    m.name = "module1"
    m.available = True
    lbuild.module.build_modules([m])

    parser = lbuild.parser.Parser()
    parser.add_repository(repo) if hasattr(parser, "add_repository") else None
    try:
        result = parser.find_modules("repo:doesnotexist")
    except lbuild.exception.LbuildException:
        return
    pytest.fail("No error for non-existing module, got %r" % (result,))
