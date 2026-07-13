"""Analysis dependency injection factory — voice check (WRITE-010)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare._app.dependencies import SessionDep  # noqa: TC001 — needed at runtime for FastAPI DI
from narrare_core.writing.context_models import KBEntity

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.analysis.voice_check_service import CharacterVoiceCheckerService
    from narrare.kb.models import KBEntry
    from narrare_core.profiles.contracts import VoiceProfileConsumer


def get_voice_check_service(session: SessionDep) -> CharacterVoiceCheckerService:
    """Create a CharacterVoiceCheckerService with injected dependencies.

    Production wiring:
    - NovelRepository for access control + language/metadata resolution.
    - ChapterRepository for chapter content fetching.
    - KBRepository-backed VoiceProfileConsumer provider for stored profiles.
    - ModelRegistry + ResolvedModelConfig for the checker agent.
    - PromptComposer for governed ``voice_check`` prompt resolution.
    - InvocationPipeline for invocation evidence.
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
    from narrare.analysis.voice_check_service import CharacterVoiceCheckerService
    from narrare.chapters.repository import ChapterRepository
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare.novels.repository import NovelRepository
    from narrare.writing.voice_profile_adapter import make_voice_profile_consumer

    registry = get_model_registry()
    composer = get_composer()
    config = build_system_default_config(SystemModelCategory.ANALYSIS)

    chapter_repo = ChapterRepository(session)
    novel_repo = NovelRepository(session)
    kb_repo = KBRepository(session)
    relationship_repo = RelationshipRepository(session)

    async def consumer_provider(novel_id: UUID) -> VoiceProfileConsumer:
        entries, _total = await kb_repo.list_entries(
            novel_id,
            entity_type="character",
            page=1,
            page_size=1000,
        )
        entities = [_entry_to_kb_entity(entry) for entry in entries]
        return make_voice_profile_consumer(entities)

    return CharacterVoiceCheckerService(
        novel_repo=novel_repo,
        chapter_repo=chapter_repo,
        model_registry=registry,
        consumer_provider=consumer_provider,
        model_config=config,
        composer=composer,
        relationship_repo=relationship_repo,
        invocation_pipeline=get_invocation_pipeline(),
    )


def _entry_to_kb_entity(entry: KBEntry) -> KBEntity:
    """Convert a persisted KB entry to the profile-consumer entity shape."""
    return KBEntity(
        entity_id=str(entry.id),
        entity_type=entry.entity_type,
        name=entry.name,
        content=entry.body or "",
        updated_at=entry.updated_at.isoformat() if entry.updated_at else None,
        metadata=entry.metadata_,
        status=entry.status,
        source=entry.source,
        review_status=entry.review_status,
    )
