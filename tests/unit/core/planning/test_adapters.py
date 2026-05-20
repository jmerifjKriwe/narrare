"""Unit tests for planning adapters — all 5 structures."""

from __future__ import annotations

import pytest

from narrare_core.planning.adapters.five_act import FiveActAdapter
from narrare_core.planning.adapters.heros_journey import HerosJourneyAdapter
from narrare_core.planning.adapters.save_the_cat import SaveTheCatAdapter
from narrare_core.planning.adapters.seven_point import SevenPointAdapter
from narrare_core.planning.adapters.three_act import ThreeActAdapter

# =====================================================================
# Fixtures
# =====================================================================


@pytest.fixture
def three_act() -> ThreeActAdapter:
    return ThreeActAdapter()


@pytest.fixture
def five_act() -> FiveActAdapter:
    return FiveActAdapter()


@pytest.fixture
def heros_journey() -> HerosJourneyAdapter:
    return HerosJourneyAdapter()


@pytest.fixture
def save_the_cat() -> SaveTheCatAdapter:
    return SaveTheCatAdapter()


@pytest.fixture
def seven_point() -> SevenPointAdapter:
    return SevenPointAdapter()


# =====================================================================
# Three-Act Adapter
# =====================================================================


class TestThreeActAdapter:
    """Tests for the Three-Act Structure adapter."""

    def test_structure_type(self, three_act: ThreeActAdapter) -> None:
        assert three_act.structure_type == "three_act"

    def test_stages_count(self, three_act: ThreeActAdapter) -> None:
        assert len(three_act.stages) == 3

    def test_stage_ids(self, three_act: ThreeActAdapter) -> None:
        ids = [s.id for s in three_act.stages]
        assert ids == ["act-1", "act-2", "act-3"]

    def test_stage_positions_ordered(self, three_act: ThreeActAdapter) -> None:
        positions = [s.position for s in three_act.stages]
        assert positions == [1, 2, 3]

    def test_suggest_stage_act1(self, three_act: ThreeActAdapter) -> None:
        # chapters 1-33% → act-1
        assert three_act.suggest_stage(1, 10) == "act-1"
        assert three_act.suggest_stage(3, 10) == "act-1"

    def test_suggest_stage_act2(self, three_act: ThreeActAdapter) -> None:
        # chapters 34-66% → act-2
        assert three_act.suggest_stage(4, 10) == "act-2"
        assert three_act.suggest_stage(6, 10) == "act-2"

    def test_suggest_stage_act3(self, three_act: ThreeActAdapter) -> None:
        # chapters 67-100% → act-3
        assert three_act.suggest_stage(7, 10) == "act-3"
        assert three_act.suggest_stage(10, 10) == "act-3"

    def test_suggest_stage_zero_chapters(self, three_act: ThreeActAdapter) -> None:
        assert three_act.suggest_stage(1, 0) == "act-1"

    def test_suggest_stage_single_chapter(self, three_act: ThreeActAdapter) -> None:
        # 1/1 = 100% → act-3
        assert three_act.suggest_stage(1, 1) == "act-3"

    def test_validate_assignment_valid(self, three_act: ThreeActAdapter) -> None:
        assert three_act.validate_assignment("act-1", 1) is True
        assert three_act.validate_assignment("act-2", 5) is True
        assert three_act.validate_assignment("act-3", 10) is True

    def test_validate_assignment_invalid(self, three_act: ThreeActAdapter) -> None:
        assert three_act.validate_assignment("nonexistent", 1) is False
        assert three_act.validate_assignment("exposition", 1) is False

    def test_beat_expectations_act1(self, three_act: ThreeActAdapter) -> None:
        beats = three_act.get_beat_expectations("act-1")
        assert len(beats) == 3
        assert beats[0].title == "Opening / Status Quo"
        assert any(b.required for b in beats)

    def test_beat_expectations_act2(self, three_act: ThreeActAdapter) -> None:
        beats = three_act.get_beat_expectations("act-2")
        assert len(beats) == 4

    def test_beat_expectations_act3(self, three_act: ThreeActAdapter) -> None:
        beats = three_act.get_beat_expectations("act-3")
        assert len(beats) == 2

    def test_beat_expectations_unknown(self, three_act: ThreeActAdapter) -> None:
        assert three_act.get_beat_expectations("unknown") == []


# =====================================================================
# Five-Act Adapter
# =====================================================================


class TestFiveActAdapter:
    """Tests for the Five-Act Structure adapter."""

    def test_structure_type(self, five_act: FiveActAdapter) -> None:
        assert five_act.structure_type == "five_act"

    def test_stages_count(self, five_act: FiveActAdapter) -> None:
        assert len(five_act.stages) == 5

    def test_stage_ids(self, five_act: FiveActAdapter) -> None:
        ids = [s.id for s in five_act.stages]
        assert ids == [
            "exposition",
            "rising-action",
            "climax",
            "falling-action",
            "resolution",
        ]

    def test_suggest_stage_even_distribution(self, five_act: FiveActAdapter) -> None:
        # 5 chapters → 1 each
        assert five_act.suggest_stage(1, 5) == "exposition"
        assert five_act.suggest_stage(3, 5) == "climax"
        assert five_act.suggest_stage(5, 5) == "resolution"

    def test_suggest_stage_zero_chapters(self, five_act: FiveActAdapter) -> None:
        assert five_act.suggest_stage(1, 0) == "exposition"

    def test_suggest_stage_many_chapters(self, five_act: FiveActAdapter) -> None:
        # 20 chapters, first chapter → exposition
        assert five_act.suggest_stage(1, 20) == "exposition"
        # middle → climax
        assert five_act.suggest_stage(10, 20) == "climax"
        # end → resolution
        assert five_act.suggest_stage(20, 20) == "resolution"

    def test_validate_assignment_valid(self, five_act: FiveActAdapter) -> None:
        for stage in five_act.stages:
            assert five_act.validate_assignment(stage.id, 1) is True

    def test_validate_assignment_invalid(self, five_act: FiveActAdapter) -> None:
        assert five_act.validate_assignment("act-1", 1) is False

    def test_beat_expectations_per_stage(self, five_act: FiveActAdapter) -> None:
        total = 0
        for stage in five_act.stages:
            beats = five_act.get_beat_expectations(stage.id)
            assert len(beats) > 0
            total += len(beats)
        assert total >= 10  # at least 2 per stage x 5

    def test_beat_expectations_unknown(self, five_act: FiveActAdapter) -> None:
        assert five_act.get_beat_expectations("unknown") == []


# =====================================================================
# Hero's Journey Adapter
# =====================================================================


class TestHerosJourneyAdapter:
    """Tests for the Hero's Journey adapter."""

    def test_structure_type(self, heros_journey: HerosJourneyAdapter) -> None:
        assert heros_journey.structure_type == "heros_journey"

    def test_stages_count(self, heros_journey: HerosJourneyAdapter) -> None:
        assert len(heros_journey.stages) == 12

    def test_stage_ids(self, heros_journey: HerosJourneyAdapter) -> None:
        ids = [s.id for s in heros_journey.stages]
        assert ids[0] == "ordinary-world"
        assert ids[-1] == "return-with-elixir"

    def test_positions_sequential(self, heros_journey: HerosJourneyAdapter) -> None:
        positions = [s.position for s in heros_journey.stages]
        assert positions == list(range(1, 13))

    def test_suggest_stage_many_chapters(self, heros_journey: HerosJourneyAdapter) -> None:
        # 24 chapters → ratio-based mapping
        assert heros_journey.suggest_stage(1, 24) == "ordinary-world"
        assert heros_journey.suggest_stage(24, 24) == "return-with-elixir"

    def test_suggest_stage_few_chapters_collapsed(self, heros_journey: HerosJourneyAdapter) -> None:
        # 3 chapters → collapsed into beginning/middle/end
        assert heros_journey.suggest_stage(1, 3) == "crossing-threshold"
        assert heros_journey.suggest_stage(2, 3) == "ordeal"
        assert heros_journey.suggest_stage(3, 3) == "return-with-elixir"

    def test_suggest_stage_zero_chapters(self, heros_journey: HerosJourneyAdapter) -> None:
        assert heros_journey.suggest_stage(1, 0) == "ordinary-world"

    def test_validate_assignment_valid(self, heros_journey: HerosJourneyAdapter) -> None:
        assert heros_journey.validate_assignment("ordinary-world", 1) is True
        assert heros_journey.validate_assignment("ordeal", 5) is True

    def test_validate_assignment_invalid(self, heros_journey: HerosJourneyAdapter) -> None:
        assert heros_journey.validate_assignment("act-1", 1) is False

    def test_beat_expectations_per_stage(self, heros_journey: HerosJourneyAdapter) -> None:
        for stage in heros_journey.stages:
            beats = heros_journey.get_beat_expectations(stage.id)
            assert len(beats) >= 1

    def test_beat_expectations_unknown(self, heros_journey: HerosJourneyAdapter) -> None:
        assert heros_journey.get_beat_expectations("unknown") == []

    def test_suggest_stage_single_chapter(self, heros_journey: HerosJourneyAdapter) -> None:
        # 1/1 = 100% → return-with-elixir (last stage)
        result = heros_journey.suggest_stage(1, 1)
        assert result == "return-with-elixir"


# =====================================================================
# Save the Cat! Adapter
# =====================================================================


class TestSaveTheCatAdapter:
    """Tests for the Save the Cat! adapter."""

    def test_structure_type(self, save_the_cat: SaveTheCatAdapter) -> None:
        assert save_the_cat.structure_type == "save_the_cat"

    def test_stages_count(self, save_the_cat: SaveTheCatAdapter) -> None:
        assert len(save_the_cat.stages) == 3

    def test_stage_ids(self, save_the_cat: SaveTheCatAdapter) -> None:
        ids = [s.id for s in save_the_cat.stages]
        assert ids == ["act-1", "act-2", "act-3"]

    def test_beat_count_per_act(self, save_the_cat: SaveTheCatAdapter) -> None:
        # Each act should have 5 beats
        for stage in save_the_cat.stages:
            beats = save_the_cat.get_beat_expectations(stage.id)
            assert len(beats) == 5

    def test_total_beats(self, save_the_cat: SaveTheCatAdapter) -> None:
        total = sum(len(save_the_cat.get_beat_expectations(s.id)) for s in save_the_cat.stages)
        assert total == 15

    def test_suggest_stage_act1(self, save_the_cat: SaveTheCatAdapter) -> None:
        assert save_the_cat.suggest_stage(1, 10) == "act-1"  # 10% → act-1
        assert save_the_cat.suggest_stage(2, 10) == "act-1"  # 20% → act-1

    def test_suggest_stage_act2(self, save_the_cat: SaveTheCatAdapter) -> None:
        assert save_the_cat.suggest_stage(3, 10) == "act-2"  # 30% → act-2
        assert save_the_cat.suggest_stage(7, 10) == "act-2"  # 70% → act-2

    def test_suggest_stage_act3(self, save_the_cat: SaveTheCatAdapter) -> None:
        assert save_the_cat.suggest_stage(8, 10) == "act-3"  # 80% → act-3
        assert save_the_cat.suggest_stage(10, 10) == "act-3"  # 100% → act-3

    def test_suggest_stage_zero_chapters(self, save_the_cat: SaveTheCatAdapter) -> None:
        assert save_the_cat.suggest_stage(1, 0) == "act-1"

    def test_validate_assignment(self, save_the_cat: SaveTheCatAdapter) -> None:
        assert save_the_cat.validate_assignment("act-1", 1) is True
        assert save_the_cat.validate_assignment("act-2", 5) is True
        assert save_the_cat.validate_assignment("act-3", 10) is True
        assert save_the_cat.validate_assignment("exposition", 1) is False

    def test_beat_expectations_unknown(self, save_the_cat: SaveTheCatAdapter) -> None:
        assert save_the_cat.get_beat_expectations("unknown") == []

    def test_beats_have_required_flag(self, save_the_cat: SaveTheCatAdapter) -> None:
        for stage in save_the_cat.stages:
            beats = save_the_cat.get_beat_expectations(stage.id)
            for beat in beats:
                assert isinstance(beat.required, bool)


# =====================================================================
# Seven-Point Adapter
# =====================================================================


class TestSevenPointAdapter:
    """Tests for the Seven-Point adapter."""

    def test_structure_type(self, seven_point: SevenPointAdapter) -> None:
        assert seven_point.structure_type == "seven_point"

    def test_stages_count(self, seven_point: SevenPointAdapter) -> None:
        assert len(seven_point.stages) == 7

    def test_stage_ids(self, seven_point: SevenPointAdapter) -> None:
        ids = [s.id for s in seven_point.stages]
        assert ids == [
            "hook",
            "plot-turn-1",
            "pinch-1",
            "midpoint",
            "pinch-2",
            "plot-turn-2",
            "resolution",
        ]

    def test_positions_sequential(self, seven_point: SevenPointAdapter) -> None:
        positions = [s.position for s in seven_point.stages]
        assert positions == list(range(1, 8))

    def test_suggest_stage_even_distribution(self, seven_point: SevenPointAdapter) -> None:
        # 7 chapters → 1 per stage
        assert seven_point.suggest_stage(1, 7) == "hook"
        assert seven_point.suggest_stage(4, 7) == "midpoint"
        assert seven_point.suggest_stage(7, 7) == "resolution"

    def test_suggest_stage_many_chapters(self, seven_point: SevenPointAdapter) -> None:
        assert seven_point.suggest_stage(1, 21) == "hook"
        assert seven_point.suggest_stage(21, 21) == "resolution"

    def test_suggest_stage_zero_chapters(self, seven_point: SevenPointAdapter) -> None:
        assert seven_point.suggest_stage(1, 0) == "hook"

    def test_validate_assignment(self, seven_point: SevenPointAdapter) -> None:
        for stage in seven_point.stages:
            assert seven_point.validate_assignment(stage.id, 1) is True
        assert seven_point.validate_assignment("act-1", 1) is False

    def test_beat_expectations_per_stage(self, seven_point: SevenPointAdapter) -> None:
        for stage in seven_point.stages:
            beats = seven_point.get_beat_expectations(stage.id)
            assert len(beats) == 1

    def test_beat_expectations_unknown(self, seven_point: SevenPointAdapter) -> None:
        assert seven_point.get_beat_expectations("unknown") == []
