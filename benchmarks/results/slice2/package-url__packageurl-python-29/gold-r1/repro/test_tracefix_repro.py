from packageurl import PackageURL


def test_packageurl_is_hashable_and_usable_in_set():
    a = PackageURL(name='test', type='pypi')
    b = PackageURL(name='test', type='pypi')
    c = PackageURL(name='other', type='pypi')
    s = {a, b, c}
    assert len(s) == 2
    assert a in s
    assert hash(a) == hash(b)
