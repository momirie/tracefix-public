from dlx import DB
from dlx.marc import Bib, BibSet
from dlx.marc.query import Query


def test_wildcard_at_end_matches_start_of_value():
    DB.connect('mongomock://localhost')
    b1 = Bib()
    b1.set('245', 'a', 'german language')
    b1.commit()
    b2 = Bib()
    b2.set('245', 'a', 'not german')
    b2.commit()

    q = Query.from_string('245__a:german*', record_type='bib')
    found = list(BibSet.from_query(q.compile()))
    values = [b.get_value('245', 'a') for b in found]
    assert values == ['german language']
