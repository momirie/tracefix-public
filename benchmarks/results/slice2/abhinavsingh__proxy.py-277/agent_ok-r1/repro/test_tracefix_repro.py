from proxy.http.parser import HttpParser
from proxy.http.parser import httpParserTypes


def test_connect_request_host_and_port_parsed():
    parser = HttpParser(httpParserTypes.REQUEST_PARSER)
    parser.parse(b'CONNECT uni.corn:443 HTTP/1.1\r\nHost: uni.corn:443\r\n\r\n')
    assert parser.host == b'uni.corn'
    assert parser.port == 443


def test_connect_request_numeric_hostname():
    parser = HttpParser(httpParserTypes.REQUEST_PARSER)
    parser.parse(b'CONNECT localhost:8080 HTTP/1.1\r\nHost: localhost:8080\r\n\r\n')
    assert parser.host == b'localhost'
    assert parser.port == 8080
