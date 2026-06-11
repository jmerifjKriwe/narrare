"""AI provider CRUD routes — provider management endpoints.

Split from router_ai.py for RULE-04 compliance.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from narrare._app.dependencies import CurrentUserIdDep, SessionDep
from narrare.settings.schemas import (
    CreateProviderRequest,
    ProviderResponse,
    UpdateProviderRequest,
)

if TYPE_CHECKING:
    from narrare.settings.user_providers_service import UserProvidersService

router = APIRouter(tags=["settings"])


async def _get_providers_service(
    session: SessionDep,
) -> UserProvidersService:
    from narrare.settings.user_ai_settings_repository import UserAiSettingsRepository
    from narrare.settings.user_providers_repository import UserProvidersRepository
    from narrare.settings.user_providers_service import UserProvidersService

    return UserProvidersService(
        providers_repo=UserProvidersRepository(session),
        ai_settings_repo=UserAiSettingsRepository(session),
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
