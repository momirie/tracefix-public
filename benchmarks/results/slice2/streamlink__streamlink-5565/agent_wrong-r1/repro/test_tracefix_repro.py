import pytest
from unittest.mock import patch

from streamlink import Streamlink
from streamlink.plugins.nos import NOS


HTML = """<html><head></head><body>
<script id="__NEXT_DATA__" type="application/json">{"props": {"pageProps": {"data": {"livestream": {"title": "NOS Live", "isLive": true, "stream": "https://example.com/live.m3u8"}}}}}</script>
</body></html>"""


def test_nos_next_data_livestream():
    session = Streamlink()
    sentinel = {"live": object()}
    url = "https://nos.nl/livestream/2489911"
    plugin = NOS(session, url)

    class Resp:
        text = HTML
        content = HTML.encode("utf-8")
        encoding = "utf-8"
        headers = {}

    with patch("streamlink.plugins.nos.HLSStream.parse_variant_playlist", return_value=sentinel) as hls, \
            patch.object(session.http, "get", side_effect=lambda u, *a, **kw: kw["schema"].validate(HTML) if kw.get("schema") else Resp()):
        streams = plugin._get_streams()

    assert streams == sentinel
    assert hls.call_args[0][1] == "https://example.com/live.m3u8"
