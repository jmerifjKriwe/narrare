"""Settings routes - user settings and project settings.

Routes are grouped by prefix ``/settings``. The router delegates
immediately to service classes - no business logic here (RULE-06).

For AI provider and settings routes, see router_ai.py.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from narrare._app.dependencies import CurrentUserIdDep, SessionDep
from narrare.settings.dependencies import verify_novel_owned
from narrare.settings.models_router import router as models_router
from narrare.settings.repository import ProjectSettingsRepository, UserSettingsRepository
from narrare.settings.router_ai import router as ai_router
from narrare.settings.router_tones import router as tones_router
from narrare.settings.schemas import (
    ProjectSettingsResponse,
    UpdateProjectSettingsRequest,
    UpdateUserSettingsRequest,
    UserSettingsResponse,
)
from narrare.settings.token_limits.router import router as token_limits_router

router = APIRouter(prefix="/settings", tags=["settings"])

# Include AI sub-router (no prefix - routes already have /ai/ prefix)
router.include_router(ai_router)

# Include custom tones sub-router (no prefix - routes already have /settings/user/tones prefix)
router.include_router(tones_router)

# Include models sub-router (no prefix - routes already have /models/ prefix)
router.include_router(models_router)

# Include token limits sub-router — it carries the "/token-limits" sub-path
# prefix; the parent's "/settings" prefix is prepended on inclusion, so the
# routes mount at /settings/token-limits/… (single prefix, IDOR S11b fix).
router.include_router(token_limits_router)


# ---------------------------------------------------------------------------
# Existing routes: user settings, project settings
# ---------------------------------------------------------------------------


@router.get("/user", response_model=UserSettingsResponse)
async def get_user_settings(
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> UserSettingsResponse:
    repo = UserSettingsRepository(session)
    settings = await repo.get(uuid.UUID(user_id))
    return UserSettingsResponse.model_validate(settings)


@router.patch("/user", response_model=UserSettingsResponse)
async def update_user_settings(
    request: UpdateUserSettingsRequest,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> UserSettingsResponse:
    repo = UserSettingsRepository(session)
    settings = await repo.update(uuid.UUID(user_id), request)
    return UserSettingsResponse.model_validate(settings)


@router.get("/novels/{novel_id}", response_model=ProjectSettingsResponse)
async def get_project_settings(
    novel_id: uuid.UUID,
    session: SessionDep,
    _: None = Depends(verify_novel_owned),
) -> ProjectSettingsResponse:
    # Ownership is enforced by the verify_novel_owned dependency BEFORE
    # this handler runs — critical because ProjectSettingsRepository.get
    # auto-creates a row on first read (IDOR remediation S11a).
    repo = ProjectSettingsRepository(session)
    settings = await repo.get(novel_id)
    return ProjectSettingsResponse.model_validate(settings)


@router.patch("/novels/{novel_id}", response_model=ProjectSettingsResponse)
async def update_project_settings(
    novel_id: uuid.UUID,
    request: UpdateProjectSettingsRequest,
    session: SessionDep,
    _: None = Depends(verify_novel_owned),
) -> ProjectSettingsResponse:
    # Same gate-first ordering as GET above (IDOR remediation S11a).
    repo = ProjectSettingsRepository(session)
    settings = await repo.update(novel_id, request)
    return ProjectSettingsResponse.model_validate(settings)
