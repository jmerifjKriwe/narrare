"""Scene plan repository — DB queries only (RULE-07: repo → DB)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from narrare._app.base_repository import BaseRepository
from narrare.planning.models import ScenePlan

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

# Mutable scene fields carried onto persisted rows during bulk_replace.
# id is the diff key, chapter_id/position are managed by the diff-sync
# itself, and timestamps are owned by the DB (server defaults / onupdate).
_SCENE_FIELDS: tuple[str, ...] = (
    "title",
    "pov_character_ref",
    "location_ref",
    "present_characters",
    "purpose",
    "conflict",
    "resolution",
    "beats",
    "status",
)


class ScenePlanRepository(BaseRepository):
    """Persistence layer for chapter scene plans (PLAN-001 — ADR-096)."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def list_by_chapter(self, chapter_id: uuid.UUID) -> list[ScenePlan]:
        """Return all scenes of a chapter ordered by position."""
        result = await self._session.execute(
            select(ScenePlan).where(ScenePlan.chapter_id == chapter_id).order_by(ScenePlan.position)
        )
        return list(result.scalars())

    async def list_by_novel(self, novel_id: uuid.UUID) -> list[ScenePlan]:
        """Return all scenes of a novel ordered by chapter, then scene position.

        Joins through the ``chapters`` table to filter by ``novel_id``.
        """
        from narrare.chapters.models import Chapter

        result = await self._session.execute(
            select(ScenePlan)
            .join(Chapter, ScenePlan.chapter_id == Chapter.id)
            .where(Chapter.novel_id == novel_id)
            .order_by(Chapter.position, ScenePlan.position)
        )
        return list(result.scalars())

    async def get(self, scene_id: uuid.UUID) -> ScenePlan | None:
        """Return a scene plan by id, or None."""
        result = await self._session.execute(select(ScenePlan).where(ScenePlan.id == scene_id))
        return result.scalar_one_or_none()

    async def bulk_replace(self, chapter_id: uuid.UUID, rows: list[ScenePlan]) -> list[ScenePlan]:
        """Replace a chapter's scene plan with ``rows`` (aggregate diff-sync).

        Deletes persisted rows absent from ``rows`` (matched by id), inserts
        new ids, carries ``rows``' fields onto the persisted rows for
        existing ids, and renumbers ``position`` 1..N in ``rows`` order.
        ``chapter_id`` is forced onto every row. All changes flush in one
        flush; returned rows are refreshed so server-default columns
        (created_at/updated_at) are loaded.
        """
        existing = await self.list_by_chapter(chapter_id)
        existing_by_id = {row.id: row for row in existing}
        incoming_ids = {row.id for row in rows}

        for row in existing:
            if row.id not in incoming_ids:
                await self._session.delete(row)

        result: list[ScenePlan] = []
        for position, incoming in enumerate(rows, start=1):
            persisted = existing_by_id.get(incoming.id)
            row = persisted if persisted is not None and persisted is not incoming else incoming
            if row is not incoming:
                for field in _SCENE_FIELDS:
                    setattr(row, field, getattr(incoming, field))
            row.chapter_id = chapter_id
            row.position = position
            if persisted is None:
                self._session.add(incoming)
            result.append(row)

        await self._flush()
        for row in result:
            await self._session.refresh(row)
        return result
