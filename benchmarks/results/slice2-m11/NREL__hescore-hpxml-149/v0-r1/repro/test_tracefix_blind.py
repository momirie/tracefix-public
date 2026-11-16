import glob
import os
from hescorehpxml import HPXMLtoHEScoreTranslator


def test_external_building_id_in_building_address(request):
    exdir = os.path.join(str(request.fspath.dirpath()), 'examples')
    paths = sorted(glob.glob(os.path.join(exdir, '*.xml')))
    assert paths
    found_in_address = False
    for path in paths:
        try:
            d = HPXMLtoHEScoreTranslator(path).hpxml_to_hescore()
        except Exception:
            continue
        assert 'external_building_id' not in d['building']['about']
        if 'external_building_id' in d['building_address']:
            found_in_address = True
    assert found_in_address
