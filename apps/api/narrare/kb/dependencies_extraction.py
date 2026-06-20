"""KB dependency injection — extraction service factory."""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare._app.dependencies import SessionDep  # noqa: TC001 - needed at runtime for FastAPI DI

if TYPE_CHECKING:
    from narrare.kb.extraction_service import ExtractionService


def get_extraction_service(session: SessionDep) -> ExtractionService:
    """Create an ExtractionService with injected dependencies.

    Production wiring: uses ModelRegistry for LLM model, PromptComposer
    for system prompts, and ChapterRepository + KBRepository for data.

    Also injects KBService and RelationshipRepository for the apply
    extraction step (KB-007).

    Includes InvocationPipeline for invocation evidence (ADR-040).
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
    from narrare.chapters.repository import ChapterRepository
    from narrare.kb.extraction_service import ExtractionService
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare.kb.service import KBService

    registry = get_model_registry()
    composer = get_composer()
    config = build_system_default_config(SystemModelCategory.ANALYSIS)

    return ExtractionService(
        registry=registry,
        config=config,
        chapter_repo=ChapterRepository(session),
        kb_repo=KBRepository(session),
        composer=composer,
        kb_service=KBService(
            repo=KBRepository(session),
            novel_repo=None,
            embedding_hooks=None,
        ),
        rel_repo=RelationshipRepository(session),
        invocation_pipeline=get_invocation_pipeline(),
    )
