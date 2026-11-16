import pytest

from mqtt_exporter import main, settings


def test_keep_full_topic_shelly_emeter(monkeypatch):
    monkeypatch.setattr(settings, "KEEP_FULL_TOPIC", True, raising=False)
    topic, payload = main._parse_message("shellies/shelly-deviceid1234/emeter/0/power", b"12.5")
    assert topic == "shellies_shelly-deviceid1234_emeter_0"
    assert payload == {"power": 12.5}


def test_keep_full_topic_distinguishes_phases(monkeypatch):
    monkeypatch.setattr(settings, "KEEP_FULL_TOPIC", True, raising=False)
    t0, _ = main._parse_message("shellies/dev/emeter/0/power", b"1")
    t1, _ = main._parse_message("shellies/dev/emeter/1/power", b"2")
    assert t0 != t1
