from dissect.cstruct import cstruct
from dissect.cstruct.expression import Expression


def test_tab_in_expression():
    cs = cstruct()
    assert Expression(cs, "1\t+\t2").evaluate() == 3
    assert Expression(cs, "(1\t+ 2)\t* 2").evaluate() == 6


def test_tab_in_define():
    cs = cstruct()
    cs.load("#define B 2\n#define C 3\n#define A\t(B + C)\t// comment\n")
    assert cs.A == 5
