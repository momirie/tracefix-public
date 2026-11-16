from __future__ import annotations

from typing import TypedDict

from mashumaro.jsonschema import build_json_schema


class TD(TypedDict):
    int: int
    float: float


def test_typeddict_schema_with_future_annotations():
    schema = build_json_schema(TD)
    assert schema.properties["int"].type.value == "integer"
    assert schema.properties["float"].type.value == "number"
