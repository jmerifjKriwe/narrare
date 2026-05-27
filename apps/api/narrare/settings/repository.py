"""Settings repository — user settings and project settings base operations.

Updated for configurable model routing to handle JSONB override columns
on project_settings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from narrare._app.base_repository import BaseRepository
from narrare.settings.models import ProjectSettings, UserSettings

if TYPE_CHECKING:
    import uuid

    from narrare.settings.schemas import UpdateProjectSettingsRequest, UpdateUserSettingsRequest

logger = structlog.get_logger(__name__)


class UserSettingsRepository(BaseRepository):
    async def get(self, user_id: uuid.UUID) -> UserSettings:
        result = await self._session.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
        settings = result.scalar_one_or_none()
        if settings is not None:
            return settings
        # Race-safe insert: concurrent requests may both see None and
        # attempt INSERT — catch IntegrityError and re-select the winner.
        settings = UserSettings(user_id=user_id)
        self._session.add(settings)
        try:
            await self._flush_and_refresh(settings)
        except IntegrityError:
            logger.debug("user_settings_concurrent_create", user_id=str(user_id))
            await self._session.rollback()
            result = await self._session.execute(
                select(UserSettings).where(UserSettings.user_id == user_id)
            )
            settings = result.scalar_one_or_none()
            if settings is None:
                raise
        return settings

    async def update(self, user_id: uuid.UUID, request: UpdateUserSettingsRequest) -> UserSettings:
        settings = await self.get(user_id)
        for field, value in request.model_dump(exclude_none=True).items():
            setattr(settings, field, value)
        await self._flush_and_refresh(settings)
        return settings


class ProjectSettingsRepository(BaseRepository):
    async def get(self, novel_id: uuid.UUID) -> ProjectSettings:
        result = await self._session.execute(
            select(ProjectSettings).where(ProjectSettings.novel_id == novel_id)
        )
        settings = result.scalar_one_or_none()
        if settings is not None:
            return settings
        # Race-safe insert: concurrent requests may both see None and
        # attempt INSERT — catch IntegrityError and re-select the winner.
        settings = ProjectSettings(novel_id=novel_id)
        self._session.add(settings)
        try:
            await self._flush_and_refresh(settings)
        except IntegrityError:
            logger.debug("project_settings_concurrent_create", novel_id=str(novel_id))
            await self._session.rollback()
            result = await self._session.execute(
                select(ProjectSettings).where(ProjectSettings.novel_id == novel_id)
            )
            settings = result.scalar_one_or_none()
            if settings is None:
                raise
        return settings

    async def update(
        self, novel_id: uuid.UUID, request: UpdateProjectSettingsRequest
    ) -> ProjectSettings:
        settings = await self.get(novel_id)
        for field, value in request.model_dump(exclude_none=True).items():
            setattr(settings, field, value)
        await self._flush_and_refresh(settings)
        return settings
