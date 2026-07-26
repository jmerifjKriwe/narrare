"""Analysis dependency injection factory — voice drift (ANAL-009 / ADR-073).

Production wiring for :class:`CharacterVoiceDriftService`. Mirrors
``dependencies_voice_check`` — the drift service is a read-only consumer of
the same ``VoiceProfileConsumer`` contract (ADR-050 — no SSOT bypass).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare._app.dependencies import SessionDep  # noqa: TC001 — needed at runtime for FastAPI DI

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.analysis.voice_drift_service import CharacterVoiceDriftService
    from narrare.kb.models import KBEntry
    from narrare_core.profiles.contracts import VoiceProfileConsumer
    from narrare_core.writing.context_models import KBEntity


def get_voice_drift_service(session: SessionDep) -> CharacterVoiceDriftService:
    """Create a CharacterVoiceDriftService with injected dependencies.

    Production wiring:
    - NovelRepository for novel access control + language/metadata resolution.
    - ChapterRepository for chapter content fetching (novel-scoped list).
    - KBRepository-backed VoiceProfileConsumer provider for stored profiles
      (the same consumer contract WRITE-010 uses — ADR-050, no SSOT bypass).
    - ModelRegistry + ResolvedModelConfig for the drift agent.
    - PromptComposer for governed ``voice_drift`` prompt resolution (Mode 1).
    - RelationshipRepository for populating ``kb_relationships`` (character
      relationships help the classifier distinguish ``context`` drift from
      ``inconsistency``).
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
    from narrare.analysis.voice_drift_service import CharacterVoiceDriftService
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

    return CharacterVoiceDriftService(
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
    """Convert a persisted KB entry to the profile-consumer entity shape.

    Thin delegate to the canonical ``KBEntry→KBEntity`` mapper in
    :func:`narrare.kb._context_provider.kb_entry_to_kb_entity` (ADR-067), kept
    as a local name so the closure above reads without a cross-module import
    at the call site.
    """
    from narrare.kb._context_provider import kb_entry_to_kb_entity

    return kb_entry_to_kb_entity(entry)
