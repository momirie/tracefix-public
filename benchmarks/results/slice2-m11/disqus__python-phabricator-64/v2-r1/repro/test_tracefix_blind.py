from phabricator import Phabricator, Resource


def test_almanac_interface_search_resource():
    phab = Phabricator(username='u', certificate='c', host='http://localhost/api/', token='api-xxxx')
    phab.interface['almanac.interface.search'] = {'required': {}, 'optional': {}, 'formatted': {}}
    phab.interface['almanac.interface.edit'] = {'required': {}, 'optional': {}, 'formatted': {}}
    res = phab.almanac.interface.search
    assert isinstance(res, Resource)
