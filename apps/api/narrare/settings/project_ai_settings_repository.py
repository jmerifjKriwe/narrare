"""Project AI settings repository — get/update project-level AI overrides.

Handles the JSONB override columns on the ``project_settings`` table.
Reuses the existing ``ProjectSettings`` model but focuses on AI-related
fields only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from narrare._app.base_repository import BaseRepository
from narrare.settings.models import ProjectSettings

if TYPE_CHECKING:
    import uuid


class ProjectAiSettingsRepository(BaseRepository):
    """Repository for project-level AI override columns."""

    async def get(self, novel_id: uuid.UUID) -> ProjectSettings:
        """Get project settings including AI override columns.

        Auto-creates if the project has no settings row yet. Race-safe:
        the INSERT carries ``ON CONFLICT (novel_id) DO NOTHING`` so a
        concurrent request winning the insert does not raise
        IntegrityError — the loser re-selects the winner's committed row
        (READ COMMITTED snapshot). Without this, a racing request hit a
        UniqueViolation on ``project_settings_pkey`` → HTTP 500
        (benchmark 2026-09-07-clean-failed-1).

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
        await self._flush_and_refresh(settings)
        return settings
