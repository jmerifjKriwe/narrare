"""Memory repository — DB queries only."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete, func, select

from narrare._app.base_repository import BaseRepository
from narrare.memory.models import FeedbackEventModel

if TYPE_CHECKING:
    import uuid


class FeedbackRepository(BaseRepository):
    """DB queries for the memory domain."""

    async def create(self, event: FeedbackEventModel) -> FeedbackEventModel:
        """Persist a new feedback event."""
        self._session.add(event)
        await self._flush_and_refresh(event)
        return event

    async def list_by_user_project(
        self,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        *,
        limit: int = 100,
    ) -> list[FeedbackEventModel]:
        """Retrieve recent feedback events for a user/project pair."""
        result = await self._session.execute(
            select(FeedbackEventModel)
            .where(
                FeedbackEventModel.user_id == user_id,
                FeedbackEventModel.project_id == project_id,
            )
            .order_by(FeedbackEventModel.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def delete_by_user_project(
        self,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> int:
        """Delete all feedback events for a user/project pair. Returns count deleted."""
        count_result = await self._session.execute(
            select(func.count())
            .select_from(FeedbackEventModel)
            .where(
                FeedbackEventModel.user_id == user_id,
                FeedbackEventModel.project_id == project_id,
            )
        )
        count = count_result.scalar() or 0

        await self._session.execute(
            delete(FeedbackEventModel).where(
                FeedbackEventModel.user_id == user_id,
                FeedbackEventModel.project_id == project_id,
            )
        )
        await self._flush()
        return count
