"""Unit tests for prompts/variable_metadata.py — VariableMeta dataclass and registry.

Covers VariableMeta creation, defaults, immutability, get_variable_info(),
get_variables_for_names(), and registry completeness.
"""

from __future__ import annotations

from typing import ClassVar

import pytest

from narrare_core.prompts.variable_metadata import (
    VARIABLE_REGISTRY,
    VariableMeta,
    get_variable_info,
    get_variables_for_names,
)

# =====================================================================
# VariableMeta — dataclass behavior
# =====================================================================


class TestVariableMetaCreation:
    """Test VariableMeta creation and field access."""

    def test_creation_with_all_fields(self) -> None:
        meta = VariableMeta(
            name="language",
            description="ISO language code",
            variable_type="text",
            required=True,
            default="en",
        )
        assert meta.name == "language"
        assert meta.description == "ISO language code"
        assert meta.variable_type == "text"
        assert meta.required is True
        assert meta.default == "en"

    def test_creation_with_defaults(self) -> None:
        meta = VariableMeta(name="genre", description="Genre of the work", variable_type="text")
        assert meta.required is False  # default is False
        assert meta.default == ""  # default is empty string

    def test_creation_required_true(self) -> None:
        meta = VariableMeta(
            name="language",
            description="ISO language code",
            variable_type="text",
            required=True,
        )
        assert meta.required is True

    def test_creation_with_list_type(self) -> None:
        meta = VariableMeta(
            name="kb_context_entries",
            description="Relevant KB entries",
            variable_type="list",
        )
        assert meta.variable_type == "list"

    def test_creation_with_number_type(self) -> None:
        meta = VariableMeta(
            name="count",
            description="Number of items",
            variable_type="number",
        )
        assert meta.variable_type == "number"


class TestVariableMetaEquality:
    """Test VariableMeta equality and inequality (frozen dataclass)."""

    def test_equal_instances(self) -> None:
        a = VariableMeta(
            name="language", description="ISO code", variable_type="text", required=True
        )
        b = VariableMeta(
            name="language", description="ISO code", variable_type="text", required=True
        )
        assert a == b

    def test_unequal_name(self) -> None:
        a = VariableMeta(name="language", description="ISO code", variable_type="text")
        b = VariableMeta(name="genre", description="ISO code", variable_type="text")
        assert a != b

    def test_unequal_required(self) -> None:
        a = VariableMeta(
            name="language", description="ISO code", variable_type="text", required=True
        )
        b = VariableMeta(
            name="language", description="ISO code", variable_type="text", required=False
        )
        assert a != b

    def test_hash_equal_instances(self) -> None:
        a = VariableMeta(name="language", description="ISO code", variable_type="text")
        b = VariableMeta(name="language", description="ISO code", variable_type="text")
        assert hash(a) == hash(b)

    def test_usable_in_set(self) -> None:
        a = VariableMeta(name="language", description="ISO code", variable_type="text")
        b = VariableMeta(name="language", description="ISO code", variable_type="text")
        c = VariableMeta(name="genre", description="Genre", variable_type="text")
        assert len({a, b, c}) == 2

    def test_usable_as_dict_key(self) -> None:
        meta = VariableMeta(name="language", description="ISO code", variable_type="text")
        mapping = {meta: "value"}
        assert mapping[meta] == "value"


class TestVariableMetaImmutability:
    """Test that VariableMeta is frozen (immutable)."""

    def test_cannot_set_name(self) -> None:
        meta = VariableMeta(name="language", description="ISO code", variable_type="text")
        with pytest.raises(AttributeError):
            meta.name = "changed"  # type: ignore[misc]

    def test_cannot_set_required(self) -> None:
        meta = VariableMeta(name="language", description="ISO code", variable_type="text")
        with pytest.raises(AttributeError):
            meta.required = True  # type: ignore[misc]

    def test_cannot_add_attribute(self) -> None:
        """Slots=True prevents adding new attributes."""
        meta = VariableMeta(name="language", description="ISO code", variable_type="text")
        with pytest.raises((AttributeError, TypeError)):
            meta.extra = "unexpected"  # type: ignore[attr-defined]

    def test_has_no_dict_attribute(self) -> None:
        """Slots=True means no __dict__ — memory-efficient and prevents dynamic attrs."""
        meta = VariableMeta(name="language", description="ISO code", variable_type="text")
        assert not hasattr(meta, "__dict__")


class TestVariableMetaRepr:
    """Test VariableMeta string representation."""

    def test_repr_contains_class_name(self) -> None:
        meta = VariableMeta(name="language", description="ISO code", variable_type="text")
        assert "VariableMeta" in repr(meta)

    def test_str_contains_name(self) -> None:
        meta = VariableMeta(name="language", description="ISO code", variable_type="text")
        assert "language" in str(meta)


# =====================================================================
# get_variable_info() — lookup function
# =====================================================================


class TestGetVariableInfo:
    """Test get_variable_info() lookup behavior."""

    def test_returns_metadata_for_known_variable(self) -> None:
        result = get_variable_info("language")
        assert result is not None
        assert result.name == "language"
        assert result.variable_type == "text"
        assert result.required is True

    def test_returns_none_for_unknown_variable(self) -> None:
        result = get_variable_info("nonexistent_variable")
        assert result is None

    def test_returns_correct_metadata_for_genre(self) -> None:
        result = get_variable_info("genre")
        assert result is not None
        assert result.name == "genre"
        assert result.required is False

    def test_returns_correct_metadata_for_count(self) -> None:
        result = get_variable_info("count")
        assert result is not None
        assert result.name == "count"
        assert result.variable_type == "number"

    def test_returns_correct_metadata_for_kb_context_entries(self) -> None:
        result = get_variable_info("kb_context_entries")
        assert result is not None
        assert result.variable_type == "list"

    def test_empty_string_returns_none(self) -> None:
        result = get_variable_info("")
        assert result is None


# =====================================================================
# get_variables_for_names() — batch lookup
# =====================================================================


class TestGetVariablesForNames:
    """Test get_variables_for_names() batch lookup behavior."""

    def test_filters_correctly(self) -> None:
        result = get_variables_for_names(["language", "genre"])
        assert len(result) == 2
        names = {v.name for v in result}
        assert names == {"language", "genre"}

    def test_skips_unknown_names(self) -> None:
        result = get_variables_for_names(["language", "nonexistent", "genre"])
        assert len(result) == 2
        names = {v.name for v in result}
        assert names == {"language", "genre"}

    def test_empty_list_returns_empty(self) -> None:
        result = get_variables_for_names([])
        assert result == []

    def test_all_unknown_returns_empty(self) -> None:
        result = get_variables_for_names(["unknown1", "unknown2"])
        assert result == []

    def test_preserves_order_of_known_names(self) -> None:
        """Known names appear in the order they were requested."""
        result = get_variables_for_names(["genre", "language"])
        assert result[0].name == "genre"
        assert result[1].name == "language"

    def test_single_name_returns_single_entry(self) -> None:
        result = get_variables_for_names(["language"])
        assert len(result) == 1
        assert result[0].name == "language"


# =====================================================================
# VARIABLE_REGISTRY — completeness and invariants
# =====================================================================


class TestVariableRegistryCompleteness:
    """Test that VARIABLE_REGISTRY has all expected entries and invariants."""

    # Expected prompt variables that MUST have metadata entries.
    # These mirror fields from PromptContext plus generation-specific variables.
    EXPECTED_VARIABLES: ClassVar[list[str]] = [
        # Project metadata
        "language",
        "project_title",
        "genre",
        "tone",
        "story_structure",
        "author_name",
        # Novel context
        "novel_synopsis",
        "style_profile",
        # Chapter context
        "mode",
        "chapter_title",
        "existing_content",
        "author_instructions",
        "previous_chapter_summary",
        "next_chapter_hint",
        # KB context
        "kb_context_entries",
        "kb_summary",
        # Entity context
        "entity_type",
        "entity_name",
        "entity_current_content",
        "entity_template",
        "entity_focus_areas",
        # Analysis context
        "text_to_analyse",
        "analysis_focus",
        # Generation-specific
        "name_type",
        "count",
        "gender",
        "existing_names",
        "culture_guidelines",
        "name_style",
        "writing_language",
        "explanation_language",
        # Memory / Preference context
        "user_preferences",
        "avoidance_patterns",
        "style_constraints",
    ]

    def test_registry_has_all_expected_variables(self) -> None:
        """Every expected variable name has a registry entry."""
        for var_name in self.EXPECTED_VARIABLES:
            assert var_name in VARIABLE_REGISTRY, f"Missing registry entry for '{var_name}'"

    def test_registry_keys_match_variable_names(self) -> None:
        """Each registry key matches the VariableMeta.name field."""
        for key, meta in VARIABLE_REGISTRY.items():
            assert key == meta.name, f"Registry key '{key}' != meta.name '{meta.name}'"

    def test_all_descriptions_non_empty(self) -> None:
        """Every variable has a non-empty description."""
        for key, meta in VARIABLE_REGISTRY.items():
            assert len(meta.description) > 0, f"Variable '{key}' has empty description"

    def test_all_variable_types_valid(self) -> None:
        """Every variable has a recognized variable_type."""
        valid_types = {"text", "list", "number"}
        for key, meta in VARIABLE_REGISTRY.items():
            assert meta.variable_type in valid_types, (
                f"Variable '{key}' has unexpected type '{meta.variable_type}'"
            )

    def test_required_variables_are_marked(self) -> None:
        """Language is required; verify the flag is set."""
        language = VARIABLE_REGISTRY["language"]
        assert language.required is True, "language should be marked as required"

    def test_optional_variables_have_defaults(self) -> None:
        """Optional variables should have empty string as default."""
        genre = VARIABLE_REGISTRY["genre"]
        assert genre.required is False
        assert genre.default == ""

    def test_registry_is_dict(self) -> None:
        """VARIABLE_REGISTRY is a dict[str, VariableMeta]."""
        assert isinstance(VARIABLE_REGISTRY, dict)
        for key in VARIABLE_REGISTRY:
            assert isinstance(key, str)
            assert isinstance(VARIABLE_REGISTRY[key], VariableMeta)

    def test_no_duplicate_entries(self) -> None:
        """No duplicate variable names in the registry."""
        names = [meta.name for meta in VARIABLE_REGISTRY.values()]
        assert len(names) == len(set(names)), "Duplicate variable names found in registry"
