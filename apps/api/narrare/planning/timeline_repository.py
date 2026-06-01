"""Timeline event repository — DB queries only (RULE-07: repo → DB).

Persistence layer for ``timeline_events`` table. All SQLAlchemy queries
live here — services never write SQL directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete, select

from narrare._app.base_repository import BaseRepository
from narrare.planning.models import TimelineEvent

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class TimelineEventRepository(BaseRepository):
    """Persistence layer for timeline events."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_id(self, event_id: uuid.UUID) -> TimelineEvent | None:
        """Return a single timeline event by ID, or None.

        Args:
            event_id: UUID of the event.

        Returns:
            The ``TimelineEvent`` if found, else ``None``.
        """
        result = await self._session.execute(
            select(TimelineEvent).where(TimelineEvent.id == event_id)
        )
        return result.scalar_one_or_none()

    async def list_by_novel(
        self,
        novel_id: uuid.UUID,
        *,
        event_type: str | None = None,
        chapter_id: uuid.UUID | None = None,
        source: str | None = None,
        is_confirmed: bool | None = None,
    ) -> list[TimelineEvent]:
        """Return timeline events for a novel with optional filters.

        Events are ordered by ``temporal_order`` (NULLs last), then
        ``created_at`` as a tiebreaker.

        Args:
            novel_id: UUID of the novel.
            event_type: Optional filter by event type.
            chapter_id: Optional filter by chapter.
            source: Optional filter by source (manual/ai_analysis/extracted).
            is_confirmed: Optional filter by confirmation status.

        Returns:
            Filtered list of ``TimelineEvent`` objects.
        """
        stmt = select(TimelineEvent).where(TimelineEvent.novel_id == novel_id)

        if event_type is not None:
            stmt = stmt.where(TimelineEvent.event_type == event_type)
        if chapter_id is not None:
            stmt = stmt.where(TimelineEvent.chapter_id == chapter_id)
        if source is not None:
            stmt = stmt.where(TimelineEvent.source == source)
        if is_confirmed is not None:
            stmt = stmt.where(TimelineEvent.is_confirmed == is_confirmed)

        # Order: temporal_order ascending (NULLs last), then created_at
        stmt = stmt.order_by(
            TimelineEvent.temporal_order.asc().nulls_last(),
            TimelineEvent.created_at.asc(),
        )

        result = await self._session.execute(stmt)
        return list(result.scalars())

    async def create(self, **fields: object) -> TimelineEvent:
        """Create a new timeline event.

        Args:
            **fields: Column values for the new event.

        Returns:
            The created ``TimelineEvent`` with server-generated fields populated.
        """
        event = TimelineEvent(**fields)  # type: ignore[arg-type]
        self._session.add(event)
        await self._flush_and_refresh(event)
        return event

    async def update(self, event_id: uuid.UUID, **fields: object) -> TimelineEvent:
        """Update specific fields on a timeline event.

        Args:
            event_id: UUID of the event to update.
            **fields: Fields to update.

        Returns:
            The updated ``TimelineEvent``.

        Raises:
            NotFoundError: If the event does not exist.
        """
        event = await self.get_by_id(event_id)
        if event is None:
            from narrare_core.shared.errors import NotFoundError

            raise NotFoundError("TimelineEvent", identifier=str(event_id))

        for field, value in fields.items():
            setattr(event, field, value)
        await self._flush_and_refresh(event)
        return event

    async def delete(self, event_id: uuid.UUID) -> bool:
        """Delete a timeline event by ID.

        Args:
            event_id: UUID of the event to delete.

        Returns:
            ``True`` if an event was deleted, ``False`` if not found.
        """
        result = await self._session.execute(
            delete(TimelineEvent).where(TimelineEvent.id == event_id)
        )
        await self._flush()
        return result.rowcount > 0  # type: ignore[union-attr]

    async def bulk_create(self, events: list[dict[str, object]]) -> list[TimelineEvent]:
        """Create multiple timeline events in a single flush.

        Used for AI-generated events that need to be persisted in batch.

        Args:
            events: List of field dictionaries for each event.

        Returns:
            List of created ``TimelineEvent`` objects.
        """
        created: list[TimelineEvent] = []
        for fields in events:
            event = TimelineEvent(**fields)  # type: ignore[arg-type]
            self._session.add(event)
            created.append(event)
        await self._flush()

        # Refresh all to load server-generated fields
        for event in created:
            await self._session.refresh(event)
        return created
