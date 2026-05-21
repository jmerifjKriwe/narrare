"""Memory repository — DB queries only.

Contains two repository classes:
    - ``FeedbackRepository`` — queries for ``feedback_events`` table
    - ``PreferenceProfileRepository`` — queries for ``preference_profiles`` table
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete, func, select

from narrare._app.base_repository import BaseRepository
from narrare.memory.models import FeedbackEventModel, PreferenceProfileModel

if TYPE_CHECKING:
    import uuid


class FeedbackRepository(BaseRepository):
    """DB queries for the ``feedback_events`` table."""

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

    async def get_event_count(
        self,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> int:
        """Count feedback events for a user/project pair.

        Args:
            user_id: The user's UUID.
            project_id: The project's UUID.

        Returns:
            Number of feedback events.
        """
        result = await self._session.execute(
            select(func.count())
            .select_from(FeedbackEventModel)
            .where(
                FeedbackEventModel.user_id == user_id,
                FeedbackEventModel.project_id == project_id,
            )
        )
        return result.scalar() or 0

    async def get_events_batch(
        self,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        *,
        limit: int = 50,
    ) -> list[FeedbackEventModel]:
        """Retrieve the most recent feedback events for agent analysis.

        Args:
            user_id: The user's UUID.
            project_id: The project's UUID.
            limit: Maximum number of events to return.

        Returns:
            List of feedback events ordered by creation time (newest first).
        """
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


class PreferenceProfileRepository(BaseRepository):
    """DB queries for the ``preference_profiles`` table."""

    async def upsert(self, profile: PreferenceProfileModel) -> PreferenceProfileModel:
        """Insert or update a preference profile.

        If a profile with the same (user_id, project_id) exists, it is
        replaced. Otherwise a new row is inserted.

        Args:
            profile: The profile model to persist.

        Returns:
            The persisted profile with server-generated fields populated.
        """
        existing = await self.get(profile.user_id, profile.project_id)
        if existing is not None:
            # Update existing row
            for field in (
                "style_patterns",
                "content_patterns",
                "avoidance_patterns",
                "confidence",
                "summary",
                "event_count_at_analysis",
            ):
                setattr(existing, field, getattr(profile, field))
            await self._flush_and_refresh(existing)
            return existing

        # Insert new row
        self._session.add(profile)
        await self._flush_and_refresh(profile)
        return profile

    async def get(
        self,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> PreferenceProfileModel | None:
        """Get a preference profile by user/project pair.

        Args:
            user_id: The user's UUID.
            project_id: The project's UUID.

        Returns:
            The profile, or ``None`` if not found.
        """
        result = await self._session.execute(
            select(PreferenceProfileModel).where(
                PreferenceProfileModel.user_id == user_id,
                PreferenceProfileModel.project_id == project_id,
            )
        )
        return result.scalar_one_or_none()
