"""Unit tests for enriched CharacterMetadata schema with nested groups.

Tests cover:
- CharacterMetadata with flat fields (backward compat)
- CharacterMetadata with nested group fields
- Nested group models have extra="allow"
- Extra fields preserved on both metadata and nested groups
- Validation constraints maintained
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from narrare_core.kb.schemas import (
    AppearanceFields,
    BackgroundFields,
    CharacterMetadata,
    DevelopmentFields,
    PersonalityFields,
    RelationshipFields,
    SpeechPatterns,
)


class TestAppearanceFields:
    """Tests for the AppearanceFields nested group model."""

    def test_all_optional(self) -> None:
        fields = AppearanceFields()
        assert fields.height is None
        assert fields.build is None

    def test_with_data(self) -> None:
        fields = AppearanceFields(
            height="6'0\"",
            build="athletic",
            hair_color="brown",
            eye_color="green",
        )
        assert fields.height == "6'0\""
        assert fields.hair_color == "brown"

    def test_extra_fields_preserved(self) -> None:
        fields = AppearanceFields(
            height="5'8\"",
            tattoo="dragon",  # type: ignore[call-arg]
        )
        assert fields.tattoo == "dragon"  # type: ignore[attr-defined]

    def test_model_config_extra_allow(self) -> None:
        assert AppearanceFields.model_config.get("extra") == "allow"


class TestPersonalityFields:
    """Tests for the PersonalityFields nested group model."""

    def test_all_optional(self) -> None:
        fields = PersonalityFields()
        assert fields.traits is None
        assert fields.quirks is None

    def test_with_data(self) -> None:
        fields = PersonalityFields(
            traits=["brave", "curious"],
            strengths=["determination"],
            weaknesses=["stubbornness"],
        )
        assert fields.traits == ["brave", "curious"]
        assert fields.strengths == ["determination"]

    def test_extra_fields_preserved(self) -> None:
        fields = PersonalityFields(mbti="INTJ", traits=["analytical"])  # type: ignore[call-arg]
        assert fields.mbti == "INTJ"  # type: ignore[attr-defined]


class TestBackgroundFields:
    """Tests for the BackgroundFields nested group model."""

    def test_all_optional(self) -> None:
        fields = BackgroundFields()
        assert fields.family is None
        assert fields.key_events is None

    def test_with_data(self) -> None:
        fields = BackgroundFields(
            family="Noble family",
            upbringing="Strict",
            key_events=["Left home", "Met mentor"],
        )
        assert fields.family == "Noble family"
        assert fields.key_events is not None
        assert len(fields.key_events) == 2


class TestSpeechPatterns:
    """Tests for the SpeechPatterns nested group model."""

    def test_all_optional(self) -> None:
        fields = SpeechPatterns()
        assert fields.dialect is None
        assert fields.typical_phrases is None

    def test_with_data(self) -> None:
        fields = SpeechPatterns(
            typical_phrases=["Indeed", "Fascinating"],
            dialect="Upper class",
        )
        assert "Indeed" in fields.typical_phrases  # type: ignore[operator]


class TestRelationshipFields:
    """Tests for the RelationshipFields nested group model."""

    def test_all_optional(self) -> None:
        fields = RelationshipFields()
        assert fields.allies is None

    def test_with_data(self) -> None:
        fields = RelationshipFields(
            allies=["Alice", "Bob"],
            rivals=["Malice"],
            notes="Secretly related",
        )
        assert fields.notes == "Secretly related"


class TestDevelopmentFields:
    """Tests for the DevelopmentFields nested group model."""

    def test_all_optional(self) -> None:
        fields = DevelopmentFields()
        assert fields.starting_point is None

    def test_with_data(self) -> None:
        fields = DevelopmentFields(
            starting_point="Farm boy",
            key_turning_points=["Leaves home", "Defeats villain"],
            planned_arc="Hero's journey",
        )
        assert fields.planned_arc == "Hero's journey"


class TestCharacterMetadataEnriched:
    """Tests for CharacterMetadata with nested groups."""

    def test_flat_fields_only(self) -> None:
        """Backward compat: flat fields still work."""
        meta = CharacterMetadata(
            age=30,
            role="protagonist",
            aliases=["Hero"],
        )
        assert meta.age == 30
        assert meta.role == "protagonist"

    def test_with_nested_groups(self) -> None:
        meta = CharacterMetadata(
            age=25,
            appearance=AppearanceFields(
                height="5'10\"",
                hair_color="blonde",
            ),
            personality=PersonalityFields(
                traits=["bold"],
                motivations="To find the truth",
            ),
            background=BackgroundFields(
                family="Merchant family",
                upbringing="Privileged",
            ),
        )
        assert meta.age == 25
        assert meta.appearance is not None
        assert meta.appearance.height == "5'10\""
        assert meta.personality is not None
        assert meta.personality.motivations == "To find the truth"
        assert meta.background is not None
        assert meta.background.family == "Merchant family"

    def test_nested_groups_optional(self) -> None:
        """Nested groups should be None when not provided."""
        meta = CharacterMetadata(age=30)
        assert meta.appearance is None
        assert meta.personality is None
        assert meta.background is None
        assert meta.speech is None
        assert meta.relationships is None
        assert meta.development is None

    def test_all_groups(self) -> None:
        """All six nested groups should work together."""
        meta = CharacterMetadata(
            appearance=AppearanceFields(height="6'0\""),
            personality=PersonalityFields(traits=["kind"]),
            background=BackgroundFields(education="Self-taught"),
            speech=SpeechPatterns(dialect="Southern"),
            relationships=RelationshipFields(allies=["Friend"]),
            development=DevelopmentFields(current_state="Mid-journey"),
        )
        assert meta.appearance is not None
        assert meta.personality is not None
        assert meta.background is not None
        assert meta.speech is not None
        assert meta.relationships is not None
        assert meta.development is not None

    def test_extra_fields_on_metadata(self) -> None:
        """Extra fields should be preserved (inherited from KBEntryMetadata)."""
        meta = CharacterMetadata(
            age=30,
            custom_flag=True,  # type: ignore[call-arg]
        )
        assert meta.custom_flag is True  # type: ignore[attr-defined]

    def test_extra_fields_in_group(self) -> None:
        """Extra fields within nested groups should be preserved."""
        meta = CharacterMetadata(
            appearance=AppearanceFields(
                height="5'5\"",
                extra_attribute="custom",  # type: ignore[call-arg]
            ),
        )
        assert meta.appearance is not None
        assert meta.appearance.extra_attribute == "custom"  # type: ignore[attr-defined]

    def test_validation_maintained(self) -> None:
        """Type validation should still work for flat fields."""
        with pytest.raises(ValidationError, match="age"):
            CharacterMetadata(age="not a number")  # type: ignore[arg-type]

    def test_empty_metadata(self) -> None:
        """Empty metadata should pass validation."""
        meta = CharacterMetadata()
        assert meta.age is None
        assert meta.role is None

    def test_model_dump_includes_groups(self) -> None:
        """Serialisation should include nested groups."""
        meta = CharacterMetadata(
            appearance=AppearanceFields(height="6'2\""),
        )
        dumped = meta.model_dump()
        assert dumped["appearance"] is not None
        assert dumped["appearance"]["height"] == "6'2\""
