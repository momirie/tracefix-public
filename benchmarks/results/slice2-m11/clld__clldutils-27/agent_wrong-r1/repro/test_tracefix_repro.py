from clldutils.badge import badge


def test_badge_keyword_label_message_color():
    url = badge(label='build', message='passing', color='green', markdown=False)
    assert url == 'https://img.shields.io/badge/build-passing-green.svg'


def test_badge_message_color_only():
    url = badge(message='passing', color='green', markdown=False)
    assert url == 'https://img.shields.io/badge/passing-green.svg'
