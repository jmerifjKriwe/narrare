"""Unit tests for SettingMetadata schema with nested groups.

Tests cover:
- SettingMetadata with flat fields (backward compat)
- SettingMetadata with nested group fields
- Nested group models have extra="allow"
- Extra fields preserved on both metadata and nested groups
- Validation constraints maintained
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from narrare_core.kb.schemas import (
    SettingBasics,
    SettingGeography,
    SettingMetadata,
    SettingSociety,
    SettingWorldRules,
)


class TestSettingBasics:
    """Tests for the SettingBasics nested group model."""

    def test_all_optional(self) -> None:
        fields = SettingBasics()
        assert fields.genre is None
        assert fields.time_period is None

    def test_with_data(self) -> None:
        fields = SettingBasics(
            genre="fantasy",
            time_period="Medieval",
            tone="dark",
            atmosphere="foreboding",
        )
        assert fields.genre == "fantasy"
        assert fields.time_period == "Medieval"
        assert fields.tone == "dark"

    def test_extra_fields_preserved(self) -> None:
        fields = SettingBasics(
            genre="sci-fi",
            custom_theme="cyberpunk",  # type: ignore[call-arg]
        )
        assert fields.custom_theme == "cyberpunk"  # type: ignore[attr-defined]

    def test_model_config_extra_allow(self) -> None:
        assert SettingBasics.model_config.get("extra") == "allow"


class TestSettingWorldRules:
    """Tests for the SettingWorldRules nested group model."""

    def test_all_optional(self) -> None:
        fields = SettingWorldRules()
        assert fields.magic_level is None
        assert fields.tech_level is None

    def test_with_data(self) -> None:
        fields = SettingWorldRules(
            magic_level="high",
            tech_level="steampunk",
            supernatural_elements=["ghosts", "dragons"],
            limitations=["No resurrection"],
        )
        assert fields.magic_level == "high"
        assert fields.supernatural_elements is not None
        assert "dragons" in fields.supernatural_elements

    def test_extra_fields_preserved(self) -> None:
        fields = SettingWorldRules(
            magic_level="low",
            extra_rule="no_time_travel",  # type: ignore[call-arg]
        )
        assert fields.extra_rule == "no_time_travel"  # type: ignore[attr-defined]


class TestSettingSociety:
    """Tests for the SettingSociety nested group model."""

    def test_all_optional(self) -> None:
        fields = SettingSociety()
        assert fields.political_structure is None
        assert fields.cultural_values is None

    def test_with_data(self) -> None:
        fields = SettingSociety(
            political_structure="constitutional monarchy",
            cultural_values=["honor", "tradition"],
            social_classes=["nobility", "commoners", "slaves"],
            major_conflicts=["class warfare"],
        )
        assert fields.political_structure == "constitutional monarchy"
        assert fields.cultural_values is not None
        assert "honor" in fields.cultural_values

    def test_extra_fields_preserved(self) -> None:
        fields = SettingSociety(
            political_structure="theocracy",
            state_religion="official",  # type: ignore[call-arg]
        )
        assert fields.state_religion == "official"  # type: ignore[attr-defined]


class TestSettingGeography:
    """Tests for the SettingGeography nested group model."""

    def test_all_optional(self) -> None:
        fields = SettingGeography()
        assert fields.central_location is None
        assert fields.landmarks is None

    def test_with_data(self) -> None:
        fields = SettingGeography(
            central_location="Capital City",
            landmarks=["Great Library", "Old Quarter"],
            dangerous_areas=["The Wastes", "Dark Forest"],
        )
        assert fields.central_location == "Capital City"
        assert fields.landmarks is not None
        assert len(fields.landmarks) == 2

    def test_extra_fields_preserved(self) -> None:
        fields = SettingGeography(
            central_location="Island",
            climate_data="temperate",  # type: ignore[call-arg]
        )
        assert fields.climate_data == "temperate"  # type: ignore[attr-defined]


class TestSettingMetadata:
    """Tests for SettingMetadata with nested groups."""

    def test_flat_fields_only(self) -> None:
        """Backward compat: flat fields still work."""
        meta = SettingMetadata(setting_type="primary")
        assert meta.setting_type == "primary"

    def test_with_nested_groups(self) -> None:
        meta = SettingMetadata(
            setting_type="primary",
            basics=SettingBasics(
                genre="fantasy",
                time_period="Medieval",
                tone="dark",
            ),
            world_rules=SettingWorldRules(
                magic_level="high",
                tech_level="medieval",
            ),
            society=SettingSociety(
                political_structure="feudal",
                cultural_values=["chivalry"],
            ),
            geography=SettingGeography(
                central_location="The Kingdom",
                landmarks=["Castle", "Forest"],
            ),
        )
        assert meta.setting_type == "primary"
        assert meta.basics is not None
        assert meta.basics.genre == "fantasy"
        assert meta.world_rules is not None
        assert meta.world_rules.magic_level == "high"
        assert meta.society is not None
        assert meta.society.political_structure == "feudal"
        assert meta.geography is not None
        assert meta.geography.central_location == "The Kingdom"

    def test_nested_groups_optional(self) -> None:
        """Nested groups should be None when not provided."""
        meta = SettingMetadata(setting_type="secondary")
        assert meta.basics is None
        assert meta.world_rules is None
        assert meta.society is None
        assert meta.geography is None

    def test_all_groups(self) -> None:
        """All nested groups should work together."""
        meta = SettingMetadata(
            basics=SettingBasics(genre="sci-fi"),
            world_rules=SettingWorldRules(tech_level="advanced"),
            society=SettingSociety(political_structure="republic"),
            geography=SettingGeography(central_location="Space Station"),
        )
        assert meta.basics is not None
        assert meta.world_rules is not None
        assert meta.society is not None
        assert meta.geography is not None

    def test_extra_fields_on_metadata(self) -> None:
        """Extra fields should be preserved (inherited from KBEntryMetadata)."""
        meta = SettingMetadata(
            setting_type="primary",
            custom_flag=True,  # type: ignore[call-arg]
        )
        assert meta.custom_flag is True  # type: ignore[attr-defined]

    def test_extra_fields_in_group(self) -> None:
        """Extra fields within nested groups should be preserved."""
        meta = SettingMetadata(
            basics=SettingBasics(
                genre="fantasy",
                extra_attribute="custom",  # type: ignore[call-arg]
            ),
        )
        assert meta.basics is not None
        assert meta.basics.extra_attribute == "custom"  # type: ignore[attr-defined]

    def test_validation_maintained(self) -> None:
        """Type validation should still work for flat fields."""
        with pytest.raises(ValidationError, match="setting_type"):
            SettingMetadata(setting_type=42)  # type: ignore[arg-type]

    def test_empty_metadata(self) -> None:
        """Empty metadata should pass validation."""
        meta = SettingMetadata()
        assert meta.setting_type is None

    def test_model_dump_includes_groups(self) -> None:
        """Serialisation should include nested groups."""
        meta = SettingMetadata(
            basics=SettingBasics(genre="historical"),
        )
        dumped = meta.model_dump()
        assert dumped["basics"] is not None
        assert dumped["basics"]["genre"] == "historical"
