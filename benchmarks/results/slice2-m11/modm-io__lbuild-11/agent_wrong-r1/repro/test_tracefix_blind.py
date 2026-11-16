import os
import sys

import pytest

sys.path.append(os.path.abspath("."))

import lbuild
import lbuild.parser


def test_find_modules_raises_on_nonexistent_module():
    parser = lbuild.parser.Parser()
    with pytest.raises(Exception):
        parser.find_modules(["repo:this:does:not:exist"])
