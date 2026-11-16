import smatch
from smatch import get_amr_match


def test_top_not_penalized_when_label_differs():
    a1 = "(a / dog :ARG0 (b / cat))"
    a2 = "(a / puppy :ARG0 (b / cat))"
    best, t1, t2 = get_amr_match(a1, a2)
    # triples: instances 2, relation 1 (ARG0), TOP attribute 1 => 4 total
    # matches: instance b, relation ARG0, TOP (top node same position) = 3
    assert best == 3
