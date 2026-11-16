import pytest

from mqtt_exporter import main, settings


def test_shelly_3em_phases_kept_separate(monkeypatch):
    monkeypatch.setattr(settings, "KEEP_FULL_TOPIC", True, raising=False)
    topics = []
    for phase in (0, 1, 2):
        topic, payload = main._parse_message(
            f"shellies/shelly-deviceid1234/emeter/{phase}/power", b"12.5"
        )
        assert payload == {"power": 12.5}
        topics.append(topic)
    assert topics == [
        "shellies_shelly-deviceid1234_emeter_0",
        "shellies_shelly-deviceid1234_emeter_1",
        "shellies_shelly-deviceid1234_emeter_2",
    ]
