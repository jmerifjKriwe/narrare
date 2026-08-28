"""Generation routes — thin, delegates immediately to name generator service."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends

from narrare._app.dependencies import (
    CurrentUserIdDep,
    SessionDep,
    get_composer,
    get_invocation_pipeline,
    get_model_registry,
)
from narrare._app.dependencies_services import get_model_routing_resolver
from narrare._app.rate_limits import AI_LIGHT_LIMITER
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

    Ownership first (IDOR remediation S12b): the project is gated on the
    caller BEFORE the model-routing resolver reads the project's AI settings
    — foreign and unknown projects are indistinguishable (``NotFoundError``
    → 404). The service re-checks the same gate at entry (Pattern B), so
    the gate holds regardless of wiring.

    Uses ModelRoutingResolverImpl to look up the user's provider and model
    for the NAME_GENERATE intent instead of hardcoding them.
    """
    from narrare.generation.name_service import NameGeneratorService
    from narrare.kb.repository import KBRepository
    from narrare.novels.repository import NovelRepository
    from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
    from narrare_core.llm.intents import LLMIntent
    from narrare_core.shared.errors import NotFoundError

    novel_repo = NovelRepository(session)
    novel = await novel_repo.get_by_id(project_id, UUID(user_id))
    if novel is None:
        raise NotFoundError("Novel", identifier=str(project_id))

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
        novel_repo=novel_repo,
        api_key=resolved.api_key,
        base_url=resolved.base_url,
        kb_repo=kb_repo,
        invocation_pipeline=get_invocation_pipeline(),
    )


@router.post(
    "/names", response_model=NameGenerateResponse, dependencies=[Depends(AI_LIGHT_LIMITER)]
)
async def generate_names(
    request: NameGenerateRequest,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> NameGenerateResponse:
    """Generate names based on type, name_style, and preferences."""
    service = await _get_service(session=session, user_id=user_id, project_id=request.project_id)
    return await service.generate_names(request, UUID(user_id))
