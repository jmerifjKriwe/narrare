"""KB dependency injection — improve service factory."""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare._app.dependencies import SessionDep  # noqa: TC001 - needed at runtime for FastAPI DI

if TYPE_CHECKING:
    from narrare.kb.improve_service import KBImproveService


def get_kb_improve_service(session: SessionDep) -> KBImproveService:
    """Create a KBImproveService with injected dependencies.

    Production wiring: uses ModelRegistry for LLM model, PromptComposer
    for system prompts, KBContextProvider for curated world context
    (ADR-067 — single source for KB prompt context), and KBRepository +
    KBService + RelationshipRepository for data access. Uses the in-memory
    KBImproveCache for 10min TTL on analysis results. Includes
    InvocationPipeline for invocation evidence (ADR-040).
    """
    from narrare._app.dependencies import (
        get_composer,
        get_invocation_pipeline,
        get_model_registry,
    )
    from narrare._app.dependencies_services import (
        SystemModelCategory,
        build_system_default_config,
    )
    from narrare.kb._context_provider import KBContextProvider
    from narrare.kb.dependencies_core import get_kb_service
    from narrare.kb.improve_analyzer import KBImproveAnalyzer
    from narrare.kb.improve_cache import KBImproveCache
    from narrare.kb.improve_service import KBImproveService
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare_core.cache import InMemorySessionCache

    registry = get_model_registry()
    composer = get_composer()
    config = build_system_default_config(SystemModelCategory.ANALYSIS)

    kb_repo = KBRepository(session)
    rel_repo = RelationshipRepository(session)
    # Single source for KB world context (ADR-067): the analyzer draws its
    # curated world context from the KBContextProvider, not an inline
    # ProactiveContext call.
    kb_context_provider = KBContextProvider(kb_repo, rel_repo)

    kb_service = get_kb_service(session)

    # In-memory improve cache with 10min TTL (ADR-080)
    cache = InMemorySessionCache()
    improve_cache = KBImproveCache(cache)

    # Analyzer handles all LLM interaction + caching
    analyzer = KBImproveAnalyzer(
        registry=registry,
        config=config,
        kb_context_provider=kb_context_provider,
        prompt_composer=composer,
        kb_repo=kb_repo,
        rel_repo=rel_repo,
        improve_cache=improve_cache,
        invocation_pipeline=get_invocation_pipeline(),
    )

    return KBImproveService(
        analyzer=analyzer,
        kb_repo=kb_repo,
        kb_service=kb_service,
        rel_repo=rel_repo,
        invocation_pipeline=get_invocation_pipeline(),
    )
