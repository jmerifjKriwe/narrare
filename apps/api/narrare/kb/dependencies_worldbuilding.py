"""KB dependency injection — worldbuilding service factory.

Model acquisition follows the per-user model-routing cascade: the factory
wires the ``LLMIntent.KB_WORLDBUILD`` cascade for the authenticated user
(+ novel for project-level overrides) as a ``LazyModelResolution`` and
passes it into the analyzer, which resolves it on first use (ADR-086) —
never at construction. No business logic lives here — only wiring.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import Depends

from narrare._app.dependencies import (
    SessionDep,
    get_current_user_id,
)
from narrare._app.dependencies_services import (
    LazyModelResolution,
    get_model_routing_resolver,
)
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from narrare.kb.worldbuilding_service import WorldbuildingService


async def get_worldbuilding_service(
    novel_id: UUID,
    session: SessionDep,
    user_id: str = Depends(get_current_user_id),
) -> WorldbuildingService:
    """Create a WorldbuildingService with per-user lazy model routing.

    FastAPI dependency: novel_id comes from the route path, user_id and
    session are resolved via Depends. The model is NOT resolved here —
    the per-user cascade (project intent → project category → user
    intent → user category → user default) is wired as a
    ``LazyModelResolution`` and resolves on the analyzer's first use
    (ADR-086), so request validation errors surface as 422 before any
    routing cascade runs. ``ConfigurationError`` propagates loudly from
    the entry point when the user has no provider configured (kb routers
    are auth-mandatory; RULE-11). The apply endpoint consumes no model
    resolution at all (pure validation + relationship writes).

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
    from narrare.novels.repository import NovelRepository
    from narrare_core.cache import InMemorySessionCache

    resolver = get_model_routing_resolver(session)
    model_resolution = LazyModelResolution(
        lambda: resolver.resolve(LLMIntent.KB_WORLDBUILD, UUID(user_id), novel_id)
    )

    registry = get_model_registry()
    composer = get_composer()

    kb_repo = KBRepository(session)
    rel_repo = RelationshipRepository(session)
    novel_repo = NovelRepository(session)

    # In-memory worldbuilding cache with 10min TTL (ADR-080)
    cache = InMemorySessionCache()
    worldbuilding_cache = WorldbuildingCache(cache)

    # Analyzer handles all LLM interaction + caching; the model routing
    # cascade resolves on the analyzer's first use (ADR-086), never here.
    analyzer = WorldbuildingAnalyzer(
        kb_repo=kb_repo,
        rel_repo=rel_repo,
        cache=worldbuilding_cache,
        registry=registry,
        model_resolution=model_resolution,
        composer=composer,
        invocation_pipeline=get_invocation_pipeline(),
    )

    return WorldbuildingService(
        analyzer=analyzer,
        rel_repo=rel_repo,
        entry_repo=kb_repo,
        cache=worldbuilding_cache,
        novel_repo=novel_repo,
        invocation_pipeline=get_invocation_pipeline(),
    )
