from hescorehpxml.hpxml2 import HPXML2toHEScoreTranslator


def _find_mapping():
    for name in dir(HPXML2toHEScoreTranslator):
        try:
            val = getattr(HPXML2toHEScoreTranslator, name)
        except Exception:
            continue
        if isinstance(val, dict) and 'garage' in val and 'unconditioned attic' in val and 'outside' in val:
            return val
    return None


def test_garage_duct_location_is_unvented_crawl():
    mapping = _find_mapping()
    assert mapping is not None
    assert mapping['garage'] == 'unvented_crawl'
