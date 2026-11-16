from dissect.cstruct import cstruct
from dissect.cstruct.expression import Expression


def test_tab_in_expression_tokenizer():
    c = cstruct()
    assert Expression(c, "1\t+\t2").evaluate() == 3


def test_tabs_in_define():
    c = cstruct()
    c.load("#define B 1\n#define C 2\n#define A\t(B + C)\t// comment\n")
    assert c.consts["A"] == 3
