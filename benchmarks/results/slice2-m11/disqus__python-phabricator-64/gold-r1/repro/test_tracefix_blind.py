from phabricator import Phabricator, Resource


def test_almanac_interface_search_is_resource():
    phab = Phabricator(host='http://localhost/api/', username='u', certificate='c', token='api-x')
    phab.api = phab
    phab.interface['almanac.interface.search'] = {'required': {}, 'optional': {}}
    phab.interface['almanac.interface.edit'] = {'required': {}, 'optional': {}}
    res = phab.almanac.interface.search
    assert isinstance(res, Resource)
    assert res.endpoint == 'search' or res.endpoint == 'almanac.interface.search'
