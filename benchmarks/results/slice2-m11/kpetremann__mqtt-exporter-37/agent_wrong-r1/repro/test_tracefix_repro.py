from mqtt_exporter.main import _parse_message


def test_shelly_3em_phases_are_distinguished():
    t0, p0 = _parse_message("shellies/shelly-deviceid1234/emeter/0/power", b"123.45")
    t1, p1 = _parse_message("shellies/shelly-deviceid1234/emeter/1/power", b"200.5")
    assert t0 != t1
    assert p0 == {"power": 123.45}
    assert p1 == {"power": 200.5}
