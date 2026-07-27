"""Analysis dependency injection factory — author voice (RULE-04 split).

Extracted to keep the analysis ``dependencies.py`` under its size limit
(RULE-04). Production wiring for :class:`AuthorVoiceService` lives here.

Mirrors :mod:`narrare.analysis.dependencies_character_voice` (the closest
sibling — novel-scoped SSE analysis service).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare._app.dependencies import SessionDep  # noqa: TC001 — needed at runtime for FastAPI DI

if TYPE_CHECKING:
    from narrare.analysis.author_voice_service import AuthorVoiceService


def get_author_voice_service(session: SessionDep) -> AuthorVoiceService:
    """Create an AuthorVoiceService with injected dependencies.

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
    from narrare._app.dependencies_services import (
        SystemModelCategory,
        build_system_default_config,
    )
    from narrare.analysis.author_voice_repository import AuthorVoiceRepository
    from narrare.analysis.author_voice_service import AuthorVoiceService
    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository

    registry = get_model_registry()
    composer = get_composer()
    config = build_system_default_config(SystemModelCategory.ANALYSIS)

    chapter_repo = ChapterRepository(session)
    novel_repo = NovelRepository(session)
    repository = AuthorVoiceRepository(session)

    return AuthorVoiceService(
        novel_repo=novel_repo,
        chapter_repo=chapter_repo,
        repository=repository,
        model_registry=registry,
        model_config=config,
        composer=composer,
        invocation_pipeline=get_invocation_pipeline(),
    )
