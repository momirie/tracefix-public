import pytest
from dlx import DB, Config
from dlx.marc import Bib
from dlx.marc.query import Query


def test_logical_field_wildcard_matches_beginning():
    DB.connect('mock://')
    old = dict(Config.bib_logical_fields)
    Config.bib_logical_fields['author'] = {'245': ['a']}
    try:
        Bib().set('245', 'a', 'German Smith').commit()
        Bib().set('245', 'a', 'Other Person').commit()
        q = Query.from_string('author:german*', record_type='bib')
        results = list(Bib.find(q.compile()))
        assert len(results) == 1
    finally:
        Config.bib_logical_fields.clear()
        Config.bib_logical_fields.update(old)
