"""Setup Wizard routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from narrare._app.database import get_async_session
from narrare._app.dependencies import CurrentUserIdDep
from narrare.novels.repository import NovelRepository
from narrare.settings.repository import ProjectSettingsRepository, UserSettingsRepository
from narrare.settings.user_ai_settings_repository import UserAiSettingsRepository
from narrare.settings.user_providers_repository import UserProvidersRepository
from narrare.setup.demo_loader import DemoLoader
from narrare.setup.provider_service import ProviderService
from narrare.setup.schemas import (
    AIProvider,
    AvailableModelsResponse,
    CompleteSetupRequest,
    CompleteSetupResponse,
    Step1LocationRequest,
    Step1LocationResponse,
    Step2NovelRequest,
    Step2NovelResponse,
    Step3StarterRequest,
    Step3StarterResponse,
    Step4ProviderRequest,
    Step4ProviderResponse,
)
from narrare.setup.service import SetupService

from .router_demos import router as demo_router

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/setup", tags=["setup"])


router.include_router(demo_router)


def _get_service(
    session: AsyncSession = Depends(get_async_session),
) -> SetupService:
    return SetupService(
        session=session,
        novel_repo=NovelRepository(session),
        user_settings_repo=UserSettingsRepository(session),
        project_settings_repo=ProjectSettingsRepository(session),
        provider_service=ProviderService(),
        demo_loader=DemoLoader(session),
        providers_repo=UserProvidersRepository(session),
        ai_settings_repo=UserAiSettingsRepository(session),
    )


# ---------------------------------------------------------------------------
# Step validation endpoints
# ---------------------------------------------------------------------------


@router.post("/validate/step-1", response_model=Step1LocationResponse)
async def validate_step1(
    request: Step1LocationRequest,
    service: SetupService = Depends(_get_service),
) -> Step1LocationResponse:
    """Validate Step 1: Location and project name."""
    return await service.validate_step1(request)


@router.post("/validate/step-2", response_model=Step2NovelResponse)
async def validate_step2(
    request: Step2NovelRequest,
    service: SetupService = Depends(_get_service),
) -> Step2NovelResponse:
    """Validate Step 2: Novel metadata."""
    return await service.validate_step2(request)


@router.post("/validate/step-3", response_model=Step3StarterResponse)
async def validate_step3(
    request: Step3StarterRequest,
    service: SetupService = Depends(_get_service),
) -> Step3StarterResponse:
    """Validate Step 3: Starter content selection."""
    return await service.validate_step3(request)


@router.post("/validate/step-4", response_model=Step4ProviderResponse)
async def validate_step4(
    request: Step4ProviderRequest,
    service: SetupService = Depends(_get_service),
) -> Step4ProviderResponse:
    """Validate Step 4: AI provider connection (real API call)."""
    return await service.validate_step4(request)


# ---------------------------------------------------------------------------
# Provider model discovery
# ---------------------------------------------------------------------------


@router.get("/providers/{provider}/models", response_model=AvailableModelsResponse)
async def list_provider_models(
    provider: AIProvider,
    api_key: str = "",
    ollama_url: str = "http://localhost:11434",
) -> AvailableModelsResponse:
    """
    Fetch available models for a provider.

    Falls back to a curated list if the provider API is unreachable.
    No auth required — called before login during setup.
    """
    svc = ProviderService()
    return await svc.list_models(provider, api_key, ollama_url)


# ---------------------------------------------------------------------------
# Complete setup
# ---------------------------------------------------------------------------


@router.post("/complete", response_model=CompleteSetupResponse)
async def complete_setup(
    request: CompleteSetupRequest,
    user_id: CurrentUserIdDep,
    service: SetupService = Depends(_get_service),
) -> CompleteSetupResponse:
    """
    Complete the wizard — create novel, load demo content, save settings.

    Requires authentication. The user must have registered before completing setup.
    """
    return await service.complete(user_id, request.state)
