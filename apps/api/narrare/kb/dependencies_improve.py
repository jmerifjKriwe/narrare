"""KB dependency injection — improve service factory.

Model acquisition follows the per-user model-routing cascade: the factory
resolves ``LLMIntent.KB_IMPROVE`` for the authenticated user (+ novel for
project-level overrides) and passes the resolved config + credentials into
the analyzer. No business logic lives here — only wiring.
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
from narrare.events.publisher import (
    WikiEventPublisherDep,  # noqa: TC001 - needed at runtime for FastAPI DI
)
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from narrare.kb.improve_service import KBImproveService


async def get_kb_improve_service(
    novel_id: UUID,
    session: SessionDep,
    event_publisher: WikiEventPublisherDep,
    user_id: str = Depends(get_current_user_id),
) -> KBImproveService:
    """Create a KBImproveService with per-user resolved model routing.

    FastAPI dependency: novel_id comes from the route path, user_id and
    session are resolved via Depends. The model is resolved through the
    per-user cascade; ``ConfigurationError`` propagates when the user has
    no provider configured (kb routers are auth-mandatory).

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
    from narrare.kb._context_provider import KBContextProvider
    from narrare.kb.dependencies_core import get_kb_service
    from narrare.kb.improve_analyzer import KBImproveAnalyzer
    from narrare.kb.improve_cache import KBImproveCache
    from narrare.kb.improve_service import KBImproveService
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare_core.cache import InMemorySessionCache

    resolver = get_model_routing_resolver(session)
    resolved = await resolver.resolve(
        LLMIntent.KB_IMPROVE,
        UUID(user_id),
        novel_id,
    )

    registry = get_model_registry()
    composer = get_composer()

    kb_repo = KBRepository(session)
    rel_repo = RelationshipRepository(session)
    # Single source for KB world context (ADR-067): the analyzer draws its
    # curated world context from the KBContextProvider, not an inline
    # ProactiveContext call.
    kb_context_provider = KBContextProvider(kb_repo, rel_repo)

    kb_service = get_kb_service(session, event_publisher=event_publisher)

    # In-memory improve cache with 10min TTL (ADR-080)
    cache = InMemorySessionCache()
    improve_cache = KBImproveCache(cache)

    # Analyzer handles all LLM interaction + caching
    analyzer = KBImproveAnalyzer(
        registry=registry,
        config=resolved.config,
        kb_context_provider=kb_context_provider,
        prompt_composer=composer,
        kb_repo=kb_repo,
        rel_repo=rel_repo,
        improve_cache=improve_cache,
        invocation_pipeline=get_invocation_pipeline(),
        api_key=resolved.api_key,
        base_url=resolved.base_url,
    )

    return KBImproveService(
        analyzer=analyzer,
        kb_repo=kb_repo,
        kb_service=kb_service,
        rel_repo=rel_repo,
        invocation_pipeline=get_invocation_pipeline(),
    )
