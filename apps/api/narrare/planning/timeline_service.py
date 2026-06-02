"""Timeline CRUD service — create, read, update, delete timeline events.

Implements ``TimelineEventServiceProtocol`` from timeline_contracts.py.
Uses ``TimelineEventRepository`` for all DB queries and
``NovelRepository`` for ownership verification.

Pattern: router → service → repository (RULE-06, RULE-07).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.planning.timeline_schemas import TimelineEventCRUDResponse
from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    import uuid

    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository
    from narrare.planning.timeline_repository import TimelineEventRepository
    from narrare.planning.timeline_schemas import (
        TimelineEventCreateRequest,
        TimelineEventUpdateRequest,
    )

logger = structlog.get_logger(__name__)


class TimelineService:
    """CRUD service for persistent timeline events.

    Verifies novel ownership before every operation and validates
    chapter_id references when provided.

    Args:
        event_repo: Persistence layer for timeline events.
        novel_repo: For ownership verification.
        chapter_repo: For chapter existence checks.
    """

    def __init__(
        self,
        event_repo: TimelineEventRepository,
        novel_repo: NovelRepository,
        chapter_repo: ChapterRepository,
    ) -> None:
        self._event_repo = event_repo
        self._novel_repo = novel_repo
        self._chapter_repo = chapter_repo

    async def _verify_novel_ownership(self, novel_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Verify the novel exists and belongs to the user.

        Args:
            novel_id: UUID of the novel.
            user_id: UUID of the requesting user.

        Raises:
            NotFoundError: If the novel does not exist or doesn't belong to user.
        """
        novel = await self._novel_repo.get_by_id(novel_id, user_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(novel_id))

    async def _verify_event_in_novel(self, event_id: uuid.UUID, novel_id: uuid.UUID) -> None:
        """Verify an event exists and belongs to the given novel.

        Args:
            event_id: UUID of the event.
            novel_id: UUID of the novel.

        Raises:
            NotFoundError: If the event does not exist or doesn't belong to novel.
        """
        event = await self._event_repo.get_by_id(event_id)
        if event is None or event.novel_id != novel_id:
            raise NotFoundError("TimelineEvent", identifier=str(event_id))

    async def create_event(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        request: TimelineEventCreateRequest,
    ) -> TimelineEventCRUDResponse:
        """Create a new timeline event.

        Args:
            novel_id: UUID of the novel.
            user_id: UUID of the requesting user.
            request: Creation payload.

        Returns:
            The created event as a response.

        Raises:
            NotFoundError: If the novel or referenced chapter doesn't exist.
        """
        await self._verify_novel_ownership(novel_id, user_id)

        # Validate chapter_id belongs to this novel if provided
        if request.chapter_id is not None:
            chapter = await self._chapter_repo.get_by_id(request.chapter_id, novel_id)
            if chapter is None:
                raise NotFoundError("Chapter", identifier=str(request.chapter_id))

        event = await self._event_repo.create(
            novel_id=novel_id,
            event_name=request.event_name,
            description=request.description,
            event_type=request.event_type,
            timestamp_raw=request.timestamp_raw,
            timestamp_normalized=request.timestamp_normalized,
            temporal_order=request.temporal_order,
            chapter_id=request.chapter_id,
            character_refs=[dict(ref) for ref in request.character_refs],
            location_ref=dict(request.location_ref) if request.location_ref else None,
            causes=request.causes,
            consequences=request.consequences,
            source="manual",
            is_confirmed=True,
        )
        logger.info(
            "timeline_event_created",
            event_id=str(event.id),
            novel_id=str(novel_id),
        )
        return TimelineEventCRUDResponse.model_validate(event)

    async def list_events(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        **filters: object,
    ) -> list[TimelineEventCRUDResponse]:
        """List timeline events for a novel with optional filters.

        Args:
            novel_id: UUID of the novel.
            user_id: UUID of the requesting user.
            **filters: Optional filters (event_type, chapter_id, source, is_confirmed).

        Returns:
            Filtered list of event responses.

        Raises:
            NotFoundError: If the novel does not exist.
        """
        await self._verify_novel_ownership(novel_id, user_id)

        events = await self._event_repo.list_by_novel(
            novel_id,
            event_type=filters.get("event_type"),  # type: ignore[arg-type]
            chapter_id=filters.get("chapter_id"),  # type: ignore[arg-type]
            source=filters.get("source"),  # type: ignore[arg-type]
            is_confirmed=filters.get("is_confirmed"),  # type: ignore[arg-type]
        )
        return [TimelineEventCRUDResponse.model_validate(e) for e in events]

    async def get_event(
        self,
        event_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        novel_id: uuid.UUID | None = None,
    ) -> TimelineEventCRUDResponse:
        """Get a single timeline event by ID.

        Args:
            event_id: UUID of the event.
            user_id: UUID of the requesting user.
            novel_id: Optional novel scope for validation.

        Returns:
            The event response.

        Raises:
            NotFoundError: If the event doesn't exist.
        """
        event = await self._event_repo.get_by_id(event_id)
        if event is None:
            raise NotFoundError("TimelineEvent", identifier=str(event_id))

        # Verify ownership via novel
        await self._verify_novel_ownership(event.novel_id, user_id)

        return TimelineEventCRUDResponse.model_validate(event)

    async def update_event(
        self,
        event_id: uuid.UUID,
        user_id: uuid.UUID,
        request: TimelineEventUpdateRequest,
        *,
        novel_id: uuid.UUID | None = None,
    ) -> TimelineEventCRUDResponse:
        """Update specific fields on a timeline event.

        Args:
            event_id: UUID of the event to update.
            user_id: UUID of the requesting user.
            request: Update payload (only non-None fields are applied).
            novel_id: Optional novel scope for validation.

        Returns:
            The updated event response.

        Raises:
            NotFoundError: If the event or referenced chapter doesn't exist.
        """
        event = await self._event_repo.get_by_id(event_id)
        if event is None:
            raise NotFoundError("TimelineEvent", identifier=str(event_id))

        await self._verify_novel_ownership(event.novel_id, user_id)

        updates = request.model_dump(exclude_none=True)

        # Validate chapter_id if being updated
        if "chapter_id" in updates and updates["chapter_id"] is not None:
            chapter = await self._chapter_repo.get_by_id(updates["chapter_id"], event.novel_id)
            if chapter is None:
                raise NotFoundError("Chapter", identifier=str(updates["chapter_id"]))

        # Convert character_refs/location_ref lists/dicts for JSONB storage
        if "character_refs" in updates:
            updates["character_refs"] = [dict(ref) for ref in updates["character_refs"]]
        if "location_ref" in updates and updates["location_ref"] is not None:
            updates["location_ref"] = dict(updates["location_ref"])

        updated = await self._event_repo.update(event_id, **updates)
        logger.info(
            "timeline_event_updated",
            event_id=str(event_id),
            fields=list(updates.keys()),
        )
        return TimelineEventCRUDResponse.model_validate(updated)

    async def delete_event(
        self,
        event_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Delete a timeline event.

        Args:
            event_id: UUID of the event to delete.
            user_id: UUID of the requesting user.

        Returns:
            ``True`` if the event was deleted, ``False`` if not found.

        Raises:
            NotFoundError: If the user doesn't own the event's novel.
        """
        event = await self._event_repo.get_by_id(event_id)
        if event is None:
            return False

        await self._verify_novel_ownership(event.novel_id, user_id)

        deleted = await self._event_repo.delete(event_id)
        if deleted:
            logger.info("timeline_event_deleted", event_id=str(event_id))
        return deleted
