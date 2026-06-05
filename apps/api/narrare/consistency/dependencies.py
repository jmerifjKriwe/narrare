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
    - PromptComposer for system prompt assembly
    - ChapterRepository for chapter content fetching
    - NovelRepository for novel access control + language resolution
    - KBRepository for KB entity summaries
    """
    from narrare._app.dependencies import (
        build_system_default_config,
        get_composer,
        get_model_registry,
    )
    from narrare.chapters.repository import ChapterRepository
    from narrare.consistency.checker_service import ConsistencyCheckerService
    from narrare.kb.repository import KBRepository
    from narrare.novels.repository import NovelRepository

    registry = get_model_registry()
    composer = get_composer()
    config = build_system_default_config("analysis", temperature=0.3)

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
