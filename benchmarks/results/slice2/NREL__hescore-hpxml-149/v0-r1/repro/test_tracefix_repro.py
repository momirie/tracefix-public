import pathlib
from lxml import etree
import hescorehpxml
from hescorehpxml import HPXMLtoHEScoreTranslator


def test_external_building_id_not_in_building_about(tmp_path):
    pkg = pathlib.Path(hescorehpxml.__path__[0]).resolve()
    src = pkg.parent / 'examples' / 'house1.xml'
    tree = etree.parse(str(src))
    root = tree.getroot()
    ns = root.nsmap[None]
    bid = root.find('{%s}Building/{%s}BuildingID' % (ns, ns))
    for child in list(bid):
        if 'SendingSystemIdentifier' in child.tag:
            bid.remove(child)
    t = etree.SubElement(bid, '{%s}SendingSystemIdentifierType' % ns)
    t.text = 'some system'
    v = etree.SubElement(bid, '{%s}SendingSystemIdentifierValue' % ns)
    v.text = 'ext-id-12345'
    path = str(tmp_path / 'house_ext.xml')
    tree.write(path)
    tr = HPXMLtoHEScoreTranslator(path)
    result = tr.hpxml_to_hescore()
    assert 'external_building_id' not in result['building']['about']
