from mqtt_exporter import main


def test_shelly_emeter_topics_keep_channel_index():
    t0, p0 = main._parse_message("shellies/shelly-deviceid1234/emeter/0/power", "10.5")
    t1, p1 = main._parse_message("shellies/shelly-deviceid1234/emeter/1/power", "20.5")
    assert p0 == {"power": 10.5}
    assert p1 == {"power": 20.5}
    # the two phases must map to distinct sensor names
    assert t0 != t1
