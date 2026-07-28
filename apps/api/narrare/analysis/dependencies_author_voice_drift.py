"""Analysis dependency injection factory — author voice drift
(ANAL-009 Phase 2B / ADR-074, RULE-04 split).

Extracted to keep the analysis ``dependencies.py`` under its size limit
(RULE-04). Production wiring for :class:`AuthorVoiceDriftService` lives here.

Mirrors :mod:`narrare.analysis.dependencies_author_voice` (the closest
sibling — novel-scoped SSE analysis service that reads the stored
:class:`AuthorVoiceProfile` via :class:`AuthorVoiceRepository`). The drift
service is the read-only consumer of the same stored profile (no SSOT bypass,
ADR-074).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare._app.dependencies import SessionDep  # noqa: TC001 — needed at runtime for FastAPI DI

if TYPE_CHECKING:
    from narrare.analysis.author_voice_drift_service import AuthorVoiceDriftService


def get_author_voice_drift_service(session: SessionDep) -> AuthorVoiceDriftService:
    """Create an AuthorVoiceDriftService with injected dependencies.

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
    from narrare._app.dependencies_services import (
        SystemModelCategory,
        build_system_default_config,
    )
    from narrare.analysis.author_voice_drift_service import AuthorVoiceDriftService
    from narrare.analysis.author_voice_repository import AuthorVoiceRepository
    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository

    registry = get_model_registry()
    composer = get_composer()
    config = build_system_default_config(SystemModelCategory.ANALYSIS)

    chapter_repo = ChapterRepository(session)
    novel_repo = NovelRepository(session)
    author_voice_repo = AuthorVoiceRepository(session)

    return AuthorVoiceDriftService(
        novel_repo=novel_repo,
        chapter_repo=chapter_repo,
        author_voice_repo=author_voice_repo,
        model_registry=registry,
        model_config=config,
        composer=composer,
        invocation_pipeline=get_invocation_pipeline(),
    )
