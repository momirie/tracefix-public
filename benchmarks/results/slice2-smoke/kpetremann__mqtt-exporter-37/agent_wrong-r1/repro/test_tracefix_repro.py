from mqtt_exporter.main import _parse_message


def test_shelly_3em_phases_are_distinguished():
    topics = [
        "shellies/shelly-deviceid1234/emeter/%d/power" % i for i in range(3)
    ]
    results = [_parse_message(t, b"123.45") for t in topics]
    parsed_topics = [r[0] for r in results]
    assert len(set(parsed_topics)) == 3
    for r in results:
        assert r[1] == {"power": 123.45}
