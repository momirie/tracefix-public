import re
from dlx import DB
from dlx.marc.query import Query


class _Coll:
    def __init__(self, rec):
        self.rec = rec

    def find(self, query, *a, **k):
        self.rec.append(query)
        return []


class _Handle:
    def __init__(self):
        self.rec = []

    def __getitem__(self, name):
        return _Coll(self.rec)


def test_wildcard_at_end_matches_start_of_index_value():
    old = DB.handle
    h = _Handle()
    DB.handle = h
    try:
        try:
            Query.from_string('245__a:german*', record_type='bib')
        except Exception:
            pass
    finally:
        DB.handle = old
    assert h.rec
    rx = h.rec[0]['subfields.value']
    # index text values start with a space
    assert re.search(rx.pattern, ' german language')
    assert not re.search(rx.pattern, ' not german')
