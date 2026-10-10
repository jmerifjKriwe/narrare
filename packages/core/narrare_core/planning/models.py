"""Planning domain models — data structures for the storyboard feature.

Pure dataclasses and enums. No I/O, no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from narrare_core.planning.adapters.base import StageDef


class SyncStatus(StrEnum):
    """Sync status between a chapter's outline and its structural position."""

    EMPTY = "empty"
    PLANNED = "planned"
    ON_TRACK = "on_track"
    DEVIATED = "deviated"
    COMPLETED = "completed"


class SceneStatus(StrEnum):
    """Workflow status of a single planned scene (ADR-096 scene substrate)."""

    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"


@dataclass(frozen=True, slots=True)
class ScenePresence:
    """One ``present_characters`` entry, name-resolved at the API boundary."""

    name: str
    goal: str = ""


@dataclass(frozen=True, slots=True)
class ScenePlanData:
    """Snapshot of a single planned scene for sync checking and rendering.

    Names (POV/location/presences) are plain strings on purpose: hybrid KB
    refs exist so display survives KB deletion — sync and rendering need
    names, not KB linkage, and resolving them at the API boundary keeps
    Core free of JSONB ref semantics (spec §3.2).
    """

    id: UUID
    position: int
    title: str
    pov_character_name: str = ""  # resolved from hybrid ref at the API boundary
    location_name: str = ""
    present_characters: tuple[ScenePresence, ...] = ()
    purpose: str = ""
    conflict: str = ""
    resolution: str = ""
    beats: tuple[str, ...] = ()
    status: SceneStatus = SceneStatus.PLANNED


@dataclass(frozen=True, slots=True)
class ChapterOutlineData:
    """Snapshot of a single chapter's outline data for sync checking.

    Final shape (PLAN-001 / ADR-096): scene-based only — the legacy
    stored-beats field is gone and a chapter's planned work lives in
    ``scenes``; structure-template beats remain a separate adapter
    concept (:class:`~narrare_core.planning.adapters.base.BeatDef`,
    PLAN-003).
    """

    chapter_id: UUID
    stage_assignment: str  # kebab-case stage ID (empty string if unassigned)
    outline_notes: str
    has_content: bool  # whether the chapter has actual written content
    word_count: int
    has_summary: bool = False  # whether the chapter has been summarized
    # Scene substrate (ADR-096): the chapter's planned scenes, ordered by
    # position; drives the scene-based sync rules (empty tuple ⇒ none).
    scenes: tuple[ScenePlanData, ...] = ()


@dataclass(frozen=True, slots=True)
class StageAssignment:
    """A stage with all chapters currently assigned to it."""

    stage_id: str
    chapters: list[ChapterOutlineData]


@dataclass(frozen=True, slots=True)
class StoryboardView:
    """Complete storyboard view for a novel's current structure."""

    structure_type: str
    stages: list[StageDef]
    assignments: list[StageAssignment]


__all__ = [
    "ChapterOutlineData",
    "ScenePlanData",
    "ScenePresence",
    "SceneStatus",
    "StageAssignment",
    "StoryboardView",
    "SyncStatus",
]
