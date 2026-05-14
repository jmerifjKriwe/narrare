"""AI settings routes - provider management and AI configuration.

Split from router.py for RULE-04 compliance.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from narrare._app.database import get_async_session
from narrare._app.dependencies import CurrentUserIdDep
from narrare.settings.schemas import (
    CreateProviderRequest,
    ProjectAiSettingsResponse,
    ProviderResponse,
    UpdateProjectAiSettingsRequest,
    UpdateProviderRequest,
    UpdateUserAiSettingsRequest,
    UserAiSettingsResponse,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.settings.project_ai_settings_service import ProjectAiSettingsService
    from narrare.settings.user_ai_settings_service import UserAiSettingsService
    from narrare.settings.user_providers_service import UserProvidersService

router = APIRouter(tags=["settings"])


async def _get_providers_service(
    session: AsyncSession = Depends(get_async_session),
) -> UserProvidersService:
    from narrare.settings.user_ai_settings_repository import UserAiSettingsRepository
    from narrare.settings.user_providers_repository import UserProvidersRepository
    from narrare.settings.user_providers_service import UserProvidersService

    return UserProvidersService(
        providers_repo=UserProvidersRepository(session),
        ai_settings_repo=UserAiSettingsRepository(session),
    )


async def _get_ai_settings_service(
    session: AsyncSession = Depends(get_async_session),
) -> UserAiSettingsService:
    from narrare.settings.user_ai_settings_repository import UserAiSettingsRepository
    from narrare.settings.user_ai_settings_service import UserAiSettingsService
    from narrare.settings.user_providers_repository import UserProvidersRepository

    return UserAiSettingsService(
        ai_settings_repo=UserAiSettingsRepository(session),
        providers_repo=UserProvidersRepository(session),
    )


async def _get_project_ai_service(
    session: AsyncSession = Depends(get_async_session),
) -> ProjectAiSettingsService:
    from narrare.settings.project_ai_settings_repository import ProjectAiSettingsRepository
    from narrare.settings.project_ai_settings_service import ProjectAiSettingsService
    from narrare.settings.user_ai_settings_repository import UserAiSettingsRepository

    return ProjectAiSettingsService(
        project_ai_repo=ProjectAiSettingsRepository(session),
        user_ai_repo=UserAiSettingsRepository(session),
    )


@router.get("/ai/providers", response_model=list[ProviderResponse])
async def list_providers(
    user_id: CurrentUserIdDep,
    service: UserProvidersService = Depends(_get_providers_service),
) -> list[ProviderResponse]:
    return await service.list_providers(uuid.UUID(user_id))


@router.post("/ai/providers", response_model=ProviderResponse, status_code=201)
async def create_provider(
    request: CreateProviderRequest,
    user_id: CurrentUserIdDep,
    service: UserProvidersService = Depends(_get_providers_service),
) -> ProviderResponse:
    return await service.create_provider(uuid.UUID(user_id), request)


@router.patch("/ai/providers/{provider_id}", response_model=ProviderResponse)
async def update_provider(
    provider_id: uuid.UUID,
    request: UpdateProviderRequest,
    user_id: CurrentUserIdDep,
    service: UserProvidersService = Depends(_get_providers_service),
) -> ProviderResponse:
    return await service.update_provider(uuid.UUID(user_id), provider_id, request)


@router.delete("/ai/providers/{provider_id}", status_code=204)
async def delete_provider(
    provider_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: UserProvidersService = Depends(_get_providers_service),
) -> None:
    await service.delete_provider(uuid.UUID(user_id), provider_id)


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
