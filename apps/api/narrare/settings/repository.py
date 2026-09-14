"""Settings repository — user settings and project settings base operations.

Updated for configurable model routing to handle JSONB override columns
on project_settings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from narrare._app.base_repository import BaseRepository
from narrare.settings.models import ProjectSettings, UserSettings

if TYPE_CHECKING:
    import uuid

    from narrare.settings.schemas import UpdateProjectSettingsRequest, UpdateUserSettingsRequest


class UserSettingsRepository(BaseRepository):
    async def get(self, user_id: uuid.UUID) -> UserSettings:
        """Get settings for a user. Auto-creates if missing.

        Race-safe: the INSERT carries ``ON CONFLICT (user_id) DO NOTHING``
        so a concurrent request winning the insert does not raise
        IntegrityError — the loser re-selects the winner's committed row
        (READ COMMITTED snapshot). Without this, a racing request hit a
        UniqueViolation on ``user_settings_pkey`` → HTTP 500 (same
        defect class as ``UserAiSettingsRepository``, benchmark
        2026-09-07-clean-failed-1).

        Args:
            user_id: The user's UUID.

        Returns:
            The user's settings (never None).
        """
        result = await self._session.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
        settings = result.scalar_one_or_none()
        if not settings:
            stmt = (
                pg_insert(UserSettings)
                .values(user_id=user_id)
                .on_conflict_do_nothing(index_elements=["user_id"])
            )
            await self._session.execute(stmt)
            result = await self._session.execute(
                select(UserSettings).where(UserSettings.user_id == user_id)
            )
            settings = result.scalar_one_or_none()
            # Post-upsert the row always exists: either our INSERT landed or
            # the concurrent winner's row is committed and visible.
            assert settings is not None
        return settings

    async def update(self, user_id: uuid.UUID, request: UpdateUserSettingsRequest) -> UserSettings:
        settings = await self.get(user_id)
        for field, value in request.model_dump(exclude_none=True).items():
            setattr(settings, field, value)
        await self._flush_and_refresh(settings)
        return settings


class ProjectSettingsRepository(BaseRepository):
    async def get(self, novel_id: uuid.UUID) -> ProjectSettings:
        """Get settings for a novel. Auto-creates if missing.

        Race-safe: the INSERT carries ``ON CONFLICT (novel_id) DO NOTHING``
        so a concurrent request winning the insert does not raise
        IntegrityError — the loser re-selects the winner's committed row
        (READ COMMITTED snapshot). Without this, a racing request hit a
        UniqueViolation on ``project_settings_pkey`` → HTTP 500 (same
        defect class as ``UserAiSettingsRepository``, benchmark
        2026-09-07-clean-failed-1).

        Args:
            novel_id: The novel's UUID.

        Returns:
            The novel's settings (never None).
        """
        result = await self._session.execute(
            select(ProjectSettings).where(ProjectSettings.novel_id == novel_id)
        )
        settings = result.scalar_one_or_none()
        if not settings:
            stmt = (
                pg_insert(ProjectSettings)
                .values(novel_id=novel_id)
                .on_conflict_do_nothing(index_elements=["novel_id"])
            )
            await self._session.execute(stmt)
            result = await self._session.execute(
                select(ProjectSettings).where(ProjectSettings.novel_id == novel_id)
            )
            settings = result.scalar_one_or_none()
            # Post-upsert the row always exists: either our INSERT landed or
            # the concurrent winner's row is committed and visible.
            assert settings is not None
        return settings

    async def update(
        self, novel_id: uuid.UUID, request: UpdateProjectSettingsRequest
    ) -> ProjectSettings:
        settings = await self.get(novel_id)
        for field, value in request.model_dump(exclude_none=True).items():
            setattr(settings, field, value)
        await self._flush_and_refresh(settings)
        return settings
