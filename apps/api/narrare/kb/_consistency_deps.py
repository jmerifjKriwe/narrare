"""KB consistency service dependency factory.

Model acquisition follows the per-user model-routing cascade: the factory
resolves TWO configs for the authenticated user (+ novel for project-level
overrides) — ``LLMIntent.KB_CONSISTENCY`` for the entry-internal analyzer
and ``LLMIntent.KB_WORLDBUILD`` for the reused cross-entity worldbuilding
analyzer — and passes the resolved configs + credentials into them. No
business logic lives here — only wiring.

Note: the legacy wiring set no temperature override on either config
(unlike ``consistency/deps.py``), so none is preserved here — the resolved
cascade config is passed through as-is.
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
    from narrare.kb.consistency_service import KBConsistencyService


async def get_consistency_service(
    novel_id: UUID,
    session: SessionDep,
    user_id: str = Depends(get_current_user_id),
) -> KBConsistencyService:
    """Create a KBConsistencyService with per-user resolved model routing.

    FastAPI dependency: novel_id comes from the route path, user_id and
    session are resolved via Depends. The models are resolved through the
    per-user cascade; ``ConfigurationError`` propagates when the user has
    no provider configured (kb routers are auth-mandatory).

    Production wiring: uses ModelRegistry for LLM model, PromptComposer
    for system prompts, PromptRegistry for prompt resolution, and
    KBRepository + RelationshipRepository for data access.
    Reuses WorldbuildingAnalyzer for cross-entity Phase 2 consistency.
    Uses the in-memory ConsistencyCache for 10min TTL on results.
    Includes InvocationPipeline for invocation evidence (ADR-040).
    """
    from narrare._app.dependencies import (
        get_composer,
        get_invocation_pipeline,
        get_model_registry,
    )
    from narrare.kb._feedback_memory_deps import (
        get_consistency_feedback_memory_instance,
    )
    from narrare.kb.consistency_analyzer import KBConsistencyAnalyzer
    from narrare.kb.consistency_cache import ConsistencyCache
    from narrare.kb.consistency_service import KBConsistencyService
    from narrare.kb.dependencies import get_rel_service
    from narrare.kb.relationship_asymmetry import RelationshipAsymmetryChecker
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare.kb.worldbuilding_analyzer import WorldbuildingAnalyzer
    from narrare.kb.worldbuilding_cache import WorldbuildingCache
    from narrare.novels.repository import NovelRepository
    from narrare_core.cache import InMemorySessionCache

    resolver = get_model_routing_resolver(session)
    consistency_resolved = await resolver.resolve(
        LLMIntent.KB_CONSISTENCY,
        UUID(user_id),
        novel_id,
    )
    worldbuild_resolved = await resolver.resolve(
        LLMIntent.KB_WORLDBUILD,
        UUID(user_id),
        novel_id,
    )

    registry = get_model_registry()
    composer = get_composer()

    kb_repo = KBRepository(session)
    rel_repo = RelationshipRepository(session)
    novel_repo = NovelRepository(session)

    # In-memory consistency cache with 10min TTL (ADR-080). Shared with the
    # worldbuilding cache below (both consume SessionCacheProtocol).
    cache = InMemorySessionCache()
    consistency_cache = ConsistencyCache(cache)

    # Entry-internal analyzer (LLM per entry)
    consistency_analyzer = KBConsistencyAnalyzer(
        kb_repo=kb_repo,
        registry=registry,
        config=consistency_resolved.config,
        composer=composer,
        api_key=consistency_resolved.api_key,
        base_url=consistency_resolved.base_url,
    )

    # Relationship asymmetry checker (algorithmic, no LLM)
    rel_service = get_rel_service(session)
    asymmetry_checker = RelationshipAsymmetryChecker(
        rel_repo=rel_repo,
        rel_service=rel_service,
    )

    # Worldbuilding analyzer (reused for cross-entity Phase 2)
    worldbuilding_cache = WorldbuildingCache(cache)
    worldbuilding_analyzer = WorldbuildingAnalyzer(
        kb_repo=kb_repo,
        rel_repo=rel_repo,
        cache=worldbuilding_cache,
        registry=registry,
        config=worldbuild_resolved.config,
        composer=composer,
        api_key=worldbuild_resolved.api_key,
        base_url=worldbuild_resolved.base_url,
    )

    return KBConsistencyService(
        analyzer=consistency_analyzer,
        asymmetry_checker=asymmetry_checker,
        worldbuilding_analyzer=worldbuilding_analyzer,
        kb_repo=kb_repo,
        rel_repo=rel_repo,
        novel_repo=novel_repo,
        cache=consistency_cache,
        invocation_pipeline=get_invocation_pipeline(),
        feedback_memory=get_consistency_feedback_memory_instance(),
    )
