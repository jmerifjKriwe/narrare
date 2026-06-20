"""KB dependency injection — session service factory."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from narrare._app.dependencies import SessionDep  # noqa: TC001 - needed at runtime for FastAPI DI

if TYPE_CHECKING:
    from narrare.kb.session_service import KBSessionService
    from narrare_core.embeddings.store import EmbeddingStoreProtocol


def get_kb_session_service(session: SessionDep) -> KBSessionService:
    """Create a KBSessionService with injected dependencies.

    Production wiring: uses EmbeddingService for ProactiveContextService,
    ModelRegistry for LLM model, and PromptComposer for system prompts.
    For session storage, uses RedisSessionCache for persistence with TTL.
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
    from narrare.embeddings.repository import EmbeddingRepository
    from narrare.embeddings.service import EmbeddingService
    from narrare.kb.assist_service import KBAssistService
    from narrare.kb.dependencies_core import get_kb_service
    from narrare.kb.session_service import KBSessionService
    from narrare.kb.session_store import KBCreationSessionStore
    from narrare_core.cache.redis_client import RedisSessionCache
    from narrare_core.context.proactive_service import ProactiveContextService

    # Session storage: Redis-backed with 30min TTL.
    settings = get_settings()
    cache = RedisSessionCache(settings.redis_url)
    session_store = KBCreationSessionStore(cache=cache)

    # ProactiveContextService with real embedding service
    embedding_service = EmbeddingService(EmbeddingRepository(session))
    proactive = ProactiveContextService(
        embedding_store=cast("EmbeddingStoreProtocol", embedding_service)
    )

    # KBAssistService with real ModelRegistry + PromptComposer.
    registry = get_model_registry()
    composer = get_composer()
    config = build_system_default_config(SystemModelCategory.ANALYSIS)

    assist_service = KBAssistService(
        registry=registry,
        config=config,
        proactive_context=proactive,
        prompt_composer=composer,
        invocation_pipeline=get_invocation_pipeline(),
    )

    kb_service = get_kb_service(session)

    return KBSessionService(
        session_store=session_store,
        assist_service=assist_service,
        kb_service=kb_service,
    )
