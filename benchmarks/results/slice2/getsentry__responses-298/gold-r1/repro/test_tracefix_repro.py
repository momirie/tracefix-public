import re

import requests
from responses import RequestsMock
from unittest.mock import patch


def test_add_passthru_regex():
    sentinel = requests.Response()
    sentinel.status_code = 200
    sentinel._content = b"passed"
    with patch("responses._real_send") as real_send:
        real_send.return_value = sentinel
        mock = RequestsMock(assert_all_requests_are_fired=False)
        mock.add_passthru(re.compile(r"http(s?)://(\w+)(:*)(\d*)/api/v1/activities/"))
        mock.start()
        try:
            result = requests.get("http://localhost:8080/api/v1/activities/")
            assert real_send.called
            assert result.content == b"passed"
        finally:
            mock.stop()
            mock.reset()
