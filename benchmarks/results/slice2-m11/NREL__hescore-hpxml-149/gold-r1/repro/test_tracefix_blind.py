import os
from lxml import etree
import hescorehpxml
from hescorehpxml import HPXMLtoHEScoreTranslator


def test_external_building_id_in_building_address(tmp_path):
    repo = os.path.dirname(list(hescorehpxml.__path__)[0])
    src = os.path.join(repo, 'examples', 'house1.xml')
    tree = etree.parse(src)
    root = tree.getroot()
    ns = root.nsmap[None]
    bid = root.find('{%s}Building' % ns).find('{%s}BuildingID' % ns)
    for tag in ('SendingSystemIdentifierType', 'SendingSystemIdentifierValue'):
        for el in bid.findall('{%s}%s' % (ns, tag)):
            bid.remove(el)
    t = etree.SubElement(bid, '{%s}SendingSystemIdentifierType' % ns)
    t.text = 'mysystem'
    v = etree.SubElement(bid, '{%s}SendingSystemIdentifierValue' % ns)
    v.text = 'ext123'
    out = tmp_path / 'house.xml'
    tree.write(str(out))
    with open(str(out), 'rb') as f:
        d = HPXMLtoHEScoreTranslator(f).hpxml_to_hescore()
    assert d['building_address'].get('external_building_id') == 'ext123'
    assert 'external_building_id' not in d['building']['about']
