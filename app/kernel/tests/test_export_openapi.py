"""The OpenAPI writer's number canonicalisation.

release-please rewrites `web/lib/api/openapi.json` through Go's JSON encoder
when it bumps the version, and that encoder prints an integral float as an
integer (`20.0` -> `20`). `just check-generated` compares bytes, so the file
the writer produces must already be what release-please would write — issue
#636, where every release PR went red on exactly these values.
"""

from __future__ import annotations

from scripts.export_openapi import JSONValue, canonical_numbers


def test_integral_floats_become_integers() -> None:
    """Pydantic writes `Field(le=20)` as 20.0; Go would write 20."""
    document: JSONValue = {"maximum": 20.0, "exclusiveMinimum": 0.0}
    assert canonical_numbers(document) == {"maximum": 20, "exclusiveMinimum": 0}


def test_fractional_numbers_and_other_types_stay() -> None:
    """Only the textual form of a whole number changes — nothing else."""
    document: JSONValue = {"default": 0.5, "name": "x", "count": 3, "flag": True, "empty": None}
    assert canonical_numbers(document) == document


def test_nested_lists_and_objects_are_walked() -> None:
    """The schema nests through `anyOf`, `properties` and lists."""
    document: JSONValue = {
        "anyOf": [{"minimum": 1.0}, {"minimum": 1.5}],
        "properties": {"limit": {"le": 20.0}},
    }
    assert canonical_numbers(document) == {
        "anyOf": [{"minimum": 1}, {"minimum": 1.5}],
        "properties": {"limit": {"le": 20}},
    }
