"""KB dependency injection — session service factory."""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare._app.dependencies import SessionDep  # noqa: TC001 - needed at runtime for FastAPI DI
from narrare.events.publisher import (
    WikiEventPublisherDep,  # noqa: TC001 - needed at runtime for FastAPI DI
)

if TYPE_CHECKING:
    from narrare.kb.session_service import KBSessionService


def get_kb_session_service(
    session: SessionDep,
    event_publisher: WikiEventPublisherDep,
) -> KBSessionService:
    """Create a KBSessionService with injected dependencies.

    Production wiring: uses ModelRegistry for LLM model, PromptComposer
    for system prompts, and KBContextProvider for curated world context
    (ADR-067 — single source for KB prompt context). For session storage,
    uses InMemorySessionCache for persistence with TTL. Includes
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
    from narrare.kb.assist_service import KBAssistService
    from narrare.kb.dependencies_core import get_kb_service
    from narrare.kb.repository import KBRepository
    from narrare.kb.session_service import KBSessionService
    from narrare.kb.session_store import KBCreationSessionStore
    from narrare.novels.repository import NovelRepository
    from narrare_core.cache import InMemorySessionCache

    # Session storage: in-memory cache with 30min TTL (ADR-080).
    cache = InMemorySessionCache()
    session_store = KBCreationSessionStore(cache=cache)

    # KBAssistService with real ModelRegistry + PromptComposer. World context
    # is sourced from the canonical KBContextProvider (ADR-067), the single
    # source for KB prompt context across kb features.
    registry = get_model_registry()
    composer = get_composer()
    config = build_system_default_config(SystemModelCategory.ANALYSIS)

    kb_repo = KBRepository(session)
    kb_context_provider = KBContextProvider(kb_repo)

    assist_service = KBAssistService(
        registry=registry,
        config=config,
        kb_context_provider=kb_context_provider,
        prompt_composer=composer,
        invocation_pipeline=get_invocation_pipeline(),
    )

    kb_service = get_kb_service(session, event_publisher=event_publisher)

    return KBSessionService(
        session_store=session_store,
        assist_service=assist_service,
        novel_repo=NovelRepository(session),
        kb_service=kb_service,
    )
