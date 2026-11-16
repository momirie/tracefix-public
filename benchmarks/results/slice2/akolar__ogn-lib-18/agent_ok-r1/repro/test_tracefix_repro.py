from ogn_lib import parser


def test_capturs_registered_with_ogcapt():
    assert 'OGCAPT' in parser.Capturs.__destto__
    assert 'OGLT24' not in parser.Capturs.__destto__
    assert 'OGLT24' in parser.LiveTrack24.__destto__
