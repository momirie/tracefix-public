from clldutils.badge import badge


def test_badge_escapes_dash():
    url = badge('my-subject', 'ok-status', 'green', markdown=False)
    assert url == 'https://img.shields.io/badge/my--subject-ok--status-green.svg'


def test_badge_query():
    url = badge('a', 'b', 'red', fmt='png', markdown=False, style='flat')
    assert url == 'https://img.shields.io/badge/a-b-red.png?style=flat'
