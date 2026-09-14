"""Generation routes — thin, delegates immediately to name generator service."""

from __future__ import annotations

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
from narrare._app.dependencies_services import (
    LazyModelResolution,
    get_model_routing_resolver,
)
from narrare._app.rate_limits import AI_LIGHT_LIMITER
from narrare.generation.schemas import NameGenerateRequest, NameGenerateResponse
from narrare.novels.ownership import verify_novel_owned

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.generation.name_service import NameGeneratorService

router = APIRouter(prefix="/generation", tags=["generation"])


async def _get_service(
    session: AsyncSession,
    user_id: str,
    project_id: UUID,
) -> NameGeneratorService:
    """Factory for NameGeneratorService — defers model resolution (ADR-086).

    Ownership first (IDOR remediation S12b): the project is gated on the
    caller BEFORE the model-routing cascade is wired — foreign and unknown
    projects are indistinguishable (``NotFoundError`` → 404). The service
    re-checks the same gate at entry (Pattern B), so the gate holds
    regardless of wiring.

    The per-user cascade (``LLMIntent.NAME_GENERATE`` for the caller, with
    the project tier) resolves LAZILY via ``LazyModelResolution`` on the
    service's first ``ensure_resolved()`` — never at construction
    (ADR-086). This REST endpoint has no SSE pre-header concern: first use
    happens inside ``generate_names`` after body validation and the
    ownership gates, so ``ConfigurationError`` surfaces as a loud 400.
    """
    from narrare.generation.name_service import NameGeneratorService
    from narrare.kb.repository import KBRepository
    from narrare.novels.repository import NovelRepository
    from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
    from narrare_core.llm.intents import LLMIntent

    novel_repo = NovelRepository(session)
    await verify_novel_owned(novel_repo, project_id, UUID(user_id))

    resolver = get_model_routing_resolver(session)
    assert isinstance(resolver, ModelRoutingResolverImpl)
    model_resolution = LazyModelResolution(
        lambda: resolver.resolve(LLMIntent.NAME_GENERATE, UUID(user_id), project_id)
    )

    registry = get_model_registry()
    composer = get_composer()
    kb_repo = KBRepository(session)
    return NameGeneratorService(
        registry=registry,
        composer=composer,
        model_resolution=model_resolution,
        novel_repo=novel_repo,
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
