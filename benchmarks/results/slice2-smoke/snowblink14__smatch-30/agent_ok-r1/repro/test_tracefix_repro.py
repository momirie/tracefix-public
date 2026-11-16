import smatch


def test_top_matches_despite_root_label_mismatch():
    amr1 = "(w / want-01 :ARG0 (b / boy) :ARG1 (g / girl))"
    amr2 = "(d / desire-01 :ARG0 (b / boy) :ARG1 (g / girl))"
    match_num, test_num, gold_num = smatch.get_amr_match(amr1, amr2, justattribute=True)
    assert test_num == 1 and gold_num == 1
    assert match_num == 1
