"""Analysis dependency injection factory — character voice (RULE-04 split).

Extracted from ``dependencies.py`` to keep that file under the 200-line
limit (RULE-04). Production wiring for ``CharacterVoiceService`` lives here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare._app.dependencies import SessionDep  # noqa: TC001 — needed at runtime for FastAPI DI

if TYPE_CHECKING:
    from narrare.analysis.character_voice_service import CharacterVoiceService


def get_character_voice_service(session: SessionDep) -> CharacterVoiceService:
    """Create a CharacterVoiceService with injected dependencies.

    Production wiring:
    - NovelRepository for novel access control + language/metadata resolution.
    - ChapterRepository for chapter content fetching.
    - KBRepository for finding character KB entries by name and persisting
      ``voice_analysis`` (Layer-0 storage contract, ADR-055).
    - ModelRegistry + ResolvedModelConfig for the CharacterVoiceAgent
      (AI-powered qualitative voice profiling).
    - PromptComposer for resolving the governed character-voice system
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
    from narrare.analysis.character_voice_service import CharacterVoiceService
    from narrare.chapters.repository import ChapterRepository
    from narrare.kb.repository import KBRepository
    from narrare.novels.repository import NovelRepository

    registry = get_model_registry()
    composer = get_composer()
    config = build_system_default_config(SystemModelCategory.ANALYSIS)

    chapter_repo = ChapterRepository(session)
    novel_repo = NovelRepository(session)
    kb_repo = KBRepository(session)

    return CharacterVoiceService(
        novel_repo=novel_repo,
        chapter_repo=chapter_repo,
        kb_repo=kb_repo,
        model_registry=registry,
        model_config=config,
        composer=composer,
        invocation_pipeline=get_invocation_pipeline(),
    )
