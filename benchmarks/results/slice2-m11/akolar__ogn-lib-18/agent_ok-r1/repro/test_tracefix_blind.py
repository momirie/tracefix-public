import os
import sys
import importlib

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (root, os.path.join(root, 'src')):
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)

parse = None
for name in ('ogn.parser', 'ogn_parser'):
    try:
        parse = importlib.import_module(name).parse
        break
    except (ImportError, AttributeError):
        continue


def test_capturs_parser_registered_for_ogcapt():
    assert parse is not None
    msg = "FLRDDA5BA>OGCAPT,qAS,CAPTURS:/165829h4850.50N/00934.19E'/A=000000 id0ADDA5BA +000fpm"
    result = parse(msg)
    assert result is not None
    assert result.get('beacon_type') == 'capturs'
