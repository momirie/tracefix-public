import CppHeaderParser


def test_typedef_return_type_does_not_raise():
    h = """
typedef C A;

class B
{
public:
   A aMethod();
}
"""
    header = CppHeaderParser.CppHeader(h, "string")
    assert "B" in header.classes
    meth = header.classes["B"]["methods"]["public"][0]
    assert meth["name"] == "aMethod"
