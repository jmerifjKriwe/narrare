"""Generation routes — thin, delegates immediately to name generator service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from narrare._app.dependencies import CurrentUserIdDep
from narrare.generation.schemas import NameGenerateRequest, NameGenerateResponse

if TYPE_CHECKING:
    from narrare.generation.name_service import NameGeneratorService

router = APIRouter(prefix="/generation", tags=["generation"])


async def _get_service() -> NameGeneratorService:
    """Factory for NameGeneratorService."""
    from narrare._app.dependencies import get_composer, get_gateway
    from narrare.generation.name_service import NameGeneratorService
    from narrare_core.llm.intents import ResolvedModelConfig

    gateway = get_gateway()
    composer = get_composer()
    config = ResolvedModelConfig(
        provider_name="anthropic",
        model_id="claude-haiku-3-5-20241022",
        temperature=0.8,
        max_tokens=2000,
    )
    return NameGeneratorService(gateway=gateway, composer=composer, config=config)


@router.post("/names", response_model=NameGenerateResponse)
async def generate_names(
    request: NameGenerateRequest,
    user_id: CurrentUserIdDep,
    service: NameGeneratorService = Depends(_get_service),
) -> NameGenerateResponse:
    """Generate names based on type, culture, and preferences."""
    return await service.generate_names(request)
