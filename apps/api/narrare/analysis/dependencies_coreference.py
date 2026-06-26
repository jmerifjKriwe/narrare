"""Analysis dependency injection factory — coreference (RULE-04 split).

Extracted from ``dependencies.py`` to keep that file under the 200-line
limit (RULE-04). Production wiring for ``CoreferenceService`` lives here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare._app.dependencies import SessionDep  # noqa: TC001 — needed at runtime for FastAPI DI

if TYPE_CHECKING:
    from narrare.analysis.coreference_service import CoreferenceService


def get_coreference_service(session: SessionDep) -> CoreferenceService:
    """Create a CoreferenceService with injected dependencies.

    Production wiring:
    - ChapterRepository for chapter content fetching (novel_id-free lookup).
    - NovelRepository for novel access control + language/metadata resolution.
    - ModelRegistry + ResolvedModelConfig for the CoreferenceAgent
      (AI-powered pronoun resolution, ambiguity detection, mention tracking).
    - PromptComposer for resolving the governed coreference system prompt
      via the cascade (Mode 1, ADR-054).
    - InvocationPipeline for invocation evidence (ADR-040).
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
    from narrare.analysis.coreference_service import CoreferenceService
    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository

    registry = get_model_registry()
    composer = get_composer()
    config = build_system_default_config(SystemModelCategory.ANALYSIS)

    chapter_repo = ChapterRepository(session)
    novel_repo = NovelRepository(session)

    return CoreferenceService(
        novel_repo=novel_repo,
        chapter_repo=chapter_repo,
        model_registry=registry,
        model_config=config,
        composer=composer,
        invocation_pipeline=get_invocation_pipeline(),
    )
