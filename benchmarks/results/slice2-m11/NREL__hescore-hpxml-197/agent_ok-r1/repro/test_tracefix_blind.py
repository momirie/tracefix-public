from importlib import resources
from lxml import etree
from hescorehpxml import HPXMLtoHEScoreTranslator


def test_garage_duct_location_maps_to_unvented_crawl(tmp_path):
    base = resources.files('tests') / 'examples'
    tree = None
    for name in ['house1.xml', 'house2.xml', 'house3.xml', 'hescore_min.xml']:
        t = etree.parse(str(base / name))
        els = [e for e in t.iter() if isinstance(e.tag, str) and etree.QName(e).localname == 'DuctLocation']
        if els:
            for e in els:
                e.text = 'garage'
            tree = t
            break
    assert tree is not None
    out = tmp_path / 'garage.xml'
    tree.write(str(out))
    d = HPXMLtoHEScoreTranslator(str(out)).hpxml_to_hescore_dict()
    locs = []
    for hvac in d['building']['systems']['hvac']:
        for duct in hvac.get('hvac_distribution', {}).get('duct', []):
            locs.append(duct['location'])
    assert locs
    assert all(loc == 'unvented_crawl' for loc in locs)
