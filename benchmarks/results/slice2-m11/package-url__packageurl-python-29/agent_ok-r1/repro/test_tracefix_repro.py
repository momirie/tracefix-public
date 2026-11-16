from packageurl import PackageURL


def test_packageurl_is_hashable_and_usable_in_set():
    p1 = PackageURL(name='test', type='pypi')
    p2 = PackageURL(name='test', type='pypi')
    s = {p1}
    assert p2 in s
    assert len({p1, p2}) == 1
    assert hash(p1) == hash(p2)


def test_packageurl_with_qualifiers_hashable():
    p1 = PackageURL(name='test', type='pypi', qualifiers={'a': '1', 'b': '2'})
    p2 = PackageURL(name='test', type='pypi', qualifiers={'b': '2', 'a': '1'})
    assert len({p1, p2}) == 1
