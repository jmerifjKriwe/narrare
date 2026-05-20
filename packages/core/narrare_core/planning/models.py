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


@dataclass(frozen=True, slots=True)
class ChapterOutlineData:
    """Snapshot of a single chapter's outline data for sync checking."""

    chapter_id: UUID
    stage_assignment: str  # kebab-case stage ID (empty string if unassigned)
    planned_beats: list[BeatDef]  # beats the outline committed to
    outline_notes: str
    has_content: bool  # whether the chapter has actual written content
    word_count: int


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
    "StageAssignment",
    "StoryboardView",
    "SyncStatus",
]
