from dissect.cstruct import cstruct
from dissect.cstruct.expression import Expression


def test_tab_in_expression():
    cs = cstruct()
    assert Expression(cs, "(1\t+\t2)\t* 3").evaluate() == 9


def test_tab_in_define():
    cs = cstruct()
    cs.load("#define B 1\n#define C 2\n#define A\t(B\t+\tC)\t// comment\n")
    assert cs.A == 3
