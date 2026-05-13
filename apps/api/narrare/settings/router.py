"""Settings routes."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from narrare._app.database import get_async_session
from narrare._app.dependencies import CurrentUserIdDep
from narrare.settings.repository import ProjectSettingsRepository, UserSettingsRepository
from narrare.settings.schemas import (
    ProjectSettingsResponse,
    UpdateProjectSettingsRequest,
    UpdateUserSettingsRequest,
    UserSettingsResponse,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/user", response_model=UserSettingsResponse)
async def get_user_settings(
    user_id: CurrentUserIdDep,
    session: AsyncSession = Depends(get_async_session),
) -> UserSettingsResponse:
    repo = UserSettingsRepository(session)
    settings = await repo.get(uuid.UUID(user_id))
    return UserSettingsResponse.model_validate(settings)


@router.patch("/user", response_model=UserSettingsResponse)
async def update_user_settings(
    request: UpdateUserSettingsRequest,
    user_id: CurrentUserIdDep,
    session: AsyncSession = Depends(get_async_session),
) -> UserSettingsResponse:
    repo = UserSettingsRepository(session)
    settings = await repo.update(uuid.UUID(user_id), request)
    return UserSettingsResponse.model_validate(settings)


@router.get("/novels/{novel_id}", response_model=ProjectSettingsResponse)
async def get_project_settings(
    novel_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    session: AsyncSession = Depends(get_async_session),
) -> ProjectSettingsResponse:
    repo = ProjectSettingsRepository(session)
    settings = await repo.get(novel_id)
    return ProjectSettingsResponse.model_validate(settings)


@router.patch("/novels/{novel_id}", response_model=ProjectSettingsResponse)
async def update_project_settings(
    novel_id: uuid.UUID,
    request: UpdateProjectSettingsRequest,
    user_id: CurrentUserIdDep,
    session: AsyncSession = Depends(get_async_session),
) -> ProjectSettingsResponse:
    repo = ProjectSettingsRepository(session)
    settings = await repo.update(novel_id, request)
    return ProjectSettingsResponse.model_validate(settings)
