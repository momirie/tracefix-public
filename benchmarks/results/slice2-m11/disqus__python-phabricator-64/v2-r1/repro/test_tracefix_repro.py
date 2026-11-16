import phabricator


def test_interface_conduit_method_name_not_shadowed():
    api = phabricator.Phabricator(username='test', certificate='test', host='http://localhost')
    api._interface = {
        'almanac.interface.search': {
            'description': 'x',
            'params': {},
        },
    }
    res = api.almanac.interface.search
    assert isinstance(res, phabricator.Resource)
