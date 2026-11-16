import CppHeaderParser


def test_method_returning_typedef_of_unknown_type_does_not_raise():
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
