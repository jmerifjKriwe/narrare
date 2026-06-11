"""Unit tests for planning/adapters/base.py — BeatDef, StageDef, and registry dataclass behavior.

These tests focus on the dataclass semantics (creation, defaults, immutability,
equality) that are not covered by the adapter-level tests in test_adapters.py
and test_adapters_registry.py.
"""

from __future__ import annotations

from typing import Any, cast

import pytest

from narrare_core.planning.adapters.base import (
    BeatDef,
    StageDef,
    StructureAdapter,
    StructureAdapterRegistry,
)
from narrare_core.planning.adapters.three_act import ThreeActAdapter

# =====================================================================
# BeatDef — dataclass behavior
# =====================================================================


class TestBeatDefCreation:
    """Test BeatDef creation and field access."""

    def test_creation_with_all_fields(self) -> None:
        beat = BeatDef(title="Opening", description="The world as it was", required=True)
        assert beat.title == "Opening"
        assert beat.description == "The world as it was"
        assert beat.required is True

    def test_creation_with_defaults(self) -> None:
        beat = BeatDef(title="Twist", description="A surprising turn")
        assert beat.required is True  # default is True

    def test_creation_required_false(self) -> None:
        beat = BeatDef(title="Optional beat", description="Nice to have", required=False)
        assert beat.required is False

    def test_field_access_via_getattr(self) -> None:
        beat = BeatDef(title="Climax", description="The peak moment")
        assert beat.title == "Climax"
        assert beat.description == "The peak moment"
        assert beat.required is True


class TestBeatDefEquality:
    """Test BeatDef equality and inequality (frozen dataclass)."""

    def test_equal_instances(self) -> None:
        a = BeatDef(title="Opening", description="Status quo", required=True)
        b = BeatDef(title="Opening", description="Status quo", required=True)
        assert a == b

    def test_unequal_title(self) -> None:
        a = BeatDef(title="Opening", description="Status quo")
        b = BeatDef(title="Climax", description="Status quo")
        assert a != b

    def test_unequal_description(self) -> None:
        a = BeatDef(title="Opening", description="Status quo")
        b = BeatDef(title="Opening", description="Different")
        assert a != b

    def test_unequal_required(self) -> None:
        a = BeatDef(title="Opening", description="Status quo", required=True)
        b = BeatDef(title="Opening", description="Status quo", required=False)
        assert a != b

    def test_hash_equal_instances(self) -> None:
        """Frozen dataclasses are hashable; equal instances have equal hashes."""
        a = BeatDef(title="Opening", description="Status quo")
        b = BeatDef(title="Opening", description="Status quo")
        assert hash(a) == hash(b)

    def test_hash_unequal_instances(self) -> None:
        a = BeatDef(title="Opening", description="Status quo")
        b = BeatDef(title="Climax", description="Peak moment")
        assert hash(a) != hash(b)

    def test_usable_in_set(self) -> None:
        """Frozen dataclasses can be used in sets."""
        a = BeatDef(title="Opening", description="Status quo")
        b = BeatDef(title="Opening", description="Status quo")
        c = BeatDef(title="Climax", description="Peak moment")
        assert len({a, b, c}) == 2

    def test_usable_as_dict_key(self) -> None:
        """Frozen dataclasses can be used as dict keys."""
        beat = BeatDef(title="Opening", description="Status quo")
        mapping = {beat: "act-1"}
        assert mapping[beat] == "act-1"


class TestBeatDefImmutability:
    """Test that BeatDef is frozen (immutable)."""

    def test_cannot_set_attribute(self) -> None:
        beat = BeatDef(title="Opening", description="Status quo")
        with pytest.raises(AttributeError):
            cast("Any", beat).title = "Changed"

    def test_cannot_set_required(self) -> None:
        beat = BeatDef(title="Opening", description="Status quo")
        with pytest.raises(AttributeError):
            cast("Any", beat).required = False

    def test_cannot_add_attribute(self) -> None:
        """Slots=True prevents adding new attributes."""
        beat = BeatDef(title="Opening", description="Status quo")
        with pytest.raises((AttributeError, TypeError)):
            cast("Any", beat).extra = "unexpected"

    def test_has_no_dict_attribute(self) -> None:
        """Slots=True means no __dict__ — memory-efficient and prevents dynamic attrs."""
        beat = BeatDef(title="Opening", description="Status quo")
        assert not hasattr(beat, "__dict__")


class TestBeatDefRepr:
    """Test BeatDef string representation."""

    def test_repr_contains_class_name(self) -> None:
        beat = BeatDef(title="Opening", description="Status quo")
        assert "BeatDef" in repr(beat)

    def test_str_contains_title(self) -> None:
        beat = BeatDef(title="Opening", description="Status quo")
        assert "Opening" in str(beat)


# =====================================================================
# StageDef — dataclass behavior
# =====================================================================


class TestStageDefCreation:
    """Test StageDef creation and field access."""

    def test_creation_with_all_fields(self) -> None:
        stage = StageDef(
            id="act-1",
            name="Act I: Setup",
            description="The beginning",
            position=1,
            expected_beat_count=3,
        )
        assert stage.id == "act-1"
        assert stage.name == "Act I: Setup"
        assert stage.description == "The beginning"
        assert stage.position == 1
        assert stage.expected_beat_count == 3

    def test_field_access_via_getattr(self) -> None:
        stage = StageDef(
            id="act-2",
            name="Act II",
            description="Confrontation",
            position=2,
            expected_beat_count=4,
        )
        assert stage.id == "act-2"
        assert stage.position == 2


class TestStageDefEquality:
    """Test StageDef equality and inequality."""

    def test_equal_instances(self) -> None:
        a = StageDef(
            id="act-1", name="Act I", description="Setup", position=1, expected_beat_count=3
        )
        b = StageDef(
            id="act-1", name="Act I", description="Setup", position=1, expected_beat_count=3
        )
        assert a == b

    def test_unequal_id(self) -> None:
        a = StageDef(
            id="act-1", name="Act I", description="Setup", position=1, expected_beat_count=3
        )
        b = StageDef(
            id="act-2", name="Act I", description="Setup", position=1, expected_beat_count=3
        )
        assert a != b

    def test_unequal_position(self) -> None:
        a = StageDef(
            id="act-1", name="Act I", description="Setup", position=1, expected_beat_count=3
        )
        b = StageDef(
            id="act-1", name="Act I", description="Setup", position=2, expected_beat_count=3
        )
        assert a != b

    def test_hash_equal_instances(self) -> None:
        a = StageDef(
            id="act-1", name="Act I", description="Setup", position=1, expected_beat_count=3
        )
        b = StageDef(
            id="act-1", name="Act I", description="Setup", position=1, expected_beat_count=3
        )
        assert hash(a) == hash(b)

    def test_usable_in_set(self) -> None:
        a = StageDef(
            id="act-1", name="Act I", description="Setup", position=1, expected_beat_count=3
        )
        b = StageDef(
            id="act-1", name="Act I", description="Setup", position=1, expected_beat_count=3
        )
        c = StageDef(
            id="act-2",
            name="Act II",
            description="Confrontation",
            position=2,
            expected_beat_count=4,
        )
        assert len({a, b, c}) == 2


class TestStageDefImmutability:
    """Test that StageDef is frozen (immutable)."""

    def test_cannot_set_id(self) -> None:
        stage = StageDef(
            id="act-1", name="Act I", description="Setup", position=1, expected_beat_count=3
        )
        with pytest.raises(AttributeError):
            cast("Any", stage).id = "changed"

    def test_cannot_set_position(self) -> None:
        stage = StageDef(
            id="act-1", name="Act I", description="Setup", position=1, expected_beat_count=3
        )
        with pytest.raises(AttributeError):
            cast("Any", stage).position = 99

    def test_cannot_add_attribute(self) -> None:
        """Slots=True prevents adding new attributes."""
        stage = StageDef(
            id="act-1", name="Act I", description="Setup", position=1, expected_beat_count=3
        )
        with pytest.raises((AttributeError, TypeError)):
            cast("Any", stage).extra = "unexpected"

    def test_has_no_dict_attribute(self) -> None:
        """Slots=True means no __dict__ — memory-efficient and prevents dynamic attrs."""
        stage = StageDef(
            id="act-1", name="Act I", description="Setup", position=1, expected_beat_count=3
        )
        assert not hasattr(stage, "__dict__")


# =====================================================================
# StructureAdapter Protocol — runtime checkable
# =====================================================================


class TestStructureAdapterProtocol:
    """Test that StructureAdapter is a runtime-checkable protocol."""

    def test_adapter_satisfies_protocol(self) -> None:
        adapter = ThreeActAdapter()
        assert isinstance(adapter, StructureAdapter)

    def test_plain_object_does_not_satisfy_protocol(self) -> None:
        """A plain object without the required methods is not a StructureAdapter."""

        class NotAnAdapter:
            pass

        assert not isinstance(NotAnAdapter(), StructureAdapter)

    def test_partial_implementation_does_not_satisfy(self) -> None:
        """An object missing required methods is not a StructureAdapter."""

        class PartialAdapter:
            structure_type = "partial"

        # Missing: stages, suggest_stage, validate_assignment, get_beat_expectations
        assert not isinstance(PartialAdapter(), StructureAdapter)


# =====================================================================
# StructureAdapterRegistry — additional dataclass/registry behavior
# =====================================================================


class TestStructureAdapterRegistryDataclass:
    """Test registry behavior beyond what test_adapters_registry.py covers."""

    def test_get_error_message_lists_available_types(self) -> None:
        """ValueError message includes available types when key not found."""
        fresh = StructureAdapterRegistry()
        fresh.register(ThreeActAdapter())
        with pytest.raises(ValueError, match="three_act") as exc_info:
            fresh.get("nonexistent")
        msg = str(exc_info.value)
        assert "Available:" in msg
        assert "three_act" in msg

    def test_get_error_message_shows_none_when_empty(self) -> None:
        """ValueError message shows '(none)' when registry is empty."""
        fresh = StructureAdapterRegistry()
        with pytest.raises(ValueError, match=r"\(none\)"):
            fresh.get("anything")

    def test_len_increases_on_register(self) -> None:
        fresh = StructureAdapterRegistry()
        assert len(fresh) == 0
        fresh.register(ThreeActAdapter())
        assert len(fresh) == 1

    def test_available_types_returns_sorted(self) -> None:
        fresh = StructureAdapterRegistry()
        fresh.register(ThreeActAdapter())
        # Only one type, but verify it's a sorted list
        assert fresh.available_types == ["three_act"]

    def test_contains_returns_false_for_missing(self) -> None:
        fresh = StructureAdapterRegistry()
        assert "nonexistent" not in fresh

    def test_register_same_type_replaces(self) -> None:
        """Re-registering the same type key replaces the adapter."""
        fresh = StructureAdapterRegistry()
        a1 = ThreeActAdapter()
        a2 = ThreeActAdapter()
        fresh.register(a1)
        fresh.register(a2)
        assert fresh.get("three_act") is a2
        assert len(fresh) == 1  # Still only one entry
