"""Unit tests for StructuralSyncChecker — all 5 status levels."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from narrare_core.planning.adapters.base import BeatDef
from narrare_core.planning.models import (
    ChapterOutlineData,
    ScenePlanData,
    SceneStatus,
    SyncStatus,
)
from narrare_core.planning.sync import StructuralSyncChecker

# =====================================================================
# Fixtures
# =====================================================================


@pytest.fixture
def checker() -> StructuralSyncChecker:
    return StructuralSyncChecker()


def _make_outline(
    *,
    stage_assignment: str = "",
    planned_beats: list[BeatDef] | None = None,
    outline_notes: str = "",
    has_content: bool = False,
    word_count: int = 0,
    has_summary: bool = False,
    chapter_id: UUID | None = None,
) -> ChapterOutlineData:
    """Helper to create ChapterOutlineData with sensible defaults."""
    return ChapterOutlineData(
        chapter_id=chapter_id or uuid4(),
        stage_assignment=stage_assignment,
        planned_beats=planned_beats or [],
        outline_notes=outline_notes,
        has_content=has_content,
        word_count=word_count,
        has_summary=has_summary,
    )


# =====================================================================
# Status: EMPTY
# =====================================================================


class TestEmptyStatus:
    """Rule 1: no stage assignment AND no content → EMPTY."""

    def test_no_stage_no_content(self, checker: StructuralSyncChecker) -> None:
        outline = _make_outline(stage_assignment="", has_content=False)
        assert checker.calculate_sync_status(outline, "act-1") == SyncStatus.EMPTY

    def test_no_stage_no_content_with_beats(self, checker: StructuralSyncChecker) -> None:
        """Even with planned beats, no stage + no content = EMPTY."""
        outline = _make_outline(
            stage_assignment="",
            has_content=False,
            planned_beats=[BeatDef("Test", "A beat", True)],
        )
        assert checker.calculate_sync_status(outline, "act-1") == SyncStatus.EMPTY

    def test_no_stage_no_content_with_notes(self, checker: StructuralSyncChecker) -> None:
        outline = _make_outline(
            stage_assignment="",
            has_content=False,
            outline_notes="Some planning notes",
        )
        assert checker.calculate_sync_status(outline, "act-1") == SyncStatus.EMPTY


# =====================================================================
# Status: PLANNED
# =====================================================================


class TestPlannedStatus:
    """Rule 2: has stage assignment but no content → PLANNED."""

    def test_has_stage_no_content(self, checker: StructuralSyncChecker) -> None:
        outline = _make_outline(
            stage_assignment="act-1",
            has_content=False,
        )
        assert checker.calculate_sync_status(outline, "act-1") == SyncStatus.PLANNED

    def test_has_stage_no_content_with_beats(self, checker: StructuralSyncChecker) -> None:
        outline = _make_outline(
            stage_assignment="act-2",
            has_content=False,
            planned_beats=[BeatDef("Midpoint", "The midpoint twist", True)],
        )
        assert checker.calculate_sync_status(outline, "act-2") == SyncStatus.PLANNED

    def test_has_stage_no_content_with_notes(self, checker: StructuralSyncChecker) -> None:
        outline = _make_outline(
            stage_assignment="act-1",
            has_content=False,
            outline_notes="Detailed outline notes",
        )
        assert checker.calculate_sync_status(outline, "act-1") == SyncStatus.PLANNED


# =====================================================================
# Status: DEVIATED
# =====================================================================


class TestDeviatedStatus:
    """Rule 3: stage assignment differs from suggested stage → DEVIATED."""

    def test_stage_mismatch(self, checker: StructuralSyncChecker) -> None:
        outline = _make_outline(
            stage_assignment="act-1",
            has_content=True,
            word_count=500,
        )
        assert checker.calculate_sync_status(outline, "act-2") == SyncStatus.DEVIATED

    def test_stage_mismatch_different_structures(self, checker: StructuralSyncChecker) -> None:
        outline = _make_outline(
            stage_assignment="exposition",
            has_content=True,
            word_count=1000,
        )
        assert checker.calculate_sync_status(outline, "rising-action") == SyncStatus.DEVIATED

    def test_empty_assignment_vs_suggested(self, checker: StructuralSyncChecker) -> None:
        """Empty assignment + has content is NOT empty (rule 1 doesn't match)
        → PLANNED? No — has_content=True, so rule 2 doesn't match either.
        But empty != suggested → DEVIATED."""
        outline = _make_outline(
            stage_assignment="",
            has_content=True,
            word_count=500,
        )
        # Not EMPTY (has_content=True), not PLANNED (has_content=True)
        # Empty stage != suggested → DEVIATED
        assert checker.calculate_sync_status(outline, "act-1") == SyncStatus.DEVIATED


# =====================================================================
# Status: COMPLETED
# =====================================================================


class TestCompletedStatus:
    """Rule 3b + 4: summary+content → COMPLETED, or required beats with content → COMPLETED."""

    def test_all_required_beats_with_content(self, checker: StructuralSyncChecker) -> None:
        outline = _make_outline(
            stage_assignment="act-1",
            has_content=True,
            word_count=2000,
            planned_beats=[
                BeatDef("Opening", "The opening scene", True),
                BeatDef("Inciting Incident", "The catalyst", True),
            ],
        )
        assert checker.calculate_sync_status(outline, "act-1") == SyncStatus.COMPLETED

    def test_required_and_optional_beats_with_content(self, checker: StructuralSyncChecker) -> None:
        outline = _make_outline(
            stage_assignment="act-1",
            has_content=True,
            word_count=3000,
            planned_beats=[
                BeatDef("Required Beat", "Must have", True),
                BeatDef("Optional Beat", "Nice to have", False),
            ],
        )
        assert checker.calculate_sync_status(outline, "act-1") == SyncStatus.COMPLETED

    def test_summary_and_content_returns_completed(self, checker: StructuralSyncChecker) -> None:
        """Rule 3b: has_summary + has_content → COMPLETED (stronger signal)."""
        outline = _make_outline(
            stage_assignment="act-1",
            has_content=True,
            word_count=500,
            has_summary=True,
        )
        assert checker.calculate_sync_status(outline, "act-1") == SyncStatus.COMPLETED

    def test_summary_without_content_does_not_return_completed(
        self, checker: StructuralSyncChecker
    ) -> None:
        """Summary without content → ON_TRACK (not rule 3b, not rule 4)."""
        outline = _make_outline(
            stage_assignment="act-1",
            has_content=False,
            word_count=0,
            has_summary=True,
        )
        # Summary exists but no content: rule 2 (has stage, no content) → PLANNED
        assert checker.calculate_sync_status(outline, "act-1") == SyncStatus.PLANNED

    def test_content_without_summary_falls_through(self, checker: StructuralSyncChecker) -> None:
        """Content without summary → falls through to rule 4."""
        outline = _make_outline(
            stage_assignment="act-1",
            has_content=True,
            word_count=2000,
            has_summary=False,
            planned_beats=[BeatDef("Required", "desc", True)],
        )
        assert checker.calculate_sync_status(outline, "act-1") == SyncStatus.COMPLETED


# =====================================================================
# Status: ON_TRACK
# =====================================================================


class TestOnTrackStatus:
    """Rule 5: aligned but still in progress → ON_TRACK."""

    def test_stage_matches_no_beats_in_progress(self, checker: StructuralSyncChecker) -> None:
        outline = _make_outline(
            stage_assignment="act-1",
            has_content=True,
            word_count=500,
            planned_beats=[],
        )
        assert checker.calculate_sync_status(outline, "act-1") == SyncStatus.ON_TRACK

    def test_stage_matches_optional_beats_only(self, checker: StructuralSyncChecker) -> None:
        """Only optional beats (no required) → ON_TRACK (rule 4 doesn't match)."""
        outline = _make_outline(
            stage_assignment="act-1",
            has_content=True,
            word_count=500,
            planned_beats=[
                BeatDef("Optional", "Nice to have", False),
            ],
        )
        assert checker.calculate_sync_status(outline, "act-1") == SyncStatus.ON_TRACK


# =====================================================================
# Edge Cases
# =====================================================================


class TestSyncEdgeCases:
    """Edge cases and boundary conditions."""

    def test_zero_word_count_with_content(self, checker: StructuralSyncChecker) -> None:
        """has_content=True but word_count=0 is unusual but valid."""
        outline = _make_outline(
            stage_assignment="act-1",
            has_content=True,
            word_count=0,
            planned_beats=[BeatDef("Beat", "desc", True)],
        )
        # Stage matches, but word_count=0 → rule 4 won't match → ON_TRACK
        assert checker.calculate_sync_status(outline, "act-1") == SyncStatus.ON_TRACK

    def test_empty_beats_list_with_content(self, checker: StructuralSyncChecker) -> None:
        outline = _make_outline(
            stage_assignment="act-1",
            has_content=True,
            word_count=5000,
            planned_beats=[],
        )
        # No required beats → rule 4 doesn't match → ON_TRACK
        assert checker.calculate_sync_status(outline, "act-1") == SyncStatus.ON_TRACK

    def test_many_beats_all_required(self, checker: StructuralSyncChecker) -> None:
        outline = _make_outline(
            stage_assignment="act-1",
            has_content=True,
            word_count=10000,
            planned_beats=[BeatDef(f"Beat {i}", f"Description {i}", True) for i in range(5)],
        )
        assert checker.calculate_sync_status(outline, "act-1") == SyncStatus.COMPLETED

    def test_sync_status_enum_values(self) -> None:
        """Verify SyncStatus enum has all expected values."""
        assert SyncStatus.EMPTY == "empty"
        assert SyncStatus.PLANNED == "planned"
        assert SyncStatus.ON_TRACK == "on_track"
        assert SyncStatus.DEVIATED == "deviated"
        assert SyncStatus.COMPLETED == "completed"

    def test_all_status_values_reachable(self, checker: StructuralSyncChecker) -> None:
        """Ensure all 5 status values can be produced."""
        statuses: set[SyncStatus] = set()

        # EMPTY
        o1 = _make_outline(stage_assignment="", has_content=False)
        statuses.add(checker.calculate_sync_status(o1, "act-1"))

        # PLANNED
        o2 = _make_outline(stage_assignment="act-1", has_content=False)
        statuses.add(checker.calculate_sync_status(o2, "act-1"))

        # DEVIATED
        o3 = _make_outline(stage_assignment="act-1", has_content=True, word_count=100)
        statuses.add(checker.calculate_sync_status(o3, "act-2"))

        # COMPLETED (via beats)
        o4 = _make_outline(
            stage_assignment="act-1",
            has_content=True,
            word_count=2000,
            planned_beats=[BeatDef("Beat", "desc", True)],
        )
        statuses.add(checker.calculate_sync_status(o4, "act-1"))

        # COMPLETED (via summary)
        o4b = _make_outline(
            stage_assignment="act-1",
            has_content=True,
            word_count=500,
            has_summary=True,
        )
        statuses.add(checker.calculate_sync_status(o4b, "act-1"))

        # ON_TRACK
        o5 = _make_outline(stage_assignment="act-1", has_content=True, word_count=500)
        statuses.add(checker.calculate_sync_status(o5, "act-1"))

        assert statuses == {
            SyncStatus.EMPTY,
            SyncStatus.PLANNED,
            SyncStatus.ON_TRACK,
            SyncStatus.DEVIATED,
            SyncStatus.COMPLETED,
        }


# =====================================================================
# Scene-driven sync dispatch (PLAN-001, ADR-096)
# =====================================================================


def check(outline: ChapterOutlineData, suggested_stage: str) -> SyncStatus:
    """Thin helper so scene-era tests read like the plan's sketches."""
    return StructuralSyncChecker().calculate_sync_status(outline, suggested_stage)


def _scene(status: SceneStatus, cid: UUID | None = None) -> ScenePlanData:
    return ScenePlanData(id=cid or uuid4(), position=1, title="S", status=status)


def _outline(
    *,
    stage: str = "act-1",
    has_content: bool = False,
    word_count: int = 0,
    scenes: tuple[ScenePlanData, ...] = (),
    beats: tuple[BeatDef, ...] = (),
) -> ChapterOutlineData:
    """Scene-era outline helper — `_make_outline` extended with scene kwargs."""
    return ChapterOutlineData(
        chapter_id=uuid4(),
        stage_assignment=stage,
        planned_beats=list(beats),
        outline_notes="",
        has_content=has_content,
        word_count=word_count,
        scenes=scenes,
    )


class TestSceneDrivenSync:
    """Shape dispatch: scenes present ⇒ scene rules, else legacy beat rule."""

    def test_all_complete_scenes_with_content_is_completed(self) -> None:
        outline = _outline(has_content=True, scenes=(_scene(SceneStatus.COMPLETE),))
        assert check(outline, "act-1") is SyncStatus.COMPLETED

    def test_partial_scenes_is_on_track(self) -> None:
        outline = _outline(
            has_content=True,
            scenes=(_scene(SceneStatus.COMPLETE), _scene(SceneStatus.IN_PROGRESS)),
        )
        assert check(outline, "act-1") is SyncStatus.ON_TRACK

    def test_all_planned_scenes_with_content_falls_back_on_track(self) -> None:
        outline = _outline(has_content=True, scenes=(_scene(SceneStatus.PLANNED),))
        assert check(outline, "act-1") is SyncStatus.ON_TRACK

    def test_all_complete_scenes_without_content_is_not_completed(self) -> None:
        # no content → rule 2 PLANNED fires before scene rules
        outline = _outline(has_content=False, scenes=(_scene(SceneStatus.COMPLETE),), stage="act-1")
        assert check(outline, "act-1") is SyncStatus.PLANNED

    def test_no_scenes_legacy_path_unchanged(self) -> None:
        # beats path still applies while planned_beats exists (transition)
        outline = _outline(has_content=True, word_count=500, beats=(BeatDef("b", "d", True),))
        assert check(outline, "act-1") is SyncStatus.COMPLETED
