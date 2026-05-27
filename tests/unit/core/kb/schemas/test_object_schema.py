"""Tests for kb/schemas/object.py — ObjectMetadata schema validation.

Covers:
1. Flat fields (backward compat)
2. Nested group models: ObjectProperties, ObjectOrigin, ObjectSignificance
3. Extra fields preserved (extra="allow")
4. Empty metadata passes validation
"""

from __future__ import annotations

from narrare_core.kb.schemas.object import (
    ObjectMetadata,
    ObjectOrigin,
    ObjectProperties,
    ObjectSignificance,
)


class TestObjectProperties:
    """ObjectProperties nested group model."""

    def test_all_optional(self) -> None:
        p = ObjectProperties()
        assert p.material is None
        assert p.dimensions is None
        assert p.weight is None
        assert p.condition is None
        assert p.appearance is None

    def test_with_data(self) -> None:
        p = ObjectProperties(
            material="Mithril",
            dimensions="12 inches long",
            weight="Light as a feather",
            condition="Pristine",
            appearance="Glows blue near orcs",
        )
        assert p.material == "Mithril"

    def test_extra_fields_preserved(self) -> None:
        p = ObjectProperties(material="Steel", enchantment="Fire resistance")  # type: ignore[call-arg]
        assert p.enchantment == "Fire resistance"  # type: ignore[attr-defined]


class TestObjectOrigin:
    """ObjectOrigin nested group model."""

    def test_all_optional(self) -> None:
        o = ObjectOrigin()
        assert o.creator is None

    def test_with_data(self) -> None:
        o = ObjectOrigin(
            creator="Elven smiths",
            created_date="Third Age",
            place_of_origin="Rivendell",
            method_of_creation="Forged in dragon fire",
        )
        assert o.creator == "Elven smiths"


class TestObjectSignificance:
    """ObjectSignificance nested group model."""

    def test_all_optional(self) -> None:
        s = ObjectSignificance()
        assert s.purpose is None

    def test_with_data(self) -> None:
        s = ObjectSignificance(
            purpose="Destroy the One Ring",
            powers=["Invisibility", "Fire resistance"],
            historical_significance="Central to the War of the Ring",
            current_location="With the hero",
        )
        assert len(s.powers or []) == 2


class TestObjectMetadata:
    """ObjectMetadata with flat and nested fields."""

    def test_flat_fields_only(self) -> None:
        meta = ObjectMetadata(
            object_type="weapon",
            owner="Alice",
            origin="Ancient forge",
        )
        assert meta.object_type == "weapon"
        assert meta.owner == "Alice"

    def test_with_nested_groups(self) -> None:
        meta = ObjectMetadata(
            object_type="artifact",
            properties=ObjectProperties(material="Crystal"),
            origin_details=ObjectOrigin(creator="Ancient civilization"),
            significance=ObjectSignificance(purpose="Seal the dark lord"),
        )
        assert meta.properties is not None
        assert meta.properties.material == "Crystal"
        assert meta.origin_details is not None
        assert meta.significance is not None

    def test_nested_groups_optional(self) -> None:
        meta = ObjectMetadata()
        assert meta.properties is None
        assert meta.origin_details is None
        assert meta.significance is None

    def test_extra_fields_preserved(self) -> None:
        meta = ObjectMetadata(custom_field="magic")  # type: ignore[call-arg]
        assert meta.custom_field == "magic"  # type: ignore[attr-defined]

    def test_empty_metadata(self) -> None:
        meta = ObjectMetadata()
        assert meta.object_type is None
        assert meta.owner is None

    def test_serialization_roundtrip(self) -> None:
        meta = ObjectMetadata(
            object_type="scroll",
            properties=ObjectProperties(material="Parchment"),
        )
        data = meta.model_dump()
        restored = ObjectMetadata.model_validate(data)
        assert restored.object_type == "scroll"
        assert restored.properties is not None
