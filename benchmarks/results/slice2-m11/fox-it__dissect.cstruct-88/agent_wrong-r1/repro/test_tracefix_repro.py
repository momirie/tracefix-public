from dissect import cstruct
from dissect.cstruct.expression import Expression


def test_expression_with_tabs():
    cs = cstruct.cstruct()
    cs.consts["B"] = 5
    assert Expression(cs, "(B\t+\t3)\t").evaluate() == 8


def test_define_expression_with_tabs_as_array_size():
    cs = cstruct.cstruct()
    cdef = "#define B 5\n#define A\t(B + 3)\t// comment\nstruct t {\n    uint8 a[A];\n};\n"
    cs.load(cdef)
    assert len(cs.t(b"\x01" * 8).a) == 8
