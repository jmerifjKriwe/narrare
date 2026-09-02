"""KB dependency injection — worldbuilding service factory.

Model acquisition follows the per-user model-routing cascade: the factory
resolves ``LLMIntent.KB_WORLDBUILD`` for the authenticated user (+ novel
for project-level overrides) and passes the resolved config + credentials
into the analyzer. No business logic lives here — only wiring.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import Depends

from narrare._app.dependencies import (
    SessionDep,
    get_current_user_id,
)
from narrare._app.dependencies_services import get_model_routing_resolver
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from narrare.kb.worldbuilding_service import WorldbuildingService


async def get_worldbuilding_service(
    novel_id: UUID,
    session: SessionDep,
    user_id: str = Depends(get_current_user_id),
) -> WorldbuildingService:
    """Create a WorldbuildingService with per-user resolved model routing.

    FastAPI dependency: novel_id comes from the route path, user_id and
    session are resolved via Depends. The model is resolved through the
    per-user cascade; ``ConfigurationError`` propagates when the user has
    no provider configured (kb routers are auth-mandatory).

    Production wiring: uses ModelRegistry for LLM model, PromptComposer
    for system prompts, PromptRegistry for prompt resolution, and
    KBRepository + RelationshipRepository for data access.
    Uses the in-memory WorldbuildingCache for 10min TTL on analysis results.
    Includes InvocationPipeline for invocation evidence (ADR-040).
    """
    from narrare._app.dependencies import (
        get_composer,
        get_invocation_pipeline,
        get_model_registry,
    )
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare.kb.worldbuilding_analyzer import WorldbuildingAnalyzer
    from narrare.kb.worldbuilding_cache import WorldbuildingCache
    from narrare.kb.worldbuilding_service import WorldbuildingService
    from narrare_core.cache import InMemorySessionCache

    resolver = get_model_routing_resolver(session)
    resolved = await resolver.resolve(
        LLMIntent.KB_WORLDBUILD,
        UUID(user_id),
        novel_id,
    )

    registry = get_model_registry()
    composer = get_composer()

    kb_repo = KBRepository(session)
    rel_repo = RelationshipRepository(session)

    # In-memory worldbuilding cache with 10min TTL (ADR-080)
    cache = InMemorySessionCache()
    worldbuilding_cache = WorldbuildingCache(cache)

    # Analyzer handles all LLM interaction + caching
    analyzer = WorldbuildingAnalyzer(
        kb_repo=kb_repo,
        rel_repo=rel_repo,
        cache=worldbuilding_cache,
        registry=registry,
        config=resolved.config,
        composer=composer,
        invocation_pipeline=get_invocation_pipeline(),
        api_key=resolved.api_key,
        base_url=resolved.base_url,
    )

    return WorldbuildingService(
        analyzer=analyzer,
        rel_repo=rel_repo,
        cache=worldbuilding_cache,
        invocation_pipeline=get_invocation_pipeline(),
    )
