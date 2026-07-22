"""DI factories for the ai_assist domain (RULE-04 split).

Production wiring for ``DialogueCoachService`` lives here. The service is
request-scoped (it depends on an ``AsyncSession`` for chapter loading +
evidence writes).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare._app.dependencies import SessionDep  # noqa: TC001 — needed at runtime for FastAPI DI

if TYPE_CHECKING:
    from narrare.ai_assist.service import DialogueCoachService


def get_dialogue_coach_service(
    session: SessionDep,
) -> DialogueCoachService:
    """Create a DialogueCoachService with production DI.

    Wires: ChapterRepository (unscoped chapter load), NovelRepository
    (novel-ownership access control + project metadata), ModelRegistry +
    ResolvedModelConfig (analysis-tier model), PromptComposer (Mode 1
    resolution), InvocationPipeline (evidence), AdaptiveContextProvider
    (load adaptive context + record snapshot).
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
    from narrare.adaptive.dependencies import get_adaptive_context_provider
    from narrare.ai_assist.service import DialogueCoachService
    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository

    registry = get_model_registry()
    composer = get_composer()
    config = build_system_default_config(SystemModelCategory.ANALYSIS)
    chapter_repo = ChapterRepository(session)
    novel_repo = NovelRepository(session)
    adaptive_provider = get_adaptive_context_provider(session)

    return DialogueCoachService(
        chapter_repo=chapter_repo,
        novel_repo=novel_repo,
        model_registry=registry,
        model_config=config,
        composer=composer,
        invocation_pipeline=get_invocation_pipeline(),
        adaptive_provider=adaptive_provider,
    )
