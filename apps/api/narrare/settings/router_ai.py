"""AI settings routes — AI configuration and model listing.

Split from router.py for RULE-04 compliance.
Provider CRUD routes are in router_ai_providers.py.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from narrare._app.dependencies import CurrentUserIdDep, SessionDep
from narrare.settings.router_ai_providers import router as providers_router
from narrare.settings.schemas import (
    ProjectAiSettingsResponse,
    UpdateProjectAiSettingsRequest,
    UpdateUserAiSettingsRequest,
    UserAiSettingsResponse,
)
from narrare.setup.schemas import AvailableModelsResponse

if TYPE_CHECKING:
    from narrare.settings.project_ai_settings_service import ProjectAiSettingsService
    from narrare.settings.user_ai_settings_service import UserAiSettingsService
    from narrare.settings.user_provider_models_service import UserProviderModelsService

router = APIRouter(tags=["settings"])

# Include provider CRUD sub-router (no prefix — routes already have /ai/providers)
router.include_router(providers_router)


async def _get_provider_models_service(
    session: SessionDep,
) -> UserProviderModelsService:
    from narrare.settings.user_provider_models_service import UserProviderModelsService
    from narrare.settings.user_providers_repository import UserProvidersRepository

    return UserProviderModelsService(
        providers_repo=UserProvidersRepository(session),
    )


async def _get_ai_settings_service(
    session: SessionDep,
) -> UserAiSettingsService:
    from narrare.settings.user_ai_settings_repository import UserAiSettingsRepository
    from narrare.settings.user_ai_settings_service import UserAiSettingsService
    from narrare.settings.user_providers_repository import UserProvidersRepository

    return UserAiSettingsService(
        ai_settings_repo=UserAiSettingsRepository(session),
        providers_repo=UserProvidersRepository(session),
    )


async def _get_project_ai_service(
    session: SessionDep,
) -> ProjectAiSettingsService:
    from narrare.settings.project_ai_settings_repository import ProjectAiSettingsRepository
    from narrare.settings.project_ai_settings_service import ProjectAiSettingsService
    from narrare.settings.user_ai_settings_repository import UserAiSettingsRepository

    return ProjectAiSettingsService(
        project_ai_repo=ProjectAiSettingsRepository(session),
        user_ai_repo=UserAiSettingsRepository(session),
    )


@router.get("/ai/providers/{provider_id}/models", response_model=AvailableModelsResponse)
async def get_provider_models(
    provider_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: UserProviderModelsService = Depends(_get_provider_models_service),
) -> AvailableModelsResponse:
    return await service.get_provider_models(uuid.UUID(user_id), provider_id)


@router.get("/ai", response_model=UserAiSettingsResponse)
async def get_user_ai_settings(
    user_id: CurrentUserIdDep,
    service: UserAiSettingsService = Depends(_get_ai_settings_service),
) -> UserAiSettingsResponse:
    return await service.get_settings(uuid.UUID(user_id))


@router.patch("/ai", response_model=UserAiSettingsResponse)
async def update_user_ai_settings(
    request: UpdateUserAiSettingsRequest,
    user_id: CurrentUserIdDep,
    service: UserAiSettingsService = Depends(_get_ai_settings_service),
) -> UserAiSettingsResponse:
    return await service.update_settings(uuid.UUID(user_id), request)


@router.get("/ai/novels/{novel_id}", response_model=ProjectAiSettingsResponse)
async def get_project_ai_settings(
    novel_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: ProjectAiSettingsService = Depends(_get_project_ai_service),
) -> ProjectAiSettingsResponse:
    return await service.get_settings(uuid.UUID(user_id), novel_id)


@router.patch("/ai/novels/{novel_id}", response_model=ProjectAiSettingsResponse)
async def update_project_ai_settings(
    novel_id: uuid.UUID,
    request: UpdateProjectAiSettingsRequest,
    user_id: CurrentUserIdDep,
    service: ProjectAiSettingsService = Depends(_get_project_ai_service),
) -> ProjectAiSettingsResponse:
    return await service.update_settings(uuid.UUID(user_id), novel_id, request)
