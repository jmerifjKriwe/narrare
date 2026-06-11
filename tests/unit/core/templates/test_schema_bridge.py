"""Tests for templates/schema_bridge.py — Template-to-schema bridge.

Covers:
1. get_form_fields returns fields for known entity types
2. get_form_fields returns empty for unknown entity types
3. validate_metadata validates against known schemas
4. validate_metadata falls back to KBEntryMetadata for unknown types
"""

from __future__ import annotations

from typing import Any, cast

from narrare_core.kb.schemas.base import KBEntryMetadata
from narrare_core.templates.schema_bridge import get_form_fields, validate_metadata


class TestGetFormFields:
    """get_form_fields loads template fields for entity types."""

    def test_character_returns_fields(self) -> None:
        fields = get_form_fields("character")
        # Character has a default template — should return fields
        assert isinstance(fields, list)

    def test_location_returns_fields(self) -> None:
        fields = get_form_fields("location")
        assert isinstance(fields, list)

    def test_unknown_type_returns_empty(self) -> None:
        fields = get_form_fields("nonexistent_entity_type_xyz")
        assert fields == []


class TestValidateMetadata:
    """validate_metadata validates metadata against entity type schema."""

    def test_validate_character_metadata(self) -> None:
        result = cast("Any", validate_metadata("character", {"age": 30, "role": "protagonist"}))
        assert result.age == 30
        assert result.role == "protagonist"

    def test_validate_location_metadata(self) -> None:
        result = cast("Any", validate_metadata("location", {"climate": "Tropical"}))
        assert result.climate == "Tropical"

    def test_validate_unknown_type_falls_back(self) -> None:
        """Unknown entity types fall back to KBEntryMetadata (extra='allow')."""
        result = cast(
            "Any",
            validate_metadata(
                "unknown_type_xyz",
                {"custom_field": "custom_value"},
            ),
        )
        assert isinstance(result, KBEntryMetadata)
        assert cast("Any", result).custom_field == "custom_value"

    def test_validate_empty_metadata(self) -> None:
        result = validate_metadata("character", {})
        assert isinstance(result, KBEntryMetadata)

    def test_validate_preserves_extra_fields(self) -> None:
        result = cast(
            "Any",
            validate_metadata(
                "character",
                {"age": 25, "future_field": "some_value"},
            ),
        )
        assert result.future_field == "some_value"
