from mqtt_exporter import main, settings


def test_shelly_3em_phases_are_distinguished(monkeypatch):
    monkeypatch.setattr(settings, "KEEP_FULL_TOPIC", True, raising=False)
    t0, p0 = main._parse_message("shellies/shelly-deviceid1234/emeter/0/power", b"12.5")
    t1, p1 = main._parse_message("shellies/shelly-deviceid1234/emeter/1/power", b"13.5")
    assert t0 != t1
    assert t0 == "shellies_shelly-deviceid1234_emeter_0"
    assert t1 == "shellies_shelly-deviceid1234_emeter_1"
    assert p0 == {"power": 12.5}
    assert p1 == {"power": 13.5}
