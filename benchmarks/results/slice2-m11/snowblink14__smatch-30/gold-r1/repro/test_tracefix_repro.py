import amr
import smatch


def test_top_matches_despite_label_mismatch():
    a1 = "(a / dog :ARG0 (b / cat))"
    a2 = "(a / cow :ARG0 (b / cat))"
    best, test_num, gold_num = smatch.get_amr_match(a1, a2)
    smatch.match_triple_dict.clear()
    # triples: 2 instances + 1 relation + TOP attribute = 4 each
    # matching: cat instance, ARG0 relation, TOP = 3 (dog vs cow instance mismatches)
    assert test_num == 4 and gold_num == 4
    assert best == 3
