"""Consistency dependency injection factories.

Updated for ADR-044: injects ``ConsistencyOrchestrator`` for the staged
pipeline. When the orchestrator is present, the service uses the two-stage
flow (FactExtractor → ConsistencyAgent). Otherwise falls back to legacy.
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
    - ConsistencyOrchestrator for staged pipeline (ADR-044)
    - Repositories for data access
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
    from narrare.consistency.consistency_orchestrator import ConsistencyOrchestrator
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
    consistency_config = build_system_default_config("analysis", temperature=0.3)

    # Fact extractor config for staged pipeline (ADR-044)
    fact_extractor_config = build_system_default_config("analysis", temperature=0.2)

    # Repositories
    chapter_repo = ChapterRepository(session)
    novel_repo = NovelRepository(session)
    kb_repo = KBRepository(session)
    timeline_repo = TimelineEventRepository(session)

    # Orchestrator for staged pipeline
    orchestrator = ConsistencyOrchestrator(
        registry=registry,
        fact_extractor_config=fact_extractor_config,
        consistency_config=consistency_config,
        composer=composer,
    )

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
        config=consistency_config,
        composer=composer,
        token_limits_service=token_limits_service,
        orchestrator=orchestrator,
    )
