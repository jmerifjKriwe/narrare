"""KB dependency injection — session service factory.

Model acquisition follows the per-user model-routing cascade: the factory
wires the ``LLMIntent.KB_INTERVIEW`` cascade for the authenticated user (+
novel for project-level overrides) as a ``LazyModelResolution`` and passes
it into the assist service, which resolves it on first use (ADR-086) —
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
from narrare.events.publisher import (
    WikiEventPublisherDep,  # noqa: TC001 - needed at runtime for FastAPI DI
)
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from narrare.kb.session_service import KBSessionService


async def get_kb_session_service(
    novel_id: UUID,
    session: SessionDep,
    event_publisher: WikiEventPublisherDep,
    user_id: str = Depends(get_current_user_id),
) -> KBSessionService:
    """Create a KBSessionService with per-user lazy model routing.

    FastAPI dependency: novel_id comes from the route path, user_id and
    session are resolved via Depends. The model is NOT resolved here —
    the per-user cascade (project intent → project category → user
    intent → user category → user default) is wired as a
    ``LazyModelResolution`` and resolves on the assist service's first
    use (ADR-086), so request validation errors surface as 422 before
    any routing cascade runs, and non-AI session endpoints (create /
    get / answer / complete / abandon) never resolve at all.
    ``ConfigurationError`` propagates loudly from the assist entry
    points when the user has no provider configured (kb routers are
    auth-mandatory; RULE-11).

    The assist service serves three modes (interview/suggest/enhance) via
    one injected config; the cascade resolves with ``KB_INTERVIEW`` — the
    assist service's canonical default intent (see
    ``narrare.kb._assist_context._INTENT_MAP``).

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
    from narrare.kb._context_provider import KBContextProvider
    from narrare.kb.assist_service import KBAssistService
    from narrare.kb.dependencies_core import get_kb_service
    from narrare.kb.repository import KBRepository
    from narrare.kb.session_service import KBSessionService
    from narrare.kb.session_store import KBCreationSessionStore
    from narrare.novels.repository import NovelRepository
    from narrare_core.cache import InMemorySessionCache

    resolver = get_model_routing_resolver(session)
    model_resolution = LazyModelResolution(
        lambda: resolver.resolve(LLMIntent.KB_INTERVIEW, UUID(user_id), novel_id)
    )

    # Session storage: in-memory cache with 30min TTL (ADR-080).
    cache = InMemorySessionCache()
    session_store = KBCreationSessionStore(cache=cache)

    # KBAssistService with real ModelRegistry + PromptComposer. World context
    # is sourced from the canonical KBContextProvider (ADR-067), the single
    # source for KB prompt context across kb features. The model routing
    # cascade resolves on the assist service's first use (ADR-086), never
    # here.
    registry = get_model_registry()
    composer = get_composer()

    kb_repo = KBRepository(session)
    kb_context_provider = KBContextProvider(kb_repo)

    assist_service = KBAssistService(
        registry=registry,
        model_resolution=model_resolution,
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
