import re

import requests
import responses
from requests.exceptions import ConnectionError

try:
    from mock import patch
except ImportError:
    from unittest.mock import patch


def test_passthru_regex():
    @responses.activate
    def run():
        responses.add_passthru(re.compile(r"http(s?)://(\w+)(:*)(\d*)/api/v1/activities/"))
        with patch("responses._real_send", return_value="passed") as real_send:
            try:
                result = requests.get("http://myhost:8080/api/v1/activities/")
            except ConnectionError:
                result = None
                raised = True
            else:
                raised = False
            assert not raised
            assert real_send.call_count == 1

    run()
