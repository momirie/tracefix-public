import re

import requests
import responses
from responses import RequestsMock
from unittest.mock import patch


def test_add_passthru_regex():
    pattern = re.compile(r"https?://[^/]+/api/v1/activities/")
    with RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add_passthru(pattern)
        with patch("responses._real_send") as real_send:
            real_send.return_value = "passed"
            result = requests.get("http://example.com:8080/api/v1/activities/")
        assert real_send.called
        assert result == "passed"
