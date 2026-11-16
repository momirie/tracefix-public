from unittest.mock import patch

import requests_mock

from streamlink.session import Streamlink
from streamlink.plugins.nos import NOS


def test_nos_livestream_page():
    html = (
        '<html><body><script type="application/json" data-ssr-name="pages/Livestream/Livestream">'
        '{"currentLivestream": {"is_live": true, "title": "Title", "stream": "https://example.com/live.m3u8"}}'
        '</script></body></html>'
    )
    session = Streamlink()
    url = "https://nos.nl/livestream/2489911"
    with requests_mock.Mocker() as m, patch("streamlink.plugins.nos.HLSStream.parse_variant_playlist") as p:
        m.get(url, text=html)
        p.return_value = {"720p": object()}
        plugin = NOS(session, url)
        streams = plugin._get_streams()
    assert streams and "720p" in streams
