from __future__ import annotations

from typing import TypedDict

from mashumaro.jsonschema import build_json_schema


class TD(TypedDict):
    int: int
    float: float


def test_typeddict_future_annotations():
    schema = build_json_schema(TD)
    d = schema.to_dict()
    assert d["type"] == "object"
    assert d["properties"]["int"] == {"type": "integer"}
    assert d["properties"]["float"] == {"type": "number"}
    assert sorted(d["required"]) == ["float", "int"]
