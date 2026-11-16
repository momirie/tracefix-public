from proxy.http.parser import HttpParser
from proxy.http.parser import httpParserTypes


def test_connect_request_host_and_port():
    parser = HttpParser(httpParserTypes.REQUEST_PARSER)
    parser.parse(b'CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\n\r\n')
    assert parser.host == b'example.com'
    assert parser.port == 443
