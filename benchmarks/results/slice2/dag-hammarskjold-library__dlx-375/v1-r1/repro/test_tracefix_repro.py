from bson.regex import Regex
from dlx.marc.query import WildcardRegex


def test_wildcard_regex_has_no_ignorecase_flag():
    r = WildcardRegex('^german.*')
    assert isinstance(r, Regex)
    assert r.pattern == '^german.*'
    # the fix removes the case-insensitive flag so the regex can use the index
    assert not (r.flags & 2)
