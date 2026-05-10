"""Novel service — business logic."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from fastapi import HTTPException, status

from narrare.novels.repository import NovelRepository

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.novels.models import Novel
    from narrare.novels.schemas import CreateNovelRequest, UpdateNovelRequest

logger = structlog.get_logger(__name__)


class NovelService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = NovelRepository(session)

    async def get(self, novel_id: uuid.UUID, user_id: uuid.UUID) -> Novel:
        """
        Get a novel by ID, verifying ownership.

        Raises:
            HTTPException 404: If novel not found or doesn't belong to user.
        """
        novel = await self._repo.get_by_id(novel_id, user_id)
        if not novel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Novel not found",
            )
        return novel

    async def list_novels(self, user_id: uuid.UUID) -> list[Novel]:
        """List all novels for a user, most recently updated first."""
        return await self._repo.list_by_user(user_id)

    async def create(self, user_id: uuid.UUID, request: CreateNovelRequest) -> Novel:
        """Create a new novel for a user."""
        novel = await self._repo.create(user_id, request)
        logger.info("novel_created", novel_id=str(novel.id), user_id=str(user_id))
        return novel

    async def update(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        request: UpdateNovelRequest,
    ) -> Novel:
        """Update a novel's metadata."""
        novel = await self.get(novel_id, user_id)
        updated = await self._repo.update(novel, request)
        logger.info("novel_updated", novel_id=str(novel_id))
        return updated

    async def delete(self, novel_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Delete a novel and all its content."""
        novel = await self.get(novel_id, user_id)
        await self._repo.delete(novel)
        logger.info("novel_deleted", novel_id=str(novel_id))
