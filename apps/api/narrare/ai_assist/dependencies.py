"""DI factories for the ai_assist domain (RULE-04 split).

Production wiring for ``DialogueCoachService`` lives here. The service is
request-scoped (it depends on an ``AsyncSession`` for chapter loading +
evidence writes).

Model acquisition follows the per-user model-routing cascade with LAZY
first-use resolution (ADR-086): the factory wires a ``LazyModelResolution``
around ``resolver.resolve(LLMIntent.DIALOGUE_COACH, user_id, None)`` and
passes it into the service — no resolution at construction (FastAPI solves
all sub-dependencies BEFORE body validation, so an eager resolve here
would preempt legitimate 422s with 400/500s). The cascade runs on the
service's first ``ensure_resolved()``; the router keeps pre-header 400
semantics by calling it before the SSE stream starts. The router is
chapter-scoped (``chapter_id`` path parameter) — the novel (project) is
only known after the chapter load inside the service, so the cascade runs
WITHOUT the project tier. No business logic lives here — only wiring.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from narrare._app.dependencies import (  # noqa: TC001 — needed at runtime for FastAPI DI
    CurrentUserIdDep,
    SessionDep,
)
from narrare._app.dependencies_services import (
    LazyModelResolution,
    get_model_routing_resolver,
)
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from narrare.ai_assist.service import DialogueCoachService


async def get_dialogue_coach_service(
    session: SessionDep,
    user_id: CurrentUserIdDep,
) -> DialogueCoachService:
    """Create a DialogueCoachService with lazily-wired per-user routing.

    FastAPI dependency: user_id and session are resolved via Depends. The
    model resolves through the per-user cascade (user intent → user
    category → user default) on the service's first ``ensure_resolved()``
    — NOT here (ADR-086): construction happens pre-body-validation, and
    eager resolution would preempt 422s. ``ConfigurationError`` still
    propagates loudly at first use (the router is auth-mandatory via
    ``CurrentUserIdDep``).

    Wires: ChapterRepository (unscoped chapter load), NovelRepository
    (novel-ownership access control + project metadata), ModelRegistry +
    lazy model resolution, PromptComposer (Mode 1 resolution),
    InvocationPipeline (evidence), AdaptiveContextProvider (load adaptive
    context + record snapshot). The resolved credentials reach the
    agent-runner ``get_model`` resolution point at consumption time.
    """
    from narrare._app.dependencies import (
        get_composer,
        get_invocation_pipeline,
        get_model_registry,
    )
    from narrare.adaptive.dependencies import get_adaptive_context_provider
    from narrare.ai_assist.service import DialogueCoachService
    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository

    resolver = get_model_routing_resolver(session)
    user_uuid = UUID(user_id)
    model_resolution = LazyModelResolution(
        lambda: resolver.resolve(LLMIntent.DIALOGUE_COACH, user_uuid, None)
    )

    registry = get_model_registry()
    composer = get_composer()

    return DialogueCoachService(
        chapter_repo=ChapterRepository(session),
        novel_repo=NovelRepository(session),
        model_registry=registry,
        model_resolution=model_resolution,
        composer=composer,
        invocation_pipeline=get_invocation_pipeline(),
        adaptive_provider=get_adaptive_context_provider(session),
    )
