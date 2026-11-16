from ogn_lib import parser


def test_capturs_registered_with_ogcapt():
    dests = list(parser.Capturs.__destto__)
    assert 'OGCAPT' in dests
    assert 'OGLT24' not in dests


def test_capturs_not_shared_with_livetrack24():
    assert 'OGLT24' not in parser.Capturs.__destto__
    assert 'OGLT24' in parser.LiveTrack24.__destto__
