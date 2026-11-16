from lxml import etree
from hescorehpxml import HPXMLtoHEScoreTranslator


def test_external_building_id_in_building_address():
    t = HPXMLtoHEScoreTranslator('examples/hescore_min.xml')
    ns = t.ns
    b = t.hpxmldoc.xpath('//h:Building', namespaces=ns)[0]
    bid = b.xpath('h:BuildingID', namespaces=ns)[0]
    for e in bid.xpath('h:SendingSystemIdentifierValue', namespaces=ns):
        bid.remove(e)
    el = etree.SubElement(bid, '{%s}SendingSystemIdentifierValue' % ns['h'])
    el.text = 'EXT_ID_123'
    result = t.hpxml_to_hescore()
    assert result['building_address'].get('external_building_id') == 'EXT_ID_123'
    assert 'external_building_id' not in result['building']['about']
