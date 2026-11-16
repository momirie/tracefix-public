import pytest

from streamlink import Streamlink


def test_nos_livestream_playable(requests_mock):
    m3u8 = '#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=1000,RESOLUTION=1280x720\nhttp://example.com/v.m3u8\n'
    html = ('<html><head><title>NOS</title></head><body>'
            '<script type="application/json" id="__NEXT_DATA__">'
            '{"props":{"pageProps":{"data":{"id":"2489911","title":"Livestream",'
            '"type":"livestream",'
            '"stream":"http://example.com/master.m3u8",'
            '"video":{"aspect":"16:9","assets":[{"type":"hls","url":"http://example.com/master.m3u8"}]},'
            '"assets":[{"type":"hls","url":"http://example.com/master.m3u8"}]'
            '}}}}</script></body></html>')
    requests_mock.get('https://nos.nl/livestream/2489911', text=html)
    requests_mock.get('http://example.com/master.m3u8', text=m3u8)
    session = Streamlink()
    streams = session.streams('https://nos.nl/livestream/2489911')
    assert streams
