import pytest
from unittest.mock import patch

from streamlink import Streamlink
from streamlink.plugins.nos import NOS


HTML = '''<html><body>
<script type="application/json" data-ssr-name="pages/Livestream/Livestream">
{"livestream": {"is_live": true, "title": "NOS Live", "stream": "https://example.com/live.m3u8"}}
</script></body></html>'''


def test_nos_livestream_streams(requests_mock):
    requests_mock.get("https://nos.nl/livestream/2489911", text=HTML)
    session = Streamlink()
    plugin = NOS(session, "https://nos.nl/livestream/2489911")
    with patch("streamlink.plugins.nos.HLSStream.parse_variant_playlist", return_value={"720p": object()}) as m:
        result = plugin._get_streams()
    assert result, "no streams found"
    assert m.call_args[0][1] == "https://example.com/live.m3u8"
