"""Novel repository — DB queries only."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select, update

from narrare._app.base_repository import BaseRepository
from narrare.novels.models import Novel

if TYPE_CHECKING:
    import uuid

    from narrare.novels.schemas import CreateNovelRequest, UpdateNovelRequest


class NovelRepository(BaseRepository):
    async def get(self, novel_id: uuid.UUID) -> Novel | None:
        """Load a novel by ID without ownership check (system-level access)."""
        result = await self._session.execute(select(Novel).where(Novel.id == novel_id))
        return result.scalar_one_or_none()

    async def get_by_id(self, novel_id: uuid.UUID, user_id: uuid.UUID) -> Novel | None:
        result = await self._session.execute(
            select(Novel).where(Novel.id == novel_id, Novel.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: uuid.UUID) -> list[Novel]:
        result = await self._session.execute(
            select(Novel).where(Novel.user_id == user_id).order_by(Novel.updated_at.desc())
        )
        return list(result.scalars())

    async def create(self, user_id: uuid.UUID, request: CreateNovelRequest) -> Novel:
        novel = Novel(
            user_id=user_id,
            title=request.title,
            author=request.author,
            genre=request.genre,
            writing_language=request.writing_language,
            tone=request.tone,
            story_structure=request.story_structure,
            logline=request.logline,
            synopsis=request.synopsis,
        )
        self._session.add(novel)
        await self._flush_and_refresh(novel)
        return novel

    async def update(self, novel: Novel, request: UpdateNovelRequest) -> Novel:
        for field, value in request.model_dump(exclude_none=True).items():
            setattr(novel, field, value)
        await self._flush_and_refresh(novel)
        return novel

    async def delete(self, novel: Novel) -> None:
        await self._session.delete(novel)
        await self._flush()

    async def update_series_membership(
        self,
        novel_id: uuid.UUID,
        *,
        series_id: uuid.UUID,
        series_position: int,
    ) -> None:
        """Assign a novel to a series at ``series_position`` (join flow).

        Single atomic UPDATE within the caller's transaction — the join
        service commits or rolls back the whole join (membership + KB
        promotions) together.
        """
        await self._session.execute(
            update(Novel)
            .where(Novel.id == novel_id)
            .values(series_id=series_id, series_position=series_position)
        )

    async def clear_series_membership(self, novel_id: uuid.UUID) -> None:
        """Remove a novel from its series (leave flow).

        Single atomic UPDATE within the caller's transaction — the join
        service commits or rolls back. Nulls both ``series_id`` and
        ``series_position``, returning the novel to standalone.
        """
        await self._session.execute(
            update(Novel).where(Novel.id == novel_id).values(series_id=None, series_position=None)
        )
