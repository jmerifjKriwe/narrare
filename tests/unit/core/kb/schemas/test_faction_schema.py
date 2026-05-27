"""Tests for kb/schemas/faction.py — FactionMetadata schema validation.

Covers:
1. Flat fields (backward compat)
2. Nested group models: FactionStructure, FactionIdeology, FactionHistory
3. Extra fields preserved (extra="allow")
4. Empty metadata passes validation
5. Serialization roundtrip
"""

from __future__ import annotations

from narrare_core.kb.schemas.faction import (
    FactionHistory,
    FactionIdeology,
    FactionMetadata,
    FactionStructure,
)


class TestFactionStructure:
    """FactionStructure nested group model."""

    def test_all_optional(self) -> None:
        s = FactionStructure()
        assert s.leadership is None
        assert s.hierarchy is None
        assert s.membership_count is None
        assert s.headquarters is None

    def test_with_data(self) -> None:
        s = FactionStructure(
            leadership="Council of Elders",
            hierarchy="Democratic",
            membership_count="500",
            headquarters="The Citadel",
        )
        assert s.leadership == "Council of Elders"

    def test_extra_fields_preserved(self) -> None:
        s = FactionStructure(
            leadership="King",
            succession_rule="Primogeniture",  # type: ignore[call-arg]
        )
        assert s.succession_rule == "Primogeniture"  # type: ignore[attr-defined]


class TestFactionIdeology:
    """FactionIdeology nested group model."""

    def test_all_optional(self) -> None:
        i = FactionIdeology()
        assert i.beliefs is None
        assert i.goals is None

    def test_with_lists(self) -> None:
        i = FactionIdeology(
            beliefs=["Freedom", "Equality"],
            goals=["Overthrow the tyrant"],
            methods="Diplomacy and sabotage",
        )
        assert len(i.beliefs or []) == 2

    def test_extra_fields_preserved(self) -> None:
        i = FactionIdeology(motto="Liberty or Death", beliefs=["Freedom"])  # type: ignore[call-arg]
        assert i.motto == "Liberty or Death"  # type: ignore[attr-defined]


class TestFactionHistory:
    """FactionHistory nested group model."""

    def test_all_optional(self) -> None:
        h = FactionHistory()
        assert h.founded is None

    def test_with_data(self) -> None:
        h = FactionHistory(
            founded="300 years ago",
            key_events=["The Great Schism", "The Reformation"],
            current_status="Active and growing",
        )
        assert len(h.key_events or []) == 2


class TestFactionMetadata:
    """FactionMetadata with flat and nested fields."""

    def test_flat_fields_only(self) -> None:
        meta = FactionMetadata(
            founded="1000 AD",
            members=["Alice", "Bob"],
            ideology="Militaristic",
        )
        assert meta.founded == "1000 AD"
        assert len(meta.members or []) == 2

    def test_with_nested_groups(self) -> None:
        meta = FactionMetadata(
            ideology="Democratic",
            structure=FactionStructure(leadership="Council"),
            belief_system=FactionIdeology(beliefs=["Justice"]),
            history=FactionHistory(founded="500 BC"),
        )
        assert meta.structure is not None
        assert meta.structure.leadership == "Council"
        assert meta.belief_system is not None
        assert meta.history is not None

    def test_nested_groups_optional(self) -> None:
        meta = FactionMetadata()
        assert meta.structure is None
        assert meta.belief_system is None
        assert meta.history is None

    def test_extra_fields_preserved(self) -> None:
        meta = FactionMetadata(
            founded="1200",
            custom_flag=True,  # type: ignore[call-arg]
        )
        assert meta.custom_flag is True  # type: ignore[attr-defined]

    def test_empty_metadata(self) -> None:
        meta = FactionMetadata()
        assert meta.founded is None
        assert meta.members is None

    def test_model_dump_includes_groups(self) -> None:
        meta = FactionMetadata(
            structure=FactionStructure(leadership="Queen"),
        )
        dumped = meta.model_dump()
        assert dumped["structure"] is not None
        assert dumped["structure"]["leadership"] == "Queen"
