"""Planning domain models — data structures for the storyboard feature.

Pure dataclasses and enums. No I/O, no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from narrare_core.planning.adapters.base import BeatDef, StageDef


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
    """Snapshot of a single chapter's outline data for sync checking."""

    chapter_id: UUID
    stage_assignment: str  # kebab-case stage ID (empty string if unassigned)
    planned_beats: list[BeatDef]  # beats the outline committed to
    outline_notes: str
    has_content: bool  # whether the chapter has actual written content
    word_count: int
    has_summary: bool = False  # whether the chapter has been summarized
    # Scene substrate (ADR-096): appended after existing fields with a default
    # so pre-scene constructors stay valid; empty tuple ⇒ legacy beat path.
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
