import proxy


def test_blank_line_request_does_not_raise_index_error():
    parser = proxy.HttpParser(proxy.httpParserTypes.REQUEST_PARSER)
    try:
        parser.parse(b'\r\n')
    except IndexError as e:
        raise AssertionError('parser crashed with IndexError on malformed request line: %r' % (e,))
