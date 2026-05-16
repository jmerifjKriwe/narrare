"""User AI settings repository — get/update user-level AI configuration.

Handles the ``user_ai_settings`` table. Auto-creates a row on first
access (same pattern as existing settings repositories). JSONB columns
are validated via Pydantic on read.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from narrare._app.base_repository import BaseRepository
from narrare.settings.models import UserAiSettings

if TYPE_CHECKING:
    import uuid


class UserAiSettingsRepository(BaseRepository):
    """Repository for ``user_ai_settings`` table operations."""

    async def get(self, user_id: uuid.UUID) -> UserAiSettings:
        """Get AI settings for a user. Auto-creates if missing.

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
            settings = UserAiSettings(user_id=user_id)
            self._session.add(settings)
            await self._flush_and_refresh(settings)
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
