from standings.ordinal import ordinals


def test_teens_use_th():
    assert ordinals([10, 11, 12, 13]) == ['10th', '11th', '12th', '13th']
