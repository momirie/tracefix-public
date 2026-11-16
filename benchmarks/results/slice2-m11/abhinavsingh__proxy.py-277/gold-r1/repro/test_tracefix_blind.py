from proxy.http.parser import HttpParser
from proxy.http.parser import httpParserTypes


def test_connect_request_host_and_port():
    p = HttpParser(httpParserTypes.REQUEST_PARSER)
    p.parse(b'CONNECT uni.corn:443 HTTP/1.1\r\nHost: uni.corn:443\r\n\r\n')
    assert p.host == b'uni.corn'
    assert p.port == 443
