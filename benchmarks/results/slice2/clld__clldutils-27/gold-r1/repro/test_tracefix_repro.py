from clldutils.badge import badge


def test_badge_custom_label():
    res = badge('sub', 'stat', 'green', label='My Label')
    assert res.startswith('![My Label](')
    assert res.endswith('"My Label")')
    assert 'img.shields.io/badge/sub-stat-green.svg' in res
