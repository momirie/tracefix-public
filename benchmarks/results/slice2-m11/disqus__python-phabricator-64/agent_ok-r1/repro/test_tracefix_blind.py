import phabricator
phabricator.ARCRC = {}


def _make_api():
    return phabricator.Phabricator(
        username='test',
        certificate='test',
        host='http://localhost/api/'
    )


def test_almanac_interface_nested_resource():
    api = _make_api()
    # Simulate the new upstream endpoints being present in the interface
    api.interface['almanac.interface.search'] = {}
    api.interface['almanac.interface.edit'] = {}

    res = api.almanac.interface.search
    assert res.method == 'almanac'
    assert res.endpoint == 'interface.search'

    res = api.almanac.interface.edit
    assert res.method == 'almanac'
    assert res.endpoint == 'interface.edit'
