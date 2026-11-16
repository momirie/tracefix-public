import os
import sys
import logging
import warnings

sys.path.append(os.path.abspath("."))

import lbuild
import lbuild.parser


def test_nonexistent_module_gives_feedback(caplog):
    parser = lbuild.parser.Parser()
    caplog.set_level(logging.DEBUG)
    raised = False
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        try:
            parser.find_modules(["this:does:not:exist"])
        except Exception:
            raised = True
    feedback = raised or len(w) > 0 or len(caplog.records) > 0
    assert feedback, "no error or warning for a non-existing module"
