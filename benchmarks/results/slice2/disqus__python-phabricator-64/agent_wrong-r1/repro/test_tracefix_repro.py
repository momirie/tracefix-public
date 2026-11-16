import phabricator
from phabricator import Phabricator


def test_almanac_interface_attribute_is_conduit_method():
    phab = Phabricator(username='test', certificate='test', host='http://localhost/api/')
    data = {
        'almanac.device.search': {'description': 'd', 'params': {}},
        'almanac.interface.search': {'description': 's', 'params': {}},
        'almanac.interface.edit': {'description': 'e', 'params': {}},
    }
    # Base stores interface data in `interface`; head uses `_interface_data`.
    if '_interface_data' in phab.__dict__:
        phab.__dict__['_interface_data'].update(data)
    else:
        phab.__dict__['interface'].update(data)

    res = phab.almanac.interface.search
    assert isinstance(res, phabricator.Resource)
    res2 = phab.almanac.interface.edit
    assert isinstance(res2, phabricator.Resource)
