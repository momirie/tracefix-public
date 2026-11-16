from dissect.cstruct import cstruct
from dissect.cstruct.expression import Expression


def test_tab_in_expression():
    cs = cstruct()
    assert Expression(cs, "1\t+\t2").evaluate() == 3


def test_tab_in_define():
    cs = cstruct()
    cs.load("#define A\t(1 + 2)\t// comment\n")
    assert cs.A == 3


def test_tab_in_trailing_expression():
    cs = cstruct()
    assert Expression(cs, "(1 + 2)\t").evaluate() == 3
