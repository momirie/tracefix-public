import phabricator
phabricator.ARCRC = {}


def test_almanac_interface_nested_resource():
    api = phabricator.Phabricator(
        username='test',
        certificate='test',
        host='http://localhost/api/'
    )
    res = api.almanac.interface.search
    assert isinstance(res, phabricator.Resource)
    assert not isinstance(api.almanac.interface, dict)
