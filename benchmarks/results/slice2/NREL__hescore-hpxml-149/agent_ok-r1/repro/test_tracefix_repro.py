import os
from lxml import etree
import hescorehpxml
from hescorehpxml import HPXMLtoHEScoreTranslator

NS = 'http://hpxmlonline.com/2014/6'


def test_external_building_id_in_building_address(tmp_path):
    pkg_dir = os.path.dirname(os.path.abspath(list(hescorehpxml.__path__)[0] + os.sep + 'x'))
    root = os.path.dirname(pkg_dir)
    src = os.path.join(root, 'examples', 'house1.xml')
    tree = etree.parse(src)
    bid = tree.getroot().find('{%s}Building/{%s}BuildingID' % (NS, NS))
    for ch in list(bid):
        bid.remove(ch)
    t = etree.SubElement(bid, '{%s}SendingSystemIdentifierType' % NS)
    t.text = 'some system'
    v = etree.SubElement(bid, '{%s}SendingSystemIdentifierValue' % NS)
    v.text = 'ext-123'
    path = str(tmp_path / 'h.xml')
    tree.write(path)
    d = HPXMLtoHEScoreTranslator(path).hpxml_to_hescore()
    assert d['building_address'].get('external_building_id') == 'ext-123'
    assert 'external_building_id' not in d['building']['about']
