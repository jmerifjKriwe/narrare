"""Planning service contracts — Protocol definitions (RULE-03: contract first).

Defines interfaces for:
- OutlineRepositoryProtocol: DB queries for chapter outlines
- SyncCheckerProtocol: structural sync status calculation
- StoryboardServiceProtocol: business logic for storyboard feature
- TimelineEventRepositoryProtocol: DB queries for timeline events
- TimelineEventServiceProtocol: CRUD operations for timeline events
- TimelineAnalysisServiceProtocol: AI-powered timeline analysis + extraction
- TemporalConsistencyServiceProtocol: temporal consistency checking
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid

    from narrare.planning.models import ChapterOutline, TimelineEvent
    from narrare.planning.schemas import (
        OutlineResponse,
        OutlineUpdateRequest,
        RemapResponse,
        StoryboardResponse,
        SyncStatusResponse,
        TimelineResponse,
    )
    from narrare.planning.timeline_schemas import (
        TimelineEventCreateRequest,
        TimelineEventCRUDResponse,
        TimelineEventUpdateRequest,
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


# ---------------------------------------------------------------------------
# Timeline protocols — Phase 1 (PLAN-004)
# ---------------------------------------------------------------------------


@runtime_checkable
class TimelineEventRepositoryProtocol(Protocol):
    """Protocol for timeline event persistence."""

    async def get_by_id(self, event_id: uuid.UUID) -> TimelineEvent | None: ...
    async def list_by_novel(
        self,
        novel_id: uuid.UUID,
        *,
        event_type: str | None = None,
        chapter_id: uuid.UUID | None = None,
        source: str | None = None,
        is_confirmed: bool | None = None,
    ) -> list[TimelineEvent]: ...
    async def create(self, **fields: object) -> TimelineEvent: ...
    async def update(self, event_id: uuid.UUID, **fields: object) -> TimelineEvent: ...
    async def delete(self, event_id: uuid.UUID) -> bool: ...
    async def bulk_create(self, events: list[dict[str, object]]) -> list[TimelineEvent]: ...


@runtime_checkable
class TimelineEventServiceProtocol(Protocol):
    """Protocol for timeline event CRUD operations."""

    async def create_event(
        self, novel_id: uuid.UUID, user_id: uuid.UUID, request: TimelineEventCreateRequest
    ) -> TimelineEventCRUDResponse: ...
    async def list_events(
        self, novel_id: uuid.UUID, user_id: uuid.UUID, **filters: object
    ) -> list[TimelineEventCRUDResponse]: ...
    async def get_event(
        self, event_id: uuid.UUID, user_id: uuid.UUID
    ) -> TimelineEventCRUDResponse: ...
    async def update_event(
        self, event_id: uuid.UUID, user_id: uuid.UUID, request: TimelineEventUpdateRequest
    ) -> TimelineEventCRUDResponse: ...
    async def delete_event(self, event_id: uuid.UUID, user_id: uuid.UUID) -> bool: ...


@runtime_checkable
class TimelineAnalysisServiceProtocol(Protocol):
    """Protocol for AI-powered timeline analysis and extraction."""

    async def generate_timeline(
        self, novel_id: uuid.UUID, user_id: uuid.UUID
    ) -> TimelineResponse: ...

    async def extract_temporal_expressions(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        chapter_ids: list[uuid.UUID] | None = None,
    ) -> list[object]: ...

    async def confirm_extracted_event(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        extracted: object,
    ) -> object: ...


@runtime_checkable
class TemporalConsistencyServiceProtocol(Protocol):
    """Protocol for temporal consistency checking (PLAN-004 Phase 2)."""

    async def check_consistency(self, novel_id: uuid.UUID, user_id: uuid.UUID) -> object: ...


# Backward compatibility alias — existing code references TimelineServiceProtocol
# for the analysis service. The protocol is renamed for clarity (AD-5).
TimelineServiceProtocol = TimelineAnalysisServiceProtocol
