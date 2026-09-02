"""DI factories for the ai_assist domain (RULE-04 split).

Production wiring for ``DialogueCoachService`` lives here. The service is
request-scoped (it depends on an ``AsyncSession`` for chapter loading +
evidence writes).

Model acquisition follows the per-user model-routing cascade: the factory
resolves ``LLMIntent.DIALOGUE_COACH`` (feature ``ai_assist_dialogue_coach``,
ADR-069 Decision 5) for the authenticated user and passes the resolved
config + credentials into the service that owns the actual ``get_model``
call. The router is chapter-scoped (``chapter_id`` path parameter) — the
novel (project) is only known after the chapter load inside the service,
so the cascade runs WITHOUT the project tier. No business logic lives
here — only wiring.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from narrare._app.dependencies import (  # noqa: TC001 — needed at runtime for FastAPI DI
    CurrentUserIdDep,
    SessionDep,
)
from narrare._app.dependencies_services import get_model_routing_resolver
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from narrare.ai_assist.service import DialogueCoachService


async def get_dialogue_coach_service(
    session: SessionDep,
    user_id: CurrentUserIdDep,
) -> DialogueCoachService:
    """Create a DialogueCoachService with per-user resolved model routing.

    FastAPI dependency: user_id and session are resolved via Depends. The
    model is resolved through the per-user cascade (user intent → user
    category → user default); ``ConfigurationError`` propagates when the
    user has no provider configured (the router is auth-mandatory via
    ``CurrentUserIdDep``).

    Wires: ChapterRepository (unscoped chapter load), NovelRepository
    (novel-ownership access control + project metadata), ModelRegistry +
    resolved model config, PromptComposer (Mode 1 resolution),
    InvocationPipeline (evidence), AdaptiveContextProvider (load adaptive
    context + record snapshot). The resolved credentials are threaded
    through the service to the agent-runner ``get_model`` resolution point.
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
    resolved = await resolver.resolve(LLMIntent.DIALOGUE_COACH, UUID(user_id), None)

    registry = get_model_registry()
    composer = get_composer()

    return DialogueCoachService(
        chapter_repo=ChapterRepository(session),
        novel_repo=NovelRepository(session),
        model_registry=registry,
        model_config=resolved.config,
        composer=composer,
        invocation_pipeline=get_invocation_pipeline(),
        adaptive_provider=get_adaptive_context_provider(session),
        api_key=resolved.api_key,
        base_url=resolved.base_url,
    )
