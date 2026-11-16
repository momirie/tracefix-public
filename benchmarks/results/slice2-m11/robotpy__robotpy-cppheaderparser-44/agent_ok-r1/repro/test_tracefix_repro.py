import CppHeaderParser


def test_method_returning_typedef_of_undeclared_type():
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
    methods = header.classes["B"]["methods"]["public"]
    assert len(methods) == 1
    assert methods[0]["name"] == "aMethod"
