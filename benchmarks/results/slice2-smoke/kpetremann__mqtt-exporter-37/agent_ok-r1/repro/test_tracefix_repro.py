from mqtt_exporter.main import _parse_message


def test_shelly_3em_phases_are_distinct():
    topics = {}
    for phase in range(3):
        topic = f"shellies/shelly-deviceid1234/emeter/{phase}/power"
        parsed_topic, payload = _parse_message(topic, str(100 + phase))
        assert payload == {"power": 100 + phase}
        topics[phase] = parsed_topic
    assert len(set(topics.values())) == 3
