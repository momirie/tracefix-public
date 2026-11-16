import docopt

import dphon.cli as cli


def _opt(name):
    for o in docopt.parse_defaults(cli.__doc__):
        if o.long == name:
            return o
    return None


def test_min_default_is_eight():
    opt = _opt("--min")
    assert opt is not None
    assert opt.value is not None
    assert int(opt.value) == 8
