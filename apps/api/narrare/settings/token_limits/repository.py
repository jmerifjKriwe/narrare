"""Token limits repository — get/update user and project overrides.

SQLAlchemy queries only — no business logic (RULE-06).
Auto-creates rows on first access (same pattern as existing settings repos).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

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

        Race-safe: the INSERT carries ``ON CONFLICT (user_id) DO NOTHING``
        so a concurrent request winning the insert does not raise
        IntegrityError — the loser re-selects the winner's committed row
        (READ COMMITTED snapshot). Without this, a racing request hit a
        UniqueViolation on ``user_token_limits_pkey`` → HTTP 500 (same
        defect class as ``ProjectAiSettingsRepository``, benchmark
        2026-09-07-clean-failed-1).

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
            # ``overrides`` has no server_default — pass it explicitly so the
            # core INSERT satisfies the NOT NULL constraint.
            stmt = (
                pg_insert(UserTokenLimits)
                .values(user_id=user_id, overrides={})
                .on_conflict_do_nothing(index_elements=["user_id"])
            )
            await self._session.execute(stmt)
            result = await self._session.execute(
                select(UserTokenLimits).where(UserTokenLimits.user_id == user_id)
            )
            limits = result.scalar_one_or_none()
            # Post-upsert the row always exists: either our INSERT landed or
            # the concurrent winner's row is committed and visible.
            assert limits is not None
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

        Race-safe: the INSERT carries ``ON CONFLICT (project_id) DO
        NOTHING`` so a concurrent request winning the insert does not
        raise IntegrityError — the loser re-selects the winner's committed
        row (READ COMMITTED snapshot). Without this, a racing request hit
        a UniqueViolation on ``project_token_limits_pkey`` → HTTP 500
        (same defect class as ``ProjectAiSettingsRepository``, benchmark
        2026-09-07-clean-failed-1).

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
            # ``overrides`` has no server_default — pass it explicitly so the
            # core INSERT satisfies the NOT NULL constraint.
            stmt = (
                pg_insert(ProjectTokenLimits)
                .values(project_id=project_id, overrides={})
                .on_conflict_do_nothing(index_elements=["project_id"])
            )
            await self._session.execute(stmt)
            result = await self._session.execute(
                select(ProjectTokenLimits).where(ProjectTokenLimits.project_id == project_id)
            )
            limits = result.scalar_one_or_none()
            # Post-upsert the row always exists: either our INSERT landed or
            # the concurrent winner's row is committed and visible.
            assert limits is not None
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
