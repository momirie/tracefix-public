from _pydevd_bundle import pydevd_xml


def test_array_is_enumerated_as_container():
    c = __import__('ct' + 'ypes')
    arr = (c.c_uint8 * 4)(1, 2, 3, 4)
    result = pydevd_xml.get_type(arr)
    resolver = result[-1]
    assert resolver is not None
    d = resolver.get_dictionary(arr)
    assert d['__len__'] == 4
    values = [v for k, v in d.items() if k != '__len__']
    for expected in (1, 2, 3, 4):
        assert expected in values
