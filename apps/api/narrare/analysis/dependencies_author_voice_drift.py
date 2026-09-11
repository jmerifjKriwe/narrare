"""Analysis dependency injection factory — author voice drift
(ANAL-009 Phase 2B / ADR-074, RULE-04 split).

Extracted to keep the analysis ``dependencies.py`` under its size limit
(RULE-04). Production wiring for :class:`AuthorVoiceDriftService` lives here.

Model acquisition follows the per-user model-routing cascade: the factory
resolves ``LLMIntent.VOICE`` for the authenticated user (+ novel for
project-level overrides) and passes the resolved config + credentials into
the service. No business logic lives here — only wiring.

Mirrors :mod:`narrare.analysis.dependencies_author_voice` (the closest
sibling — novel-scoped SSE analysis service that reads the stored
:class:`AuthorVoiceProfile` via :class:`AuthorVoiceRepository`). The drift
service is the read-only consumer of the same stored profile (no SSOT bypass,
ADR-074).
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
    from narrare.analysis.author_voice_drift_service import AuthorVoiceDriftService


async def get_author_voice_drift_service(
    novel_id: UUID,
    session: SessionDep,
    user_id: str = Depends(get_current_user_id),
) -> AuthorVoiceDriftService:
    """Create an AuthorVoiceDriftService with per-user resolved model routing.

    FastAPI dependency: novel_id comes from the route path, user_id and
    session are resolved via Depends. The model is resolved through the
    per-user cascade (project intent → project category → user intent →
    user category → user default); ``ConfigurationError`` propagates when
    the user has no provider configured (analysis routers are
    auth-mandatory).

    Production wiring:
    - NovelRepository for novel access control + language/metadata resolution.
    - ChapterRepository for chapter content fetching (novel-scoped list).
    - AuthorVoiceRepository for reading the stored author-voice profile
      (ADR-074 storage contract — no direct column access).
    - ModelRegistry + ResolvedModelConfig for the AuthorVoiceDriftAgent
      (AI-powered qualitative narrator-trend classification).
    - PromptComposer for resolving the governed author-voice-drift system
      prompt via the cascade (Mode 1, ADR-054).
    - InvocationPipeline for invocation evidence (ADR-040 / ADR-045).
    """
    from narrare._app.dependencies import (
        get_composer,
        get_invocation_pipeline,
        get_model_registry,
    )
    from narrare.analysis.author_voice_drift_service import AuthorVoiceDriftService
    from narrare.analysis.author_voice_repository import AuthorVoiceRepository
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
    author_voice_repo = AuthorVoiceRepository(session)

    return AuthorVoiceDriftService(
        novel_repo=novel_repo,
        chapter_repo=chapter_repo,
        author_voice_repo=author_voice_repo,
        model_registry=registry,
        model_config=resolved.config,
        composer=composer,
        invocation_pipeline=get_invocation_pipeline(),
        api_key=resolved.api_key,
        base_url=resolved.base_url,
    )
