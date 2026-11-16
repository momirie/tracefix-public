from proxy.http.parser import HttpParser, httpParserTypes


def test_connect_request_host_port_parsed():
    parser = HttpParser(httpParserTypes.REQUEST_PARSER)
    parser.parse(b'CONNECT uni.corn:443 HTTP/1.1\r\nHost: uni.corn:443\r\n\r\n')
    assert parser.host == b'uni.corn'
    assert parser.port == 443
