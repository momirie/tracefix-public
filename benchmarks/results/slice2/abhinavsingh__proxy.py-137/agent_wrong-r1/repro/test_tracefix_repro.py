import pytest
import proxy


def test_malformed_request_line_does_not_raise_index_error():
    parser = proxy.HttpParser(proxy.httpParserTypes.REQUEST_PARSER)
    try:
        parser.parse(b'\r\n')
    except IndexError:
        pytest.fail('IndexError raised on malformed request line')
    except proxy.ProtocolException:
        pass


def test_incomplete_request_line_does_not_raise_index_error():
    parser = proxy.HttpParser(proxy.httpParserTypes.REQUEST_PARSER)
    try:
        parser.parse(b'GET\r\n')
    except IndexError:
        pytest.fail('IndexError raised on malformed request line')
    except proxy.ProtocolException:
        pass
