import re
import requests
import responses
from responses import RequestsMock

try:
    from mock import patch
except ImportError:
    from unittest.mock import patch


def test_add_passthru_regex():
    fake = requests.Response()
    fake.status_code = 200
    fake._content = b"upstream"
    with patch.object(responses, "_real_send", return_value=fake) as real:
        with RequestsMock() as rsps:
            rsps.add_passthru(
                re.compile(r"http(s?):\/\/(\w+)(:*)(\d*)\/api\/v1\/activities\/")
            )
            resp = requests.get("http://host:8080/api/v1/activities/")
            assert resp.text == "upstream"
        assert real.call_count == 1
