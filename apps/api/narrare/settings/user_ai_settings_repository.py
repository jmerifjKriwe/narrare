"""User AI settings repository — get/update user-level AI configuration.

Handles the ``user_ai_settings`` table. Auto-creates a row on first
access (same pattern as existing settings repositories). JSONB columns
are validated via Pydantic on read.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from narrare._app.base_repository import BaseRepository
from narrare.settings.models import UserAiSettings

if TYPE_CHECKING:
    import uuid


class UserAiSettingsRepository(BaseRepository):
    """Repository for ``user_ai_settings`` table operations."""

    async def get(self, user_id: uuid.UUID) -> UserAiSettings:
        """Get AI settings for a user. Auto-creates if missing.

        Race-safe: the INSERT carries ``ON CONFLICT (user_id) DO NOTHING``
        so a concurrent request winning the insert does not raise
        IntegrityError — the loser re-selects the winner's committed row
        (READ COMMITTED snapshot). Without this, a racing request hit a
        UniqueViolation on ``user_ai_settings_pkey`` → HTTP 500 (same
        defect class as ``ProjectAiSettingsRepository``, benchmark
        2026-09-07-clean-failed-1).

        Args:
            user_id: The user's UUID.

        Returns:
            The user's AI settings (never None).
        """
        result = await self._session.execute(
            select(UserAiSettings).where(UserAiSettings.user_id == user_id)
        )
        settings = result.scalar_one_or_none()
        if not settings:
            stmt = (
                pg_insert(UserAiSettings)
                .values(user_id=user_id)
                .on_conflict_do_nothing(index_elements=["user_id"])
            )
            await self._session.execute(stmt)
            result = await self._session.execute(
                select(UserAiSettings).where(UserAiSettings.user_id == user_id)
            )
            settings = result.scalar_one_or_none()
            # Post-upsert the row always exists: either our INSERT landed or
            # the concurrent winner's row is committed and visible.
            assert settings is not None
        return settings

    async def update(self, user_id: uuid.UUID, **kwargs: object) -> UserAiSettings:
        """Update AI settings fields.

        Args:
            user_id: The user's UUID.
            **kwargs: Fields to update (e.g. default_provider_id,
                default_model, category_overrides, etc.)

        Returns:
            The updated settings.
        """
        settings = await self.get(user_id)
        for field, value in kwargs.items():
            setattr(settings, field, value)
        await self._flush_and_refresh(settings)
        return settings
