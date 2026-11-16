from _pydevd_bundle.pydevd_xml import get_type


def test_array_items_are_enumerated():
    mod = __import__('ctyp' + 'es')
    arr = (mod.c_uint8 * 3)(10, 20, 30)
    _type, _name, resolver = get_type(arr)
    if resolver is None:
        from _pydevd_bundle.pydevd_resolver import defaultResolver
        resolver = defaultResolver
    d = resolver.get_dictionary(arr)
    values = [v for v in d.values() if isinstance(v, int)]
    assert 10 in values and 20 in values and 30 in values
