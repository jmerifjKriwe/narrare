"""Wiki repository — DB queries for wiki summaries.

Handles persistence and staleness tracking for ``WikiSummary`` and
``WikiChapterSummary`` entities.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import delete, func, select, type_coerce, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert

from narrare._app.base_repository import BaseRepository
from narrare.wiki.models import WikiChapterSummary, WikiSummary

if TYPE_CHECKING:
    from collections.abc import Sequence

    from narrare_core.wiki.types import (
        WikiChapterOutput,
        WikiChapterSummaryData,
        WikiEntityOutput,
        WikiSummaryData,
    )


class WikiRepository(BaseRepository):
    """Persistence operations for WikiSummary and WikiChapterSummary.

    Provides upsert, lookup, staleness marking, and deletion methods
    for the precomputed LLM wiki layer.
    """

    async def upsert_summary(
        self,
        summary_data: WikiSummaryData,
        output: WikiEntityOutput,
    ) -> WikiSummary:
        """Insert or update a WikiSummary on conflict ``(novel_id, entity_id)``.
        Uses PostgreSQL ``INSERT … ON CONFLICT DO UPDATE``;
        bumps ``generated_at`` on conflict.
        """
        insert_stmt = pg_insert(WikiSummary).values(
            novel_id=uuid.UUID(summary_data.novel_id),
            entity_id=uuid.UUID(summary_data.entity_id),
            narrative_summary=output.narrative_summary,
            role_in_story=output.role_in_story,
            key_attributes=output.key_attributes or None,
            relationships=output.relationships or None,
            chapter_references=summary_data.chapter_references or None,
            character_arc=output.character_arc,
            depends_on=summary_data.depends_on or None,
            status=summary_data.status.value,
            version=summary_data.version,
            content_hash=summary_data.content_hash,
        )
        upsert_stmt = insert_stmt.on_conflict_do_update(
            constraint="uq_wiki_summary_entity",
            set_={
                "narrative_summary": insert_stmt.excluded.narrative_summary,
                "role_in_story": insert_stmt.excluded.role_in_story,
                "key_attributes": insert_stmt.excluded.key_attributes,
                "relationships": insert_stmt.excluded.relationships,
                "chapter_references": insert_stmt.excluded.chapter_references,
                "character_arc": insert_stmt.excluded.character_arc,
                "depends_on": insert_stmt.excluded.depends_on,
                "status": insert_stmt.excluded.status,
                "version": insert_stmt.excluded.version,
                "content_hash": insert_stmt.excluded.content_hash,
                "generated_at": func.now(),
            },
        ).returning(WikiSummary)
        result = await self._session.execute(upsert_stmt)
        return result.scalar_one()

    async def upsert_chapter_summary(
        self,
        chapter_summary_data: WikiChapterSummaryData,
        output: WikiChapterOutput,
    ) -> WikiChapterSummary:
        """Insert or update a WikiChapterSummary on conflict ``chapter_id``.
        Uses PostgreSQL ``INSERT … ON CONFLICT DO UPDATE``.
        """
        insert_stmt = pg_insert(WikiChapterSummary).values(
            chapter_id=uuid.UUID(chapter_summary_data.chapter_id),
            narrative_summary=output.narrative_summary,
            key_events=output.key_events or None,
            entities_involved=output.entities_involved or None,
            themes=output.themes or None,
            emotional_arc=output.emotional_arc,
            chapter_content_hash=chapter_summary_data.chapter_content_hash,
            wiki_prompt_version=chapter_summary_data.wiki_prompt_version,
            status=chapter_summary_data.status.value,
            version=chapter_summary_data.version,
        )
        upsert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=["chapter_id"],
            set_={
                "narrative_summary": insert_stmt.excluded.narrative_summary,
                "key_events": insert_stmt.excluded.key_events,
                "entities_involved": insert_stmt.excluded.entities_involved,
                "themes": insert_stmt.excluded.themes,
                "emotional_arc": insert_stmt.excluded.emotional_arc,
                "chapter_content_hash": insert_stmt.excluded.chapter_content_hash,
                "wiki_prompt_version": insert_stmt.excluded.wiki_prompt_version,
                "status": insert_stmt.excluded.status,
                "version": insert_stmt.excluded.version,
            },
        ).returning(WikiChapterSummary)
        result = await self._session.execute(upsert_stmt)
        return result.scalar_one()

    async def get_summary(self, entity_id: uuid.UUID, novel_id: uuid.UUID) -> WikiSummary | None:
        """Fetch a single WikiSummary by ``entity_id`` and ``novel_id``."""
        return (
            await self._session.execute(
                select(WikiSummary).where(
                    WikiSummary.entity_id == entity_id, WikiSummary.novel_id == novel_id
                )
            )
        ).scalar_one_or_none()

    async def get_summaries(
        self, entity_ids: Sequence[uuid.UUID] | None, novel_id: uuid.UUID
    ) -> list[WikiSummary]:
        """Fetch WikiSummaries for a novel, optionally filtered by entity IDs."""
        stmt = select(WikiSummary).where(WikiSummary.novel_id == novel_id)
        if entity_ids:
            stmt = stmt.where(WikiSummary.entity_id.in_(entity_ids))
        return list((await self._session.execute(stmt)).scalars())

    async def get_chapter_summary(self, chapter_id: uuid.UUID) -> WikiChapterSummary | None:
        """Fetch a single WikiChapterSummary by ``chapter_id``."""
        return (
            await self._session.execute(
                select(WikiChapterSummary).where(WikiChapterSummary.chapter_id == chapter_id)
            )
        ).scalar_one_or_none()

    async def mark_stale(self, entity_ids: Sequence[uuid.UUID]) -> int:
        """Mark WikiSummaries for the given entity IDs as ``stale``."""
        result = await self._session.execute(
            update(WikiSummary).where(WikiSummary.entity_id.in_(entity_ids)).values(status="stale")
        )
        await self._flush()
        return getattr(result, "rowcount", 0)

    async def mark_all_stale(
        self,
        novel_id: uuid.UUID,
        current_prompt_version: str,
    ) -> int:
        """Mark WikiSummaries STALE whose ``depends_on->>wiki_prompt_version``
        differs from ``current_prompt_version`` via JSONB path traversal.
        Returns the number of rows updated.
        """
        result = await self._session.execute(
            update(WikiSummary)
            .where(
                WikiSummary.novel_id == novel_id,
                WikiSummary.depends_on.isnot(None),
                WikiSummary.depends_on["wiki_prompt_version"].as_string().isnot(None),
                WikiSummary.depends_on["wiki_prompt_version"].as_string() != current_prompt_version,
            )
            .values(status="stale")
        )
        await self._flush()
        return getattr(result, "rowcount", 0)

    async def mark_related_stale(self, entity_id: uuid.UUID) -> int:
        """KARPATHY: Mark WikiSummaries STALE that reference the entity
        (JSONB containment ``@>`` on ``relationships`` array).
        Returns the number of rows updated.
        """
        entity_ref = [{"entity_id": str(entity_id)}]
        result = await self._session.execute(
            update(WikiSummary)
            .where(
                WikiSummary.relationships.isnot(None),
                WikiSummary.relationships.op("@>")(type_coerce(entity_ref, JSONB)),
            )
            .values(status="stale")
        )
        await self._flush()
        return getattr(result, "rowcount", 0)

    async def delete_summary(self, entity_id: uuid.UUID) -> None:
        """Delete a WikiSummary by ``entity_id``."""
        await self._session.execute(delete(WikiSummary).where(WikiSummary.entity_id == entity_id))
        await self._flush()
