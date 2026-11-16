import proxy


def test_parse_blank_line_does_not_raise():
    parser = proxy.HttpParser(proxy.HttpParser.types.REQUEST_PARSER) if hasattr(proxy.HttpParser, 'types') else proxy.HttpParser(proxy.httpParserTypes.REQUEST_PARSER)
    # Malformed request line from client (just a line feed / CRLF) must not crash with IndexError
    parser.parse(b'\r\n')
