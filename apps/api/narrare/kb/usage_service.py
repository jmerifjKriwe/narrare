"""Context usage service — tracks proactive suggestion feedback.

Records accept/dismiss events in ``context_usage_events`` and updates
``kb_entries.usage_count`` / ``last_referenced_at`` on accept.

Implements ``ContextUsageProtocol`` from ``contracts.py`` (RULE-03).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class ContextUsageService:
    """Track user feedback on proactive context suggestions.

    On accept: INSERT event + UPDATE kb_entries counters.
    On dismiss: INSERT event only (no counter update).

    Args:
        session: AsyncSession for DB operations.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record_accept(
        self,
        novel_id: UUID,
        entry_id: UUID,
        chapter_id: UUID | None,
        source: str,
    ) -> None:
        """Record a suggestion acceptance.

        Inserts a context_usage_event row and increments
        ``kb_entries.usage_count`` + updates ``last_referenced_at``.
        """
        import sqlalchemy

        # Insert usage event
        await self._session.execute(
            sqlalchemy.text(
                """
                INSERT INTO context_usage_events
                    (id, novel_id, entry_id, chapter_id, action, source, created_at)
                VALUES
                    (gen_random_uuid(), :novel_id, :entry_id, :chapter_id,
                     'accepted', :source, now())
                """
            ),
            {
                "novel_id": str(novel_id),
                "entry_id": str(entry_id),
                "chapter_id": str(chapter_id) if chapter_id else None,
                "source": source,
            },
        )

        # Update kb_entries usage counters
        await self._session.execute(
            sqlalchemy.text(
                """
                UPDATE kb_entries
                SET usage_count = usage_count + 1,
                    last_referenced_at = now()
                WHERE id = :entry_id
                """
            ),
            {"entry_id": str(entry_id)},
        )

        await self._session.flush()
        logger.info(
            "context_usage_accepted",
            entry_id=str(entry_id),
            novel_id=str(novel_id),
            source=source,
        )

    async def record_dismiss(
        self,
        novel_id: UUID,
        entry_id: UUID,
        chapter_id: UUID | None,
        source: str,
    ) -> None:
        """Record a suggestion dismissal.

        Inserts a context_usage_event row only — does NOT update
        ``kb_entries.usage_count`` or ``last_referenced_at``.
        """
        import sqlalchemy

        await self._session.execute(
            sqlalchemy.text(
                """
                INSERT INTO context_usage_events
                    (id, novel_id, entry_id, chapter_id, action, source, created_at)
                VALUES
                    (gen_random_uuid(), :novel_id, :entry_id, :chapter_id,
                     'dismissed', :source, now())
                """
            ),
            {
                "novel_id": str(novel_id),
                "entry_id": str(entry_id),
                "chapter_id": str(chapter_id) if chapter_id else None,
                "source": source,
            },
        )

        await self._session.flush()
        logger.info(
            "context_usage_dismissed",
            entry_id=str(entry_id),
            novel_id=str(novel_id),
            source=source,
        )

    async def get_usage_stats(self, entry_id: UUID) -> dict[str, int]:
        """Return accept/dismiss counts for an entry.

        Returns:
            Dict with ``accepted`` and ``dismissed`` counts.
        """
        import sqlalchemy

        result = await self._session.execute(
            sqlalchemy.text(
                """
                SELECT action, COUNT(*) AS cnt
                FROM context_usage_events
                WHERE entry_id = :entry_id
                GROUP BY action
                """
            ),
            {"entry_id": str(entry_id)},
        )

        stats: dict[str, int] = {"accepted": 0, "dismissed": 0}
        for row in result.fetchall():
            action = row[0]
            count = int(row[1])
            if action in stats:
                stats[action] = count

        return stats
