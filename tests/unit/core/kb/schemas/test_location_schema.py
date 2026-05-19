"""Unit tests for enriched LocationMetadata schema with nested groups.

Tests cover:
- LocationMetadata with flat fields (backward compat)
- LocationMetadata with nested group fields
- Nested group models have extra="allow"
- Extra fields preserved on both metadata and nested groups
"""

from __future__ import annotations

from narrare_core.kb.schemas import (
    LocationFeatures,
    LocationHistory,
    LocationInhabitants,
    LocationMetadata,
)


class TestLocationFeatures:
    """Tests for the LocationFeatures nested group model."""

    def test_all_optional(self) -> None:
        fields = LocationFeatures()
        assert fields.architecture is None
        assert fields.natural_features is None

    def test_with_data(self) -> None:
        fields = LocationFeatures(
            architecture="Gothic",
            natural_features=["river", "mountains"],
            landmarks=["Great Tower"],
            atmosphere="Mysterious",
        )
        assert fields.architecture == "Gothic"
        assert "river" in fields.natural_features  # type: ignore[operator]
        assert fields.atmosphere == "Mysterious"

    def test_extra_fields_preserved(self) -> None:
        fields = LocationFeatures(
            architecture="Baroque",
            weather="rainy",  # type: ignore[call-arg]
        )
        assert fields.weather == "rainy"  # type: ignore[attr-defined]

    def test_model_config_extra_allow(self) -> None:
        assert LocationFeatures.model_config.get("extra") == "allow"


class TestLocationInhabitants:
    """Tests for the LocationInhabitants nested group model."""

    def test_all_optional(self) -> None:
        fields = LocationInhabitants()
        assert fields.population is None

    def test_with_data(self) -> None:
        fields = LocationInhabitants(
            population="5000",
            species=["Human", "Elf"],
            factions=["Merchant Guild"],
        )
        assert fields.population == "5000"
        assert fields.species is not None
        assert len(fields.species) == 2


class TestLocationHistory:
    """Tests for the LocationHistory nested group model."""

    def test_all_optional(self) -> None:
        fields = LocationHistory()
        assert fields.founded is None

    def test_with_data(self) -> None:
        fields = LocationHistory(
            founded="Year 1000",
            key_events=["Great Fire", "Siege"],
            current_state="Prosperous",
        )
        assert fields.current_state == "Prosperous"


class TestLocationMetadataEnriched:
    """Tests for LocationMetadata with nested groups."""

    def test_flat_fields_only(self) -> None:
        """Backward compat: flat fields still work."""
        meta = LocationMetadata(
            location_type="city",
            climate="temperate",
            terrain="hills",
        )
        assert meta.location_type == "city"
        assert meta.climate == "temperate"

    def test_with_nested_groups(self) -> None:
        meta = LocationMetadata(
            location_type="kingdom",
            features=LocationFeatures(
                architecture="Medieval",
                natural_features=["forests"],
            ),
            inhabitants=LocationInhabitants(
                population="10,000",
            ),
            history=LocationHistory(
                founded="Year 500",
            ),
        )
        assert meta.location_type == "kingdom"
        assert meta.features is not None
        assert meta.features.architecture == "Medieval"
        assert meta.inhabitants is not None
        assert meta.inhabitants.population == "10,000"
        assert meta.history is not None
        assert meta.history.founded == "Year 500"

    def test_nested_groups_optional(self) -> None:
        meta = LocationMetadata(location_type="village")
        assert meta.features is None
        assert meta.inhabitants is None
        assert meta.history is None

    def test_extra_fields_on_metadata(self) -> None:
        meta = LocationMetadata(
            location_type="city",
            magic_level="high",  # type: ignore[call-arg]
        )
        assert meta.magic_level == "high"  # type: ignore[attr-defined]

    def test_extra_fields_in_group(self) -> None:
        meta = LocationMetadata(
            features=LocationFeatures(
                architecture="Modern",
                hidden_ruins=True,  # type: ignore[call-arg]
            ),
        )
        assert meta.features is not None
        assert meta.features.hidden_ruins is True  # type: ignore[attr-defined]

    def test_empty_metadata(self) -> None:
        meta = LocationMetadata()
        assert meta.location_type is None
