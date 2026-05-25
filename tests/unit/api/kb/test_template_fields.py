"""Unit tests for template_fields module.

Tests get_template_fields for various entity types, field_key naming,
and fallback behavior for unknown entity types.
"""

from __future__ import annotations

from narrare.kb.session_models import KBCreationField
from narrare.kb.template_fields import get_template_fields


class TestGetTemplateFieldsCharacter:
    """Test get_template_fields for 'character' entity type."""

    def test_returns_non_empty_list(self) -> None:
        """Character template returns at least one field."""
        fields = get_template_fields("character")
        assert len(fields) > 0

    def test_all_fields_are_creation_fields(self) -> None:
        """All returned items are KBCreationField instances."""
        fields = get_template_fields("character")
        for field in fields:
            assert isinstance(field, KBCreationField)

    def test_flat_fields_present(self) -> None:
        """Character template includes flat fields like 'name', 'role'."""
        fields = get_template_fields("character")
        field_keys = [f.field_key for f in fields]
        # CharacterMetadata has 'role', 'age', 'gender' etc.
        assert "role" in field_keys

    def test_required_fields_marked(self) -> None:
        """Required fields from the schema are marked as required."""
        fields = get_template_fields("character")
        # KBEntryMetadata has no required fields (all optional),
        # so none should be required
        required_fields = [f for f in fields if f.required]
        # All fields in KB schemas are optional (templates are recommendations)
        assert len(required_fields) == 0


class TestGetTemplateFieldsNestedModels:
    """Test field_key naming for nested models (dot notation)."""

    def test_nested_fields_use_dot_notation(self) -> None:
        """Nested model fields use dot notation (e.g. 'appearance.height')."""
        fields = get_template_fields("character")
        field_keys = [f.field_key for f in fields]
        # CharacterMetadata has nested AppearanceFields, PersonalityFields, etc.
        dot_keys = [k for k in field_keys if "." in k]
        assert len(dot_keys) > 0, "Expected dot-notation keys for nested models"

    def test_nested_field_labels_include_parent(self) -> None:
        """Nested field labels include parent name (e.g. 'Appearance Height')."""
        fields = get_template_fields("character")
        dot_fields = [f for f in fields if "." in f.field_key]
        for field in dot_fields:
            parent = field.field_key.split(".")[0]
            assert parent.title() in field.label

    def test_appearance_nested_fields(self) -> None:
        """Character template includes appearance.* nested fields."""
        fields = get_template_fields("character")
        field_keys = [f.field_key for f in fields]
        assert "appearance.height" in field_keys
        assert "appearance.build" in field_keys

    def test_personality_nested_fields(self) -> None:
        """Character template includes personality.* nested fields."""
        fields = get_template_fields("character")
        field_keys = [f.field_key for f in fields]
        assert "personality.traits" in field_keys


class TestGetTemplateFieldsUnknownType:
    """Test get_template_fields for unknown entity types."""

    def test_falls_back_to_base(self) -> None:
        """Unknown entity type falls back to KBEntryMetadata (base)."""
        fields = get_template_fields("unknown_entity_type")
        # Base KBEntryMetadata has no fields, but extra="allow"
        # so it returns an empty list
        assert isinstance(fields, list)

    def test_base_returns_empty_or_minimal(self) -> None:
        """Base schema returns empty list (no defined fields)."""
        fields = get_template_fields("nonexistent")
        # KBEntryMetadata has no model_fields defined
        assert len(fields) == 0


class TestGetTemplateFieldsLocation:
    """Test get_template_fields for 'location' entity type."""

    def test_returns_fields(self) -> None:
        """Location template returns at least one field."""
        fields = get_template_fields("location")
        assert len(fields) > 0

    def test_field_keys_are_strings(self) -> None:
        """All field_keys are non-empty strings."""
        fields = get_template_fields("location")
        for field in fields:
            assert isinstance(field.field_key, str)
            assert len(field.field_key) > 0


class TestFieldTypeMapping:
    """Test that field types are correctly mapped from Pydantic annotations."""

    def test_list_fields_mapped_correctly(self) -> None:
        """list[str] fields are mapped to 'list' field_type."""
        fields = get_template_fields("character")
        list_fields = [f for f in fields if f.field_type == "list"]
        # CharacterMetadata has aliases: list[str] | None
        assert len(list_fields) > 0

    def test_boolean_fields_mapped_correctly(self) -> None:
        """bool fields are mapped to 'boolean' field_type."""
        fields = get_template_fields("character")
        bool_fields = [f for f in fields if f.field_type == "boolean"]
        # CharacterMetadata has pov_character: bool | None
        assert len(bool_fields) > 0

    def test_text_fields_are_default(self) -> None:
        """str fields are mapped to 'text' field_type (default)."""
        fields = get_template_fields("character")
        text_fields = [f for f in fields if f.field_type == "text"]
        assert len(text_fields) > 0
