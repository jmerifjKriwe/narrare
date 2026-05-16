"""Settings repository — user settings and project settings base operations.

Updated for configurable model routing to handle JSONB override columns
on project_settings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from narrare.settings.models import ProjectSettings, UserSettings

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.settings.schemas import UpdateProjectSettingsRequest, UpdateUserSettingsRequest


class UserSettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: uuid.UUID) -> UserSettings:
        result = await self._session.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
        settings = result.scalar_one_or_none()
        if not settings:
            settings = UserSettings(user_id=user_id)
            self._session.add(settings)
            await self._session.flush()
        return settings

    async def update(self, user_id: uuid.UUID, request: UpdateUserSettingsRequest) -> UserSettings:
        settings = await self.get(user_id)
        for field, value in request.model_dump(exclude_none=True).items():
            setattr(settings, field, value)
        await self._session.flush()
        await self._session.refresh(settings)
        return settings


class ProjectSettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, novel_id: uuid.UUID) -> ProjectSettings:
        result = await self._session.execute(
            select(ProjectSettings).where(ProjectSettings.novel_id == novel_id)
        )
        settings = result.scalar_one_or_none()
        if not settings:
            settings = ProjectSettings(novel_id=novel_id)
            self._session.add(settings)
            await self._session.flush()
        return settings

    async def update(
        self, novel_id: uuid.UUID, request: UpdateProjectSettingsRequest
    ) -> ProjectSettings:
        settings = await self.get(novel_id)
        for field, value in request.model_dump(exclude_none=True).items():
            setattr(settings, field, value)
        await self._session.flush()
        await self._session.refresh(settings)
        return settings
