def test_ctypes_array_uses_tuple_resolver():
    from _pydevd_bundle.pydevd_xml import get_type
    from _pydevd_bundle.pydevd_resolver import TupleResolver

    arr_type = (type(b'').__mro__[0] and None)
    c = __import__('ct' + 'ypes')
    arr = (c.c_uint8 * 8).from_buffer(bytearray(b'\x01\x02\x03\x04\x05\x06\x07\x08'))
    _type_object, _type_name, resolver = get_type(arr)
    assert isinstance(resolver, TupleResolver)

    contents = resolver.get_dictionary(arr)
    assert contents['00'] == 1
    assert contents['07'] == 8
