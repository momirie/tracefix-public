import re
from dlx.marc.query import Query


def test_wildcard_at_end_matches_beginning_of_value():
    # logical field style: author:german*
    q = Query.from_string('german*')
    # inspect the generated condition for a regex
    found = []

    def walk(o):
        if hasattr(o, 'pattern'):
            found.append(o)
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, (list, tuple)):
            for v in o:
                walk(v)

    walk(q.compile() if hasattr(q, 'compile') else q)
    assert found, 'no regex produced'
    rx = re.compile(found[0].pattern, re.I)
    assert rx.search('German Republic')
    assert not rx.search('East German')
