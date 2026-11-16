from mqtt_exporter.main import _parse_message


def test_shelly_3em_phases_are_distinct():
    topics = {}
    for phase in range(3):
        topic, payload = _parse_message(
            f"shellies/shelly-deviceid1234/emeter/{phase}/power", str(100 + phase)
        )
        topics[phase] = (topic, payload)
    parsed_topics = {t for t, _ in topics.values()}
    assert len(parsed_topics) == 3
    for phase in range(3):
        assert topics[phase][1] == {"power": 100 + phase}
