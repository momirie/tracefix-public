from clldutils.badge import badge


def test_badge_accepts_custom_base_url_and_label():
    res = badge('sub', 'stat', 'green', markdown=False, base_url='https://example.org')
    assert res == 'https://example.org/badge/sub-stat-green.svg'
    md = badge('sub', 'stat', 'green', label='custom')
    assert md.startswith('![custom](https://img.shields.io/badge/sub-stat-green.svg "custom")')
