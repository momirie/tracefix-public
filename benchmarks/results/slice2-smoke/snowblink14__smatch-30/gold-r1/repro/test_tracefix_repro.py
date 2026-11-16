import amr
import smatch


def test_top_matches_even_if_labels_differ():
    a1 = "(a / cat)"
    a2 = "(b / dog)"
    match, test_num, gold_num = smatch.get_amr_match(a1, a2)
    # instance triple differs (cat vs dog), but TOP attribute should match
    # triples: instance(a), TOP attribute => 2 each; TOP must match -> 1
    assert test_num == 2
    assert gold_num == 2
    assert match == 1
