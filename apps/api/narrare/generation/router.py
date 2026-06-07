"""Generation routes — thin, delegates immediately to name generator service."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter

from narrare._app.dependencies import (
    CurrentUserIdDep,
    SessionDep,
    get_composer,
    get_model_registry,
)
from narrare._app.dependencies_services import get_model_routing_resolver
from narrare.generation.schemas import NameGenerateRequest, NameGenerateResponse

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.generation.name_service import NameGeneratorService

router = APIRouter(prefix="/generation", tags=["generation"])


async def _get_service(
    session: AsyncSession,
    user_id: str,
    project_id: UUID,
) -> NameGeneratorService:
    """Factory for NameGeneratorService — resolves user's configured model.

    Uses ModelRoutingResolverImpl to look up the user's provider and model
    for the NAME_GENERATE intent instead of hardcoding them.
    """
    from narrare.generation.name_service import NameGeneratorService
    from narrare.kb.repository import KBRepository
    from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
    from narrare_core.llm.intents import LLMIntent

    resolver = get_model_routing_resolver(session)
    assert isinstance(resolver, ModelRoutingResolverImpl)
    resolved = await resolver.resolve(LLMIntent.NAME_GENERATE, UUID(user_id), project_id)

    # Layer generation-specific defaults on top of resolved config
    config = replace(resolved.config, temperature=0.8, max_tokens=2000)

    registry = get_model_registry()
    composer = get_composer()
    kb_repo = KBRepository(session)
    return NameGeneratorService(
        registry=registry,
        composer=composer,
        config=config,
        api_key=resolved.api_key,
        base_url=resolved.base_url,
        kb_repo=kb_repo,
    )


@router.post("/names", response_model=NameGenerateResponse)
async def generate_names(
    request: NameGenerateRequest,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> NameGenerateResponse:
    """Generate names based on type, name_style, and preferences."""
    service = await _get_service(session=session, user_id=user_id, project_id=request.project_id)
    return await service.generate_names(request)
