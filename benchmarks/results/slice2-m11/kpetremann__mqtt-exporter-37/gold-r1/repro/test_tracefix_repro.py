from mqtt_exporter import main, settings


def test_shelly_3em_phases_distinguishable(monkeypatch):
    monkeypatch.setattr(settings, "KEEP_FULL_TOPIC", True, raising=False)
    topics = [
        "shellies/shelly-deviceid1234/emeter/0/power",
        "shellies/shelly-deviceid1234/emeter/1/power",
        "shellies/shelly-deviceid1234/emeter/2/power",
    ]
    results = [main._parse_message(t, b"12.5") for t in topics]
    names = {r[0] for r in results}
    assert len(names) == 3
    for name, payload in results:
        assert payload == {"power": 12.5}
    assert results[1][0] == "shellies_shelly-deviceid1234_emeter_1"
