"""Planning service contracts — Protocol definitions (RULE-03: contract first).

Defines interfaces for:
- OutlineRepositoryProtocol: DB queries for chapter outlines
- ScenePlanRepositoryProtocol: DB queries for chapter scene plans (PLAN-001)
- SyncCheckerProtocol: structural sync status calculation
- StoryboardServiceProtocol: business logic for storyboard feature
- CharacterArcServiceProtocol: character arc generation

Timeline-related protocols are in ``timeline_contracts.py`` and re-exported below
to preserve backward compatibility for existing import paths.
"""

from __future__ import annotations

__all__ = [
    "CharacterAgeServiceProtocol",
    "CharacterArcServiceProtocol",
    "OutlineRepositoryProtocol",
    "ScenePlanRepositoryProtocol",
    "StoryboardServiceProtocol",
    "SyncCheckerProtocol",
    "TemporalConsistencyServiceProtocol",
    "TimelineAnalysisServiceProtocol",
    "TimelineEventRepositoryProtocol",
    "TimelineEventServiceProtocol",
    "TimelineServiceProtocol",
]

from typing import TYPE_CHECKING, Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# Timeline protocol re-exports — split to timeline_contracts.py (RULE-04)
from narrare.planning.timeline_contracts import (  # re-export for backward compat
    CharacterAgeServiceProtocol,
    TemporalConsistencyServiceProtocol,
    TimelineAnalysisServiceProtocol,
    TimelineEventRepositoryProtocol,
    TimelineEventServiceProtocol,
    TimelineServiceProtocol,
)

# ---------------------------------------------------------------------------

if TYPE_CHECKING:
    import uuid

    from narrare.planning.models import ChapterOutline, ScenePlan
    from narrare.planning.schemas import (
        OutlineResponse,
        OutlineUpdateRequest,
        RemapResponse,
        StoryboardResponse,
        SyncStatusResponse,
    )


@runtime_checkable
class OutlineRepositoryProtocol(Protocol):
    """Protocol for chapter outline persistence."""

    async def get_by_chapter_id(self, chapter_id: uuid.UUID) -> ChapterOutline | None: ...
    async def get_all_for_novel(self, novel_id: uuid.UUID) -> list[ChapterOutline]: ...
    async def create(
        self,
        chapter_id: uuid.UUID,
        stage_assignment: str,
        planned_beats: list[dict[str, object]] | None = None,
        outline_notes: str = "",
    ) -> ChapterOutline: ...
    async def update(self, chapter_id: uuid.UUID, **fields: object) -> ChapterOutline: ...


@runtime_checkable
class ScenePlanRepositoryProtocol(Protocol):
    """Protocol for scene plan persistence (PLAN-001 — ADR-096)."""

    async def list_by_chapter(self, chapter_id: uuid.UUID) -> list[ScenePlan]: ...
    async def list_by_novel(self, novel_id: uuid.UUID) -> list[ScenePlan]: ...
    async def get(self, scene_id: uuid.UUID) -> ScenePlan | None: ...
    async def bulk_replace(
        self, chapter_id: uuid.UUID, rows: list[ScenePlan]
    ) -> list[ScenePlan]: ...


@runtime_checkable
class SyncCheckerProtocol(Protocol):
    """Protocol for structural sync status calculation."""

    def calculate_sync_status(
        self,
        outline: object,  # ChapterOutlineData from core
        suggested_stage: str,
    ) -> object: ...  # SyncStatus from core


@runtime_checkable
class StoryboardServiceProtocol(Protocol):
    """Protocol for storyboard business logic."""

    async def get_storyboard(
        self, novel_id: uuid.UUID, user_id: uuid.UUID
    ) -> StoryboardResponse: ...
    async def get_sync_status(
        self, novel_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[SyncStatusResponse]: ...
    async def get_or_create_outline(
        self,
        chapter_id: uuid.UUID,
        structure_type: str,
        user_id: uuid.UUID,
        *,
        novel_id: uuid.UUID | None = None,
    ) -> OutlineResponse: ...
    async def update_outline(
        self,
        chapter_id: uuid.UUID,
        request: OutlineUpdateRequest,
        user_id: uuid.UUID,
        *,
        novel_id: uuid.UUID | None = None,
    ) -> OutlineResponse: ...
    async def preview_remap(
        self, novel_id: uuid.UUID, new_structure: str, user_id: uuid.UUID
    ) -> RemapResponse: ...
    async def confirm_remap(
        self, novel_id: uuid.UUID, new_structure: str, user_id: uuid.UUID
    ) -> RemapResponse: ...


@runtime_checkable
class CharacterArcServiceProtocol(Protocol):
    """Protocol for character arc generation."""

    async def generate_character_arc(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        request: object,  # CharacterArcRequest from schemas
    ) -> object: ...  # CharacterArcResponse from schemas
