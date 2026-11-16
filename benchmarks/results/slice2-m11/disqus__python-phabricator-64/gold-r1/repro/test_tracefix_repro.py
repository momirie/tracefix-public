import phabricator
from phabricator import Phabricator, Resource


def test_interface_method_name_does_not_conflict():
    api = Phabricator(username='u', certificate='c', host='http://localhost/api/')
    api._interface = phabricator.parse_interfaces({
        'almanac.interface.search': {
            'description': '', 'params': {}, 'return': ''
        },
        'almanac.device.search': {
            'description': '', 'params': {}, 'return': ''
        },
    })
    dev = api.almanac.device.search
    assert isinstance(dev, Resource)
    res = api.almanac.interface.search
    assert isinstance(res, Resource)
    assert res.endpoint == 'interface.search'
