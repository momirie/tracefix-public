from proxy.http.parser import HttpParser, httpParserTypes


def test_connect_request_host_and_port_parsed():
    parser = HttpParser(httpParserTypes.REQUEST_PARSER)
    parser.parse(b'CONNECT uni.corn:443 HTTP/1.1\r\nHost: uni.corn:443\r\n\r\n')
    assert parser.host == b'uni.corn'
    assert parser.port == 443


def test_connect_request_custom_port():
    parser = HttpParser(httpParserTypes.REQUEST_PARSER)
    parser.parse(b'CONNECT example.com:8443 HTTP/1.1\r\nHost: example.com:8443\r\n\r\n')
    assert parser.host == b'example.com'
    assert parser.port == 8443
