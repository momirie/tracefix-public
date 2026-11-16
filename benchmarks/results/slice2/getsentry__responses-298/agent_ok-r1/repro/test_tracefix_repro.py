import re

import pytest
import requests
import responses
from requests.exceptions import ConnectionError

try:
    from mock import patch
except ImportError:
    from unittest.mock import patch


def test_add_passthru_regex():
    sentinel = requests.Response()
    sentinel.status_code = 204

    with patch("responses._real_send", return_value=sentinel) as real_send:
        with responses.RequestsMock() as rsps:
            rsps.add_passthru(re.compile(r"http(s?)://(\w+)(:*)(\d*)/api/v1/activities/"))
            resp = requests.get("http://localhost:8080/api/v1/activities/")
            assert resp is sentinel
            assert real_send.call_count == 1
            with pytest.raises(ConnectionError):
                requests.get("http://localhost:8080/other/")
