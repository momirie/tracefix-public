from hescorehpxml.hpxml2 import HPXML2toHEScoreTranslator


def test_garage_duct_location_maps_to_unvented_crawl():
    mapping = None
    for name in dir(HPXML2toHEScoreTranslator):
        val = getattr(HPXML2toHEScoreTranslator, name, None)
        if isinstance(val, dict) and 'garage' in val and 'unconditioned attic' in val and 'outside' in val:
            mapping = val
            break
    assert mapping is not None, 'duct location mapping not found'
    assert mapping['garage'] == 'unvented_crawl'
