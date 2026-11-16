import os
import re

import hescorehpxml
from hescorehpxml import HPXMLtoHEScoreTranslator


def test_external_building_id_in_building_address(tmp_path):
    root = os.path.dirname(os.path.abspath(list(hescorehpxml.__path__)[0]))
    path = os.path.join(root, 'examples', 'house1.xml')
    with open(path, encoding='utf-8') as f:
        s = f.read()
    assert 'HESExternalID' not in s
    m = re.search(r'<((?:\w+:)?)BuildingID(\s+id="[^"]*")\s*/>', s)
    assert m
    pre = m.group(1)
    new = '<%sBuildingID%s><%sSendingSystemIdentifierValue>EXT123</%sSendingSystemIdentifierValue></%sBuildingID>' % (
        pre, m.group(2), pre, pre, pre)
    s = s[:m.start()] + new + s[m.end():]
    f2 = tmp_path / 'h.xml'
    f2.write_text(s, encoding='utf-8')
    t = HPXMLtoHEScoreTranslator(str(f2))
    d = t.hpxml_to_hescore()
    assert d['building_address'].get('external_building_id') == 'EXT123'
    assert 'external_building_id' not in d['building']['about']
