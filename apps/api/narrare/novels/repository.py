"""Novel repository — DB queries only."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from narrare.novels.models import Novel

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.novels.schemas import CreateNovelRequest, UpdateNovelRequest


class NovelRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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
            language=request.language,
            tone=request.tone,
            story_structure=request.story_structure,
            logline=request.logline,
            synopsis=request.synopsis,
        )
        self._session.add(novel)
        await self._session.flush()
        return novel

    async def update(self, novel: Novel, request: UpdateNovelRequest) -> Novel:
        for field, value in request.model_dump(exclude_none=True).items():
            setattr(novel, field, value)
        await self._session.flush()
        return novel

    async def delete(self, novel: Novel) -> None:
        await self._session.delete(novel)
        await self._session.flush()
