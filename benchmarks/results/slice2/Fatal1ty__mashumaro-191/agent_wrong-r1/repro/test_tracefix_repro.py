from __future__ import annotations

from typing import TypedDict

from mashumaro.jsonschema import build_json_schema
from mashumaro.jsonschema.models import JSONSchemaInstanceType


class TypedDictRequiredKeys(TypedDict):
    int: int
    float: float


def test_typeddict_with_future_annotations():
    schema = build_json_schema(TypedDictRequiredKeys)
    assert schema.type == JSONSchemaInstanceType.OBJECT
    assert schema.properties["int"].type == JSONSchemaInstanceType.INTEGER
    assert schema.properties["float"].type == JSONSchemaInstanceType.NUMBER
    assert sorted(schema.required) == ["float", "int"]
