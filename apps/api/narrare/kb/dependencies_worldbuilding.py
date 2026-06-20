"""KB dependency injection — worldbuilding service factory."""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare._app.dependencies import SessionDep  # noqa: TC001 - needed at runtime for FastAPI DI

if TYPE_CHECKING:
    from narrare.kb.worldbuilding_service import WorldbuildingService


def get_worldbuilding_service(session: SessionDep) -> WorldbuildingService:
    """Create a WorldbuildingService with injected dependencies.

    Production wiring: uses ModelRegistry for LLM model, PromptComposer
    for system prompts, PromptRegistry for prompt resolution, and
    KBRepository + RelationshipRepository for data access.
    Uses Redis-backed WorldbuildingCache for 10min TTL on analysis results.
    Includes InvocationPipeline for invocation evidence (ADR-040).
    """
    from narrare._app.config import get_settings
    from narrare._app.dependencies import (
        get_composer,
        get_invocation_pipeline,
        get_model_registry,
    )
    from narrare._app.dependencies_services import (
        SystemModelCategory,
        build_system_default_config,
    )
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare.kb.worldbuilding_analyzer import WorldbuildingAnalyzer
    from narrare.kb.worldbuilding_cache import WorldbuildingCache
    from narrare.kb.worldbuilding_service import WorldbuildingService
    from narrare_core.cache.redis_client import RedisSessionCache

    registry = get_model_registry()
    composer = get_composer()
    config = build_system_default_config(SystemModelCategory.ANALYSIS)

    kb_repo = KBRepository(session)
    rel_repo = RelationshipRepository(session)

    # Redis-backed worldbuilding cache with 10min TTL
    settings = get_settings()
    redis_cache = RedisSessionCache(settings.redis_url)
    worldbuilding_cache = WorldbuildingCache(redis_cache)

    # Analyzer handles all LLM interaction + caching
    analyzer = WorldbuildingAnalyzer(
        kb_repo=kb_repo,
        rel_repo=rel_repo,
        cache=worldbuilding_cache,
        registry=registry,
        config=config,
        composer=composer,
        invocation_pipeline=get_invocation_pipeline(),
    )

    return WorldbuildingService(
        analyzer=analyzer,
        rel_repo=rel_repo,
        cache=worldbuilding_cache,
        invocation_pipeline=get_invocation_pipeline(),
    )
