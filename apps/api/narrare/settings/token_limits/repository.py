"""Token limits repository — get/update user and project overrides.

SQLAlchemy queries only — no business logic (RULE-06).
Auto-creates rows on first access (same pattern as existing settings repos).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from narrare._app.base_repository import BaseRepository
from narrare.settings.token_limits.models import ProjectTokenLimits, UserTokenLimits

if TYPE_CHECKING:
    from collections.abc import Mapping


class UserTokenLimitsRepository(BaseRepository):
    """Repository for ``user_token_limits`` table operations.

    Follows the same create-on-first-access pattern as
    ``UserAiSettingsRepository`` and ``UserSettingsRepository``.
    """

    async def get(self, user_id: str) -> UserTokenLimits:
        """Get user-level token limit overrides.

        Args:
            user_id: The user's ID (string from auth).

        Returns:
            The user's token limits (never None — auto-creates if missing).
        """
        result = await self._session.execute(
            select(UserTokenLimits).where(UserTokenLimits.user_id == user_id)
        )
        limits = result.scalar_one_or_none()
        if not limits:
            limits = UserTokenLimits(user_id=user_id)
            self._session.add(limits)
            await self._flush_and_refresh(limits)
        return limits

    async def update(
        self,
        user_id: str,
        overrides: Mapping[str, object],
    ) -> UserTokenLimits:
        """Update user-level token limit overrides.

        Args:
            user_id: The user's ID.
            overrides: Dict of fields to persist in the overrides JSONB column.

        Returns:
            The updated token limits entity.
        """
        limits = await self.get(user_id)
        current = dict(limits.overrides) if limits.overrides else {}
        current.update(overrides)
        limits.overrides = current
        await self._flush_and_refresh(limits)
        return limits


class ProjectTokenLimitsRepository(BaseRepository):
    """Repository for ``project_token_limits`` table operations."""

    async def get(self, project_id: str) -> ProjectTokenLimits:
        """Get project-level token limit overrides.

        Args:
            project_id: The project/novel ID.

        Returns:
            The project's token limits (never None — auto-creates if missing).
        """
        result = await self._session.execute(
            select(ProjectTokenLimits).where(ProjectTokenLimits.project_id == project_id)
        )
        limits = result.scalar_one_or_none()
        if not limits:
            limits = ProjectTokenLimits(project_id=project_id)
            self._session.add(limits)
            await self._flush_and_refresh(limits)
        return limits

    async def update(
        self,
        project_id: str,
        overrides: Mapping[str, object],
    ) -> ProjectTokenLimits:
        """Update project-level token limit overrides.

        Args:
            project_id: The project/novel ID.
            overrides: Dict of fields to persist in the overrides JSONB column.

        Returns:
            The updated token limits entity.
        """
        limits = await self.get(project_id)
        current = dict(limits.overrides) if limits.overrides else {}
        current.update(overrides)
        limits.overrides = current
        await self._flush_and_refresh(limits)
        return limits
