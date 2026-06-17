"""KB consistency service dependency factory."""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare._app.dependencies import SessionDep  # noqa: TC001 — runtime DI

if TYPE_CHECKING:
    from narrare.kb.consistency_service import KBConsistencyService


def get_consistency_service(session: SessionDep) -> KBConsistencyService:
    """Create a KBConsistencyService with injected dependencies.

    Production wiring: uses ModelRegistry for LLM model, PromptComposer
    for system prompts, PromptRegistry for prompt resolution, and
    KBRepository + RelationshipRepository for data access.
    Reuses WorldbuildingAnalyzer for cross-entity Phase 2 consistency.
    Uses Redis-backed ConsistencyCache for 10min TTL on results.
    Includes InvocationPipeline for invocation evidence (ADR-040).
    """
    from narrare._app.config import get_settings
    from narrare._app.dependencies import (
        get_composer,
        get_invocation_pipeline,
        get_model_registry,
    )
    from narrare._app.dependencies_services import build_system_default_config
    from narrare.kb.consistency_analyzer import KBConsistencyAnalyzer
    from narrare.kb.consistency_cache import ConsistencyCache
    from narrare.kb.consistency_service import KBConsistencyService
    from narrare.kb.dependencies import get_rel_service
    from narrare.kb.relationship_asymmetry import RelationshipAsymmetryChecker
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare.kb.worldbuilding_analyzer import WorldbuildingAnalyzer
    from narrare.kb.worldbuilding_cache import WorldbuildingCache
    from narrare_core.cache.redis_client import RedisSessionCache

    registry = get_model_registry()
    composer = get_composer()
    config = build_system_default_config("analysis")

    kb_repo = KBRepository(session)
    rel_repo = RelationshipRepository(session)

    # Redis-backed consistency cache with 10min TTL
    settings = get_settings()
    redis_cache = RedisSessionCache(settings.redis_url)
    consistency_cache = ConsistencyCache(redis_cache)

    # Entry-internal analyzer (LLM per entry)
    consistency_analyzer = KBConsistencyAnalyzer(
        kb_repo=kb_repo,
        registry=registry,
        config=config,
        composer=composer,
    )

    # Relationship asymmetry checker (algorithmic, no LLM)
    rel_service = get_rel_service(session)
    asymmetry_checker = RelationshipAsymmetryChecker(
        rel_repo=rel_repo,
        rel_service=rel_service,
    )

    # Worldbuilding analyzer (reused for cross-entity Phase 2)
    worldbuilding_cache = WorldbuildingCache(redis_cache)
    worldbuilding_analyzer = WorldbuildingAnalyzer(
        kb_repo=kb_repo,
        rel_repo=rel_repo,
        cache=worldbuilding_cache,
        registry=registry,
        config=config,
        composer=composer,
    )

    return KBConsistencyService(
        analyzer=consistency_analyzer,
        asymmetry_checker=asymmetry_checker,
        worldbuilding_analyzer=worldbuilding_analyzer,
        kb_repo=kb_repo,
        rel_repo=rel_repo,
        cache=consistency_cache,
        invocation_pipeline=get_invocation_pipeline(),
    )
