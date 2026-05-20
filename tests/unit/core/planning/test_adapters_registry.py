"""Unit tests for planning adapter registry and cross-adapter edge cases."""

from __future__ import annotations

import pytest

from narrare_core.planning.adapters import registry
from narrare_core.planning.adapters.base import (
    BeatDef,
    StageDef,
    StructureAdapter,
    StructureAdapterRegistry,
)
from narrare_core.planning.adapters.three_act import ThreeActAdapter

# =====================================================================
# Registry
# =====================================================================


class TestRegistry:
    """Tests for StructureAdapterRegistry."""

    def test_all_five_registered(self) -> None:
        assert len(registry) == 5
        assert "three_act" in registry
        assert "five_act" in registry
        assert "heros_journey" in registry
        assert "save_the_cat" in registry
        assert "seven_point" in registry

    def test_available_types_sorted(self) -> None:
        types = registry.available_types
        assert types == sorted(types)

    def test_get_known_type(self) -> None:
        adapter = registry.get("three_act")
        assert adapter.structure_type == "three_act"

    def test_get_unknown_type_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown structure type"):
            registry.get("nonexistent")

    def test_get_unknown_type_lists_available(self) -> None:
        with pytest.raises(ValueError, match="five_act") as exc_info:
            registry.get("bogus")
        assert "Available:" in str(exc_info.value)

    def test_contains(self) -> None:
        assert "three_act" in registry
        assert "nonexistent" not in registry

    def test_fresh_registry(self) -> None:
        """A new registry starts empty."""
        fresh = StructureAdapterRegistry()
        assert len(fresh) == 0
        assert fresh.available_types == []

    def test_register_and_get(self) -> None:
        fresh = StructureAdapterRegistry()
        adapter = ThreeActAdapter()
        fresh.register(adapter)
        assert "three_act" in fresh
        assert fresh.get("three_act") is adapter

    def test_register_replaces(self) -> None:
        fresh = StructureAdapterRegistry()
        a1 = ThreeActAdapter()
        a2 = ThreeActAdapter()
        fresh.register(a1)
        fresh.register(a2)
        assert fresh.get("three_act") is a2

    def test_adapter_satisfies_protocol(self) -> None:
        """All adapters satisfy the StructureAdapter protocol."""
        for stype in registry.available_types:
            adapter = registry.get(stype)
            assert isinstance(adapter, StructureAdapter)


# =====================================================================
# Edge Cases — cross-adapter
# =====================================================================


class TestEdgeCases:
    """Edge cases that apply across adapters."""

    @pytest.mark.parametrize(
        "adapter_name",
        ["three_act", "five_act", "heros_journey", "save_the_cat", "seven_point"],
    )
    def test_suggest_stage_single_chapter(self, adapter_name: str) -> None:
        adapter = registry.get(adapter_name)
        # Should return a valid stage ID
        result = adapter.suggest_stage(1, 1)
        assert result in {s.id for s in adapter.stages}

    @pytest.mark.parametrize(
        "adapter_name",
        ["three_act", "five_act", "heros_journey", "save_the_cat", "seven_point"],
    )
    def test_suggest_stage_first_chapter(self, adapter_name: str) -> None:
        adapter = registry.get(adapter_name)
        result = adapter.suggest_stage(1, 100)
        # First chapter should be in the first stage or near it
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.parametrize(
        "adapter_name",
        ["three_act", "five_act", "heros_journey", "save_the_cat", "seven_point"],
    )
    def test_suggest_stage_last_chapter(self, adapter_name: str) -> None:
        adapter = registry.get(adapter_name)
        result = adapter.suggest_stage(100, 100)
        # Last chapter should be in the last stage
        last_stage_id = adapter.stages[-1].id
        assert result == last_stage_id

    @pytest.mark.parametrize(
        "adapter_name",
        ["three_act", "five_act", "heros_journey", "save_the_cat", "seven_point"],
    )
    def test_fewer_chapters_than_stages(self, adapter_name: str) -> None:
        adapter = registry.get(adapter_name)
        # Only 2 chapters for potentially many stages
        s1 = adapter.suggest_stage(1, 2)
        s2 = adapter.suggest_stage(2, 2)
        assert s1 != s2 or len(adapter.stages) <= 1

    @pytest.mark.parametrize(
        "adapter_name",
        ["three_act", "five_act", "heros_journey", "save_the_cat", "seven_point"],
    )
    def test_stage_def_fields(self, adapter_name: str) -> None:
        adapter = registry.get(adapter_name)
        for stage in adapter.stages:
            assert isinstance(stage, StageDef)
            assert len(stage.id) > 0
            assert len(stage.name) > 0
            assert len(stage.description) > 0
            assert stage.position >= 1
            assert stage.expected_beat_count >= 1

    @pytest.mark.parametrize(
        "adapter_name",
        ["three_act", "five_act", "heros_journey", "save_the_cat", "seven_point"],
    )
    def test_beat_def_fields(self, adapter_name: str) -> None:
        adapter = registry.get(adapter_name)
        for stage in adapter.stages:
            for beat in adapter.get_beat_expectations(stage.id):
                assert isinstance(beat, BeatDef)
                assert len(beat.title) > 0
                assert len(beat.description) > 0
                assert isinstance(beat.required, bool)
