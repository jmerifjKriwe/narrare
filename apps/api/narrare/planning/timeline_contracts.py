"""Timeline service contracts — Protocol definitions for PLAN-004 timeline features.

Defines interfaces for:
- TimelineEventRepositoryProtocol: DB queries for timeline events
- TimelineEventServiceProtocol: CRUD operations for timeline events
- TimelineAnalysisServiceProtocol: AI-powered timeline analysis + extraction
- TemporalConsistencyServiceProtocol: temporal consistency checking
- CharacterAgeServiceProtocol: character age tracking via KB metadata

Split from ``contracts.py`` to stay under the 200-line limit (RULE-04).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid

    from narrare.planning.models import TimelineEvent
    from narrare.planning.schemas import TimelineResponse
    from narrare.planning.timeline_schemas import (
        TimelineEventCreateRequest,
        TimelineEventCRUDResponse,
        TimelineEventUpdateRequest,
    )
    from narrare_core.agents.temporal_extraction_types import (
        ExtractedTemporalExpression,
    )


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

    async def stream_extraction(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        chapter_ids: list[uuid.UUID] | None,
    ) -> object: ...  # AsyncGenerator[ExtractedEventResponse, None]

    async def confirm_extracted_event(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        extracted: ExtractedTemporalExpression,
    ) -> TimelineEventCRUDResponse: ...


@runtime_checkable
class TemporalConsistencyServiceProtocol(Protocol):
    """Protocol for temporal consistency checking (PLAN-004 Phase 2)."""

    async def check_consistency(self, novel_id: uuid.UUID, user_id: uuid.UUID) -> object: ...
    async def check_character_ages(self, novel_id: uuid.UUID, user_id: uuid.UUID) -> object: ...


# Backward compatibility alias — existing code references TimelineServiceProtocol
# for the analysis service. The protocol is renamed for clarity (AD-5).
TimelineServiceProtocol = TimelineAnalysisServiceProtocol


@runtime_checkable
class CharacterAgeServiceProtocol(Protocol):
    """Protocol for character age tracking via KB metadata."""

    async def get_character_ages(self, novel_id: uuid.UUID, user_id: uuid.UUID) -> object: ...
    async def load_birth_date_map(self, novel_id: uuid.UUID) -> dict[str, str | None]: ...
