"""Unit tests for KB metadata schemas.

Tests cover:
- Validation of each schema with valid data
- Extra fields are preserved (extra="allow")
- Wrong types are rejected (e.g. age="not a number")
- Registry lookup for all known types
- Registry returns base class for unknown type
- Empty metadata passes validation
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from narrare_core.kb.schemas import (
    SCHEMA_REGISTRY,
    CharacterMetadata,
    ConceptMetadata,
    FactionMetadata,
    KBEntryMetadata,
    LocationMetadata,
    ObjectMetadata,
    SettingMetadata,
    SystemMetadata,
    TimelineMetadata,
    get_schema,
)

# ---------------------------------------------------------------------------
# Base model
# ---------------------------------------------------------------------------


class TestKBEntryMetadata:
    """Tests for the base KBEntryMetadata model."""

    def test_empty_metadata_passes_validation(self) -> None:
        """Base model with no fields should validate successfully."""
        meta = KBEntryMetadata()
        assert meta.model_fields_set == set()

    def test_extra_fields_preserved(self) -> None:
        """Unknown fields should be accepted and accessible."""
        meta = KBEntryMetadata(custom_field="value", another=42)  # type: ignore[call-arg]
        assert meta.custom_field == "value"  # type: ignore[attr-defined]
        assert meta.another == 42  # type: ignore[attr-defined]

    def test_model_dump_includes_extras(self) -> None:
        """Serialisation should include extra fields."""
        meta = KBEntryMetadata(unknown="test")  # type: ignore[call-arg]
        dumped = meta.model_dump()
        assert dumped["unknown"] == "test"

    def test_model_config_extra_allow(self) -> None:
        """Config should allow extra fields."""
        assert KBEntryMetadata.model_config.get("extra") == "allow"


# ---------------------------------------------------------------------------
# Character
# ---------------------------------------------------------------------------


class TestCharacterMetadata:
    """Tests for the CharacterMetadata schema."""

    def test_valid_data(self) -> None:
        meta = CharacterMetadata(
            age=30,
            role="protagonist",
            arc="Hero's journey",
            gender="female",
            pronouns="she/her",
            nationality="German",
            pov_character=True,
            affiliation="Rebel Alliance",
            element="fire",
            first_appearance="Chapter 1",
            aliases=["The Flame", "Red"],
        )
        assert meta.age == 30
        assert meta.role == "protagonist"
        assert meta.aliases == ["The Flame", "Red"]

    def test_all_optional(self) -> None:
        """All fields should be optional."""
        meta = CharacterMetadata()
        assert meta.age is None
        assert meta.role is None

    def test_extra_fields_preserved(self) -> None:
        """Extra fields should pass through."""
        meta = CharacterMetadata(hair_color="red", age=25)  # type: ignore[call-arg]
        assert meta.hair_color == "red"  # type: ignore[attr-defined]

    def test_invalid_age_type_rejected(self) -> None:
        """Non-integer age should fail validation."""
        with pytest.raises(ValidationError, match="age"):
            CharacterMetadata(age="not a number")  # type: ignore[arg-type]

    def test_invalid_aliases_type_rejected(self) -> None:
        """Non-list aliases should fail validation."""
        with pytest.raises(ValidationError, match="aliases"):
            CharacterMetadata(aliases="not a list")  # type: ignore[arg-type]

    def test_pov_character_int_validation(self) -> None:
        """Non-boolean pov_character should fail validation with a list."""
        with pytest.raises(ValidationError, match="pov_character"):
            CharacterMetadata(pov_character=[1, 2, 3])  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Location
# ---------------------------------------------------------------------------


class TestLocationMetadata:
    """Tests for the LocationMetadata schema."""

    def test_valid_data(self) -> None:
        meta = LocationMetadata(
            location_type="city",
            parent_location="Kingdom of Azura",
            coordinates="42.3N, 13.1E",
            climate="temperate",
            terrain="hills",
            size="large",
            first_appearance="Chapter 2",
        )
        assert meta.location_type == "city"
        assert meta.climate == "temperate"

    def test_all_optional(self) -> None:
        meta = LocationMetadata()
        assert meta.location_type is None

    def test_extra_fields_preserved(self) -> None:
        meta = LocationMetadata(population=10000, terrain="mountain")  # type: ignore[call-arg]
        assert meta.population == 10000  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Faction
# ---------------------------------------------------------------------------


class TestFactionMetadata:
    """Tests for the FactionMetadata schema."""

    def test_valid_data(self) -> None:
        meta = FactionMetadata(
            founded="Year 300",
            members=["Alice", "Bob"],
            ideology="Freedom for all",
            first_appearance="Chapter 3",
        )
        assert meta.founded == "Year 300"
        assert meta.members == ["Alice", "Bob"]

    def test_all_optional(self) -> None:
        meta = FactionMetadata()
        assert meta.founded is None

    def test_invalid_members_type_rejected(self) -> None:
        with pytest.raises(ValidationError, match="members"):
            FactionMetadata(members="not a list")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Object
# ---------------------------------------------------------------------------


class TestObjectMetadata:
    """Tests for the ObjectMetadata schema."""

    def test_valid_data(self) -> None:
        meta = ObjectMetadata(
            object_type="weapon",
            owner="Hero",
            origin="Ancient Forge",
            first_appearance="Chapter 1",
        )
        assert meta.object_type == "weapon"
        assert meta.owner == "Hero"

    def test_all_optional(self) -> None:
        meta = ObjectMetadata()
        assert meta.object_type is None


# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------


class TestSystemMetadata:
    """Tests for the SystemMetadata schema."""

    def test_valid_data(self) -> None:
        meta = SystemMetadata(
            system_type="magic",
            practitioners=["Mage Guild"],
            first_appearance="Prologue",
        )
        assert meta.system_type == "magic"
        assert meta.practitioners == ["Mage Guild"]

    def test_all_optional(self) -> None:
        meta = SystemMetadata()
        assert meta.system_type is None


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------


class TestTimelineMetadata:
    """Tests for the TimelineMetadata schema."""

    def test_valid_data(self) -> None:
        meta = TimelineMetadata(
            era="First Age",
            start_date="Year 1",
            end_date="Year 500",
            first_appearance="Appendix",
        )
        assert meta.era == "First Age"
        assert meta.start_date == "Year 1"

    def test_all_optional(self) -> None:
        meta = TimelineMetadata()
        assert meta.era is None


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestSchemaRegistry:
    """Tests for the schema registry and get_schema helper."""

    @pytest.mark.parametrize(
        "entity_type",
        ["character", "concept", "faction", "location", "object", "setting", "system", "timeline"],
    )
    def test_known_type_returns_correct_schema(self, entity_type: str) -> None:
        """All known entity types should map to their specific schema."""
        schema = get_schema(entity_type)
        assert schema is SCHEMA_REGISTRY[entity_type]
        assert issubclass(schema, KBEntryMetadata)
        assert schema is not KBEntryMetadata

    def test_unknown_type_returns_base(self) -> None:
        """Unknown entity types should fall back to KBEntryMetadata."""
        schema = get_schema("unknown_entity_type")
        assert schema is KBEntryMetadata

    def test_empty_string_returns_base(self) -> None:
        """Empty string should fall back to base."""
        schema = get_schema("")
        assert schema is KBEntryMetadata

    def test_registry_has_eight_entries(self) -> None:
        """Registry should contain exactly the 8 known entity types."""
        assert len(SCHEMA_REGISTRY) == 8
        expected = {
            "character",
            "concept",
            "faction",
            "location",
            "object",
            "setting",
            "system",
            "timeline",
        }
        assert set(SCHEMA_REGISTRY.keys()) == expected


# ---------------------------------------------------------------------------
# Cross-schema validation
# ---------------------------------------------------------------------------


class TestCrossSchemaValidation:
    """Tests verifying consistent behaviour across all schemas."""

    @pytest.mark.parametrize(
        "schema_cls",
        [
            KBEntryMetadata,
            CharacterMetadata,
            ConceptMetadata,
            FactionMetadata,
            LocationMetadata,
            ObjectMetadata,
            SettingMetadata,
            SystemMetadata,
            TimelineMetadata,
        ],
    )
    def test_all_schemas_allow_empty(self, schema_cls: type[KBEntryMetadata]) -> None:
        """Every schema should accept an empty dict."""
        instance = schema_cls()
        assert instance is not None

    @pytest.mark.parametrize(
        "schema_cls",
        [
            KBEntryMetadata,
            CharacterMetadata,
            ConceptMetadata,
            FactionMetadata,
            LocationMetadata,
            ObjectMetadata,
            SettingMetadata,
            SystemMetadata,
            TimelineMetadata,
        ],
    )
    def test_all_schemas_allow_extras(self, schema_cls: type[KBEntryMetadata]) -> None:
        """Every schema should accept arbitrary extra fields."""
        instance = schema_cls(custom_unknown_field="anything")  # type: ignore[call-arg]
        dumped = instance.model_dump()
        assert dumped["custom_unknown_field"] == "anything"
