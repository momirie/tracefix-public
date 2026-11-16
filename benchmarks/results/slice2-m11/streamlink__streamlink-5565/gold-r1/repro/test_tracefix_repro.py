import pytest
import requests_mock as rm

from streamlink import Streamlink
from streamlink.plugins.nos import NOS


HTML = """<!DOCTYPE html><html><head>
<script type="application/ld+json">{"@type":"VideoObject","encodingFormat":"application/vnd.apple.mpegurl","contentUrl":"https://example.com/live.m3u8","identifier":"2489911","name":"Some Title"}</script>
</head><body></body></html>"""

M3U8 = """#EXTM3U
#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=1000000,RESOLUTION=1280x720
https://example.com/720.m3u8
"""


def test_nos_ldjson_streams():
    session = Streamlink()
    url = "https://nos.nl/livestream/2489911"
    with rm.Mocker() as m:
        m.get(url, text=HTML)
        m.get("https://example.com/live.m3u8", text=M3U8)
        plugin = NOS(session, url)
        streams = plugin.streams()
    assert streams
    assert "720p" in streams
