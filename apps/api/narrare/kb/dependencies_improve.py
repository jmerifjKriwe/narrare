"""KB dependency injection — improve service factory."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from narrare._app.dependencies import SessionDep  # noqa: TC001 - needed at runtime for FastAPI DI

if TYPE_CHECKING:
    from narrare.kb.improve_service import KBImproveService
    from narrare_core.embeddings.store import EmbeddingStoreProtocol


def get_kb_improve_service(session: SessionDep) -> KBImproveService:
    """Create a KBImproveService with injected dependencies.

    Production wiring: uses ModelRegistry for LLM model, PromptComposer
    for system prompts, ProactiveContextService for world context,
    and KBRepository + KBService + RelationshipRepository for data access.
    Uses Redis-backed KBImproveCache for 10min TTL on analysis results.
    Includes InvocationPipeline for invocation evidence (ADR-040).
    """
    from narrare._app.config import get_settings
    from narrare._app.dependencies import (
        get_composer,
        get_invocation_pipeline,
        get_model_registry,
    )
    from narrare._app.dependencies_services import build_system_default_config
    from narrare.embeddings.repository import EmbeddingRepository
    from narrare.embeddings.service import EmbeddingService
    from narrare.kb.dependencies_core import get_kb_service
    from narrare.kb.improve_analyzer import KBImproveAnalyzer
    from narrare.kb.improve_cache import KBImproveCache
    from narrare.kb.improve_service import KBImproveService
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare_core.cache.redis_client import RedisSessionCache
    from narrare_core.context.proactive_service import ProactiveContextService

    registry = get_model_registry()
    composer = get_composer()
    config = build_system_default_config("analysis")

    kb_repo = KBRepository(session)
    embedding_service = EmbeddingService(EmbeddingRepository(session))
    proactive = ProactiveContextService(
        embedding_store=cast("EmbeddingStoreProtocol", embedding_service)
    )
    kb_service = get_kb_service(session)

    # Redis-backed improve cache with 10min TTL
    settings = get_settings()
    redis_cache = RedisSessionCache(settings.redis_url)
    improve_cache = KBImproveCache(redis_cache)

    # Analyzer handles all LLM interaction + caching
    analyzer = KBImproveAnalyzer(
        registry=registry,
        config=config,
        proactive_context=proactive,
        prompt_composer=composer,
        kb_repo=kb_repo,
        rel_repo=RelationshipRepository(session),
        improve_cache=improve_cache,
    )

    return KBImproveService(
        analyzer=analyzer,
        kb_repo=kb_repo,
        kb_service=kb_service,
        rel_repo=RelationshipRepository(session),
        invocation_pipeline=get_invocation_pipeline(),
    )
