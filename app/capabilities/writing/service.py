"""Writing logic. Routers delegate here; this module knows the unit of work."""

from typing import TYPE_CHECKING

from app.capabilities.writing.repository import NovelRepository

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.kernel.contracts.models import Novel


class WritingService:
    def __init__(self, session: AsyncSession, user_id: UUID) -> None:
        self.session = session
        self.user_id = user_id
        self.novels = NovelRepository(session, user_id)

    async def create_novel(self, title: str) -> Novel:
        novel = await self.novels.create(title)
        await self.session.commit()
        return novel

    async def list_novels(self) -> Sequence[Novel]:
        return await self.novels.list()
