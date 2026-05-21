"""Settings routes - user settings and project settings.

Routes are grouped by prefix ``/settings``. The router delegates
immediately to service classes - no business logic here (RULE-06).

For AI provider and settings routes, see router_ai.py.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from narrare._app.database import get_async_session
from narrare._app.dependencies import CurrentUserIdDep
from narrare.settings.repository import ProjectSettingsRepository, UserSettingsRepository
from narrare.settings.router_ai import router as ai_router
from narrare.settings.router_tones import router as tones_router
from narrare.settings.schemas import (
    ProjectSettingsResponse,
    UpdateProjectSettingsRequest,
    UpdateUserSettingsRequest,
    UserSettingsResponse,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/settings", tags=["settings"])

# Include AI sub-router (no prefix - routes already have /ai/ prefix)
router.include_router(ai_router)

# Include custom tones sub-router (no prefix - routes already have /settings/user/tones prefix)
router.include_router(tones_router)


# ---------------------------------------------------------------------------
# Existing routes: user settings, project settings
# ---------------------------------------------------------------------------


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
