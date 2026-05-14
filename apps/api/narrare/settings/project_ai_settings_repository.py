"""Project AI settings repository — get/update project-level AI overrides.

Handles the JSONB override columns on the ``project_settings`` table.
Reuses the existing ``ProjectSettings`` model but focuses on AI-related
fields only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from narrare.settings.models import ProjectSettings

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class ProjectAiSettingsRepository:
    """Repository for project-level AI override columns."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, novel_id: uuid.UUID) -> ProjectSettings:
        """Get project settings including AI override columns.

        Auto-creates if the project has no settings row yet.

        Args:
            novel_id: The novel's UUID.

        Returns:
            The project settings with AI override columns.
        """
        result = await self._session.execute(
            select(ProjectSettings).where(ProjectSettings.novel_id == novel_id)
        )
        settings = result.scalar_one_or_none()
        if not settings:
            settings = ProjectSettings(novel_id=novel_id)
            self._session.add(settings)
            await self._session.flush()
            await self._session.refresh(settings)
        return settings

    async def update(self, novel_id: uuid.UUID, **kwargs: object) -> ProjectSettings:
        """Update project AI override fields.

        Args:
            novel_id: The novel's UUID.
            **kwargs: AI-related fields to update
                (category_overrides, intent_overrides, token_limit_overrides).

        Returns:
            The updated project settings.
        """
        settings = await self.get(novel_id)
        for field, value in kwargs.items():
            setattr(settings, field, value)
        await self._session.flush()
        await self._session.refresh(settings)
        return settings
