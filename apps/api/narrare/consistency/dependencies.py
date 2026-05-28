"""Consistency dependency injection factories."""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare._app.dependencies import SessionDep  # noqa: TC001 — needed at runtime for FastAPI DI

if TYPE_CHECKING:
    from narrare.consistency.checker_service import ConsistencyCheckerService


def get_consistency_service(session: SessionDep) -> ConsistencyCheckerService:
    """Create a ConsistencyCheckerService with injected dependencies.

    Production wiring:
    - ModelRegistry for LLM model resolution
    - PromptComposer for system prompt assembly (with inline fallback)
    - ChapterRepository for chapter content fetching
    - NovelRepository for novel access control + language resolution
    - KBRepository for KB entity summaries
    """
    from narrare._app.dependencies import get_composer, get_model_registry
    from narrare.chapters.repository import ChapterRepository
    from narrare.consistency.checker_service import ConsistencyCheckerService
    from narrare.kb.repository import KBRepository
    from narrare.novels.repository import NovelRepository
    from narrare_core.llm.intents import ResolvedModelConfig

    registry = get_model_registry()
    composer = get_composer()
    config = ResolvedModelConfig(
        provider_name="default",
        model_id="default",
        temperature=0.3,
        max_tokens=4096,
    )

    # Repositories
    chapter_repo = ChapterRepository(session)
    novel_repo = NovelRepository(session)
    kb_repo = KBRepository(session)

    return ConsistencyCheckerService(
        chapter_repo=chapter_repo,
        novel_repo=novel_repo,
        kb_repo=kb_repo,
        registry=registry,
        config=config,
        composer=composer,
    )
