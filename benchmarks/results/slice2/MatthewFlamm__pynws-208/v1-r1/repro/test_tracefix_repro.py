import json
from unittest.mock import MagicMock

from pynws import SimpleNWS


class _Resp:
    status = 200
    headers = {"Content-Type": "application/json"}

    def __init__(self, data):
        self._data = data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def raise_for_status(self):
        pass

    async def json(self, *a, **k):
        return self._data

    async def text(self, *a, **k):
        return json.dumps(self._data)


async def test_forecast_icon_is_absolute_url():
    period = {
        "number": 1,
        "name": "Tonight",
        "startTime": "2024-01-01T18:00:00-05:00",
        "endTime": "2024-01-02T06:00:00-05:00",
        "isDaytime": False,
        "temperature": 30,
        "temperatureUnit": "F",
        "icon": "/icons/land/night/sct?size=small",
        "shortForecast": "Clear",
        "detailedForecast": "Clear",
    }
    payload = {"properties": {"periods": [period]}, "periods": [period]}
    session = MagicMock()
    session.get = MagicMock(side_effect=lambda *a, **k: _Resp(payload))
    session.request = MagicMock(side_effect=lambda *a, **k: _Resp(payload))
    nws = SimpleNWS("0", "0", "test@example.com", session)
    nws.station = "STN"
    nws.wfo = "ABC"
    nws.x = 1
    nws.y = 2
    await nws.update_forecast()
    result = nws.forecast
    assert result
    assert result[0]["icon"].startswith("https://api.weather.gov/icons/")
