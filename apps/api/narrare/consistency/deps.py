"""Consistency dependency injection factories.

Replaces dependencies.py — adds TokenLimitsService injection for dynamic
consistency context caps (CR-AUFG-08-02).
"""

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
    - TimelineEventRepository for temporal consistency context
    - TokenLimitsService for dynamic context cap resolution
    """
    from narrare._app.config import get_settings
    from narrare._app.dependencies import (
        get_composer,
        get_model_registry,
    )
    from narrare._app.dependencies_services import build_system_default_config
    from narrare.chapters.repository import ChapterRepository
    from narrare.consistency.checker_service import ConsistencyCheckerService
    from narrare.kb.repository import KBRepository
    from narrare.novels.repository import NovelRepository
    from narrare.planning.timeline_repository import TimelineEventRepository
    from narrare.settings.token_limits.repository import (
        ProjectTokenLimitsRepository,
        UserTokenLimitsRepository,
    )
    from narrare.settings.token_limits.service import TokenLimitsService

    registry = get_model_registry()
    composer = get_composer()
    config = build_system_default_config("analysis", temperature=0.3)

    # Repositories
    chapter_repo = ChapterRepository(session)
    novel_repo = NovelRepository(session)
    kb_repo = KBRepository(session)
    timeline_repo = TimelineEventRepository(session)

    # TokenLimitsService for dynamic context caps
    settings = get_settings()
    token_limits_service = TokenLimitsService(
        user_repo=UserTokenLimitsRepository(session),
        project_repo=ProjectTokenLimitsRepository(session),
        config=settings,
    )

    return ConsistencyCheckerService(
        chapter_repo=chapter_repo,
        novel_repo=novel_repo,
        kb_repo=kb_repo,
        timeline_repo=timeline_repo,
        registry=registry,
        config=config,
        composer=composer,
        token_limits_service=token_limits_service,
    )
