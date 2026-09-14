"""KB consistency service dependency factory.

Model acquisition follows the per-user model-routing cascade: the factory
wires TWO cascades for the authenticated user (+ novel for project-level
overrides) — ``LLMIntent.KB_CONSISTENCY`` for the entry-internal analyzer
and ``LLMIntent.KB_WORLDBUILD`` for the reused cross-entity worldbuilding
analyzer — as ``LazyModelResolution``s (dual lazy wiring, ADR-086) and
passes them into the analyzers, which resolve on first use — never at
construction. No business logic lives here — only wiring.

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
from narrare._app.dependencies_services import (
    LazyModelResolution,
    get_model_routing_resolver,
)
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from narrare.kb.consistency_service import KBConsistencyService


async def get_consistency_service(
    novel_id: UUID,
    session: SessionDep,
    user_id: str = Depends(get_current_user_id),
) -> KBConsistencyService:
    """Create a KBConsistencyService with per-user lazy model routing.

    FastAPI dependency: novel_id comes from the route path, user_id and
    session are resolved via Depends. The models are NOT resolved here —
    both cascades (KB_CONSISTENCY and KB_WORLDBUILD) are wired as
    ``LazyModelResolution``s and resolve at the service's first use
    (ADR-086), after the novel ownership gate, so request validation
    errors surface as 422 before any routing cascade runs.
    ``ConfigurationError`` propagates loudly from the entry point when
    the user has no provider configured (kb routers are auth-mandatory;
    RULE-11).

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
    # Dual lazy wiring (ADR-086): one LazyModelResolution per intent —
    # neither cascade runs at construction; the service resolves both at
    # its first use, after the ownership gate.
    consistency_resolution = LazyModelResolution(
        lambda: resolver.resolve(LLMIntent.KB_CONSISTENCY, UUID(user_id), novel_id)
    )
    worldbuild_resolution = LazyModelResolution(
        lambda: resolver.resolve(LLMIntent.KB_WORLDBUILD, UUID(user_id), novel_id)
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
        model_resolution=consistency_resolution,
        composer=composer,
    )

    # Relationship asymmetry checker (algorithmic, no LLM)
    rel_service = get_rel_service(session)
    asymmetry_checker = RelationshipAsymmetryChecker(
        rel_repo=rel_repo,
        rel_service=rel_service,
    )

    # Worldbuilding analyzer (reused for cross-entity Phase 2); its
    # KB_WORLDBUILD cascade is wired lazily above — resolve happens at
    # the service's first use (ADR-086), never here.
    worldbuilding_cache = WorldbuildingCache(cache)
    worldbuilding_analyzer = WorldbuildingAnalyzer(
        kb_repo=kb_repo,
        rel_repo=rel_repo,
        cache=worldbuilding_cache,
        registry=registry,
        model_resolution=worldbuild_resolution,
        composer=composer,
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
