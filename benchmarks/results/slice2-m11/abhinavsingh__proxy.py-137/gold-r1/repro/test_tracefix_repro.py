import proxy


def test_parser_handles_blank_line_from_client():
    parser = proxy.HttpParser(proxy.httpParserTypes.REQUEST_PARSER)
    try:
        parser.parse(b'\r\n')
    except IndexError as e:
        raise AssertionError('parser crashed with IndexError on blank line: %r' % e)
