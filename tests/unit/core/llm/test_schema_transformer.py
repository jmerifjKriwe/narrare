"""Tests for llm/_schema_transformer.py — universal ``$defs`` inlining for OpenAI-compat providers.

Covers:
- The extraction-shaped ``results.items.$ref`` schema is inlined (the structural defect fix).
- OpenAI strict-mode transforms are retained (capability preservation, not a blanket swap).
- Recursive references fall back to a ``$defs``/``$ref`` structure losslessly.
- The shared profile helper replaces only the ``json_schema_transformer`` key.
- Control: the plain OpenAI transformer does NOT inline (proves the subclass is the fix).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from pydantic_ai.profiles import ModelProfile
from pydantic_ai.profiles.openai import OpenAIJsonSchemaTransformer

from narrare_core.llm._schema_transformer import (
    NarrareOpenAICompatJsonSchemaTransformer,
    narrare_openai_compat_profile,
)

if TYPE_CHECKING:
    from pydantic_ai._json_schema import JsonSchema
    from pydantic_ai.profiles.openai import OpenAIModelProfile

_EXTRACTION_ITEM_DEF: Final[JsonSchema] = {
    "title": "ExtractionItem",
    "type": "object",
    "properties": {
        "name": {"title": "Name", "type": "string"},
        "confidence": {"title": "Confidence", "type": "number"},
    },
    "required": ["name", "confidence"],
    "additionalProperties": False,
}

#: The ``ExtractionOutput`` shape that hit the defect: ``results.items`` referenced
#: ``#/$defs/ExtractionItem``, which Z.AI did not resolve — the model saw an
#: unnamed object schema and returned empty items.
_EXTRACTION_SHAPED_SCHEMA: Final[JsonSchema] = {
    "title": "ExtractionOutput",
    "type": "object",
    "properties": {
        "results": {
            "title": "Results",
            "type": "array",
            "items": {"$ref": "#/$defs/ExtractionItem"},
        }
    },
    "required": ["results"],
    "additionalProperties": False,
    "$defs": {"ExtractionItem": _EXTRACTION_ITEM_DEF},
}


def _collect_refs(node: object) -> list[str]:
    """Collect every ``$ref`` string in a JSON-schema-like structure."""
    if isinstance(node, dict):
        values: list[object] = list(node.values())
        ref = node.get("$ref")
        own = [ref] if isinstance(ref, str) else []
        return own + [r for value in values for r in _collect_refs(value)]
    if isinstance(node, list):
        return [r for value in node for r in _collect_refs(value)]
    return []


def _assert_refs_resolvable(schema: dict[str, object]) -> None:
    """Every ``$ref`` must resolve — ``#`` (root) or ``#/$defs/<existing key>``."""
    defs = schema.get("$defs") or {}
    assert isinstance(defs, dict)
    for ref in _collect_refs(schema):
        if ref == "#":
            continue
        assert ref.startswith("#/$defs/")
        assert ref[len("#/$defs/") :] in defs, f"dangling $ref: {ref}"


class TestInlining:
    """``NarrareOpenAICompatJsonSchemaTransformer`` inlines ``$defs``/``$ref``."""

    def test_extraction_shaped_schema_inlines_refs(self) -> None:
        result = NarrareOpenAICompatJsonSchemaTransformer(dict(_EXTRACTION_SHAPED_SCHEMA)).walk()

        assert "$defs" not in result
        assert _collect_refs(result) == []
        items = result["properties"]["results"]["items"]
        assert items["properties"]["name"] == {"type": "string"}
        assert items["properties"]["confidence"] == {"type": "number"}
        assert items["required"] == ["name", "confidence"]

    def test_transitive_defs_inlined(self) -> None:
        schema: JsonSchema = {
            "type": "object",
            "properties": {"a": {"$ref": "#/$defs/A"}},
            "required": ["a"],
            "$defs": {
                "A": {
                    "type": "object",
                    "properties": {"b": {"$ref": "#/$defs/B"}},
                    "required": ["b"],
                },
                "B": {
                    "type": "object",
                    "properties": {"c": {"type": "string"}},
                    "required": ["c"],
                },
            },
        }
        result = NarrareOpenAICompatJsonSchemaTransformer(schema).walk()

        assert "$defs" not in result
        assert _collect_refs(result) == []
        c = result["properties"]["a"]["properties"]["b"]["properties"]["c"]
        assert c == {"type": "string"}


class TestStrictModeRetained:
    """OpenAI strict-mode transforms survive the inlining flip."""

    def test_titles_removed_and_objects_strictened(self) -> None:
        transformer = NarrareOpenAICompatJsonSchemaTransformer(dict(_EXTRACTION_SHAPED_SCHEMA))
        result = transformer.walk()

        assert "title" not in result
        assert result["additionalProperties"] is False
        assert result["properties"]["results"]["items"]["additionalProperties"] is False
        assert "title" not in result["properties"]["results"]

    def test_strict_compatibility_flag_retained(self) -> None:
        transformer = NarrareOpenAICompatJsonSchemaTransformer(dict(_EXTRACTION_SHAPED_SCHEMA))
        transformer.walk()
        assert transformer.is_strict_compatible is True

    def test_plain_openai_transformer_keeps_defs_control(self) -> None:
        """Control: the base OpenAI transformer does NOT inline — the subclass is the fix."""
        result = OpenAIJsonSchemaTransformer(dict(_EXTRACTION_SHAPED_SCHEMA)).walk()

        assert result["$defs"] == {
            "ExtractionItem": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "confidence": {"type": "number"}},
                "required": ["name", "confidence"],
                "additionalProperties": False,
            }
        }


class TestRecursiveFallback:
    """Recursive references cannot be inlined — they fall back to ``$defs``/``$ref``."""

    def test_property_recursive_ref_falls_back_to_defs(self) -> None:
        node_def: JsonSchema = {
            "title": "Node",
            "type": "object",
            "properties": {
                "value": {"title": "Value", "type": "string"},
                "child": {"$ref": "#/$defs/Node"},
            },
            "required": ["value"],
            "additionalProperties": False,
        }
        schema: JsonSchema = {
            "title": "Tree",
            "type": "object",
            "properties": {
                "root": {
                    **node_def,
                    "properties": {**node_def["properties"], "child": {"$ref": "#/$defs/Node"}},
                },
            },
            "required": ["root"],
            "$defs": {"Node": node_def},
        }
        result = NarrareOpenAICompatJsonSchemaTransformer(schema).walk()

        # A recursive ref cannot be inlined (no finite expansion): the walk keeps
        # a $defs/$ref structure instead — with no dangling references.
        assert "$defs" in result
        assert "Node" in result["$defs"]
        refs = _collect_refs(result)
        assert refs, "recursive schema must retain at least one $ref"
        _assert_refs_resolvable(result)

    def test_root_recursive_model_keeps_resolvable_refs(self) -> None:
        node_body: JsonSchema = {
            "type": "object",
            "properties": {
                "value": {"type": "string"},
                "next": {"$ref": "#/$defs/Node"},
            },
            "required": ["value"],
        }
        schema: JsonSchema = {
            "$defs": {"Node": node_body},
            "$ref": "#/$defs/Node",
        }
        result = NarrareOpenAICompatJsonSchemaTransformer(schema).walk()

        assert set(result["$defs"]) == {"Node"}
        assert _collect_refs(result), "recursive schema must retain at least one $ref"
        _assert_refs_resolvable(result)


class TestProfileHelper:
    """``narrare_openai_compat_profile`` is the shared injection point."""

    def test_replaces_only_transformer_key(self) -> None:
        resolved: OpenAIModelProfile = {
            "supports_thinking": True,
            "openai_chat_supports_max_completion_tokens": False,
            "json_schema_transformer": None,
        }
        profile = narrare_openai_compat_profile(resolved)

        assert profile.get("json_schema_transformer") is NarrareOpenAICompatJsonSchemaTransformer
        assert profile.get("supports_thinking") is True
        assert profile.get("openai_chat_supports_max_completion_tokens") is False

    def test_accepts_default_resolved_profile(self) -> None:
        """The callable ``profile=`` form receives DEFAULT+provider-resolved profiles."""
        profile = narrare_openai_compat_profile(ModelProfile())
        assert profile.get("json_schema_transformer") is NarrareOpenAICompatJsonSchemaTransformer
