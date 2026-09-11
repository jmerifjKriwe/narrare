"""Analysis dependency injection factory — author voice (RULE-04 split).

Extracted to keep the analysis ``dependencies.py`` under its size limit
(RULE-04). Production wiring for :class:`AuthorVoiceService` lives here.

Model acquisition follows the per-user model-routing cascade: the factory
resolves ``LLMIntent.VOICE`` for the authenticated user (+ novel for
project-level overrides) and passes the resolved config + credentials into
the service. No business logic lives here — only wiring.

Mirrors :mod:`narrare.analysis.dependencies_character_voice` (the closest
sibling — novel-scoped SSE analysis service).
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
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from narrare.analysis.author_voice_service import AuthorVoiceService


async def get_author_voice_service(
    novel_id: UUID,
    session: SessionDep,
    user_id: str = Depends(get_current_user_id),
) -> AuthorVoiceService:
    """Create an AuthorVoiceService with per-user resolved model routing.

    FastAPI dependency: novel_id comes from the route path, user_id and
    session are resolved via Depends. The model is resolved through the
    per-user cascade (project intent → project category → user intent →
    user category → user default); ``ConfigurationError`` propagates when
    the user has no provider configured (analysis routers are
    auth-mandatory).

    Production wiring:
    - NovelRepository for novel access control + language/metadata resolution.
    - ChapterRepository for chapter content fetching.
    - AuthorVoiceRepository for persisting the assembled profile to
      ``ProjectSettings.author_voice`` (ADR-074 storage contract).
    - ModelRegistry + ResolvedModelConfig for the AuthorVoiceAgent
      (AI-powered qualitative voice profiling).
    - PromptComposer for resolving the governed author-voice system prompt
      via the cascade (Mode 1, ADR-054).
    - InvocationPipeline for invocation evidence (ADR-040 / ADR-045).
    """
    from narrare._app.dependencies import (
        get_composer,
        get_invocation_pipeline,
        get_model_registry,
    )
    from narrare.analysis.author_voice_repository import AuthorVoiceRepository
    from narrare.analysis.author_voice_service import AuthorVoiceService
    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository

    resolver = get_model_routing_resolver(session)
    resolved = await resolver.resolve(
        LLMIntent.VOICE,
        UUID(user_id),
        novel_id,
    )

    registry = get_model_registry()
    composer = get_composer()

    chapter_repo = ChapterRepository(session)
    novel_repo = NovelRepository(session)
    repository = AuthorVoiceRepository(session)

    return AuthorVoiceService(
        novel_repo=novel_repo,
        chapter_repo=chapter_repo,
        repository=repository,
        model_registry=registry,
        model_config=resolved.config,
        composer=composer,
        invocation_pipeline=get_invocation_pipeline(),
        api_key=resolved.api_key,
        base_url=resolved.base_url,
    )
