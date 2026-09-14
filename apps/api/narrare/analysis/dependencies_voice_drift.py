"""Analysis dependency injection factory — voice drift (ANAL-009 / ADR-073).

Production wiring for :class:`CharacterVoiceDriftService`. Mirrors
``dependencies_voice_check`` — the drift service is a read-only consumer of
the same ``VoiceProfileConsumer`` contract (ADR-050 — no SSOT bypass).

Model acquisition follows the per-user model-routing cascade with LAZY
first-use resolution (ADR-086): the factory wires a
``LazyModelResolution`` around ``resolver.resolve(LLMIntent.VOICE,
user_id, novel_id)`` and passes it into the service — no resolution at
construction (FastAPI solves all sub-dependencies BEFORE body
validation, so an eager resolve here would preempt legitimate 422s with
400/500s). The cascade resolves on the service's first
``ensure_resolved()``; the router keeps pre-header 400 semantics by
calling it before the SSE stream starts. No business logic lives here —
only wiring.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import Depends

from narrare._app.dependencies import (
    SessionDep,
    get_current_user_id,
)
from narrare._app.dependencies_services import (
    LazyModelResolution,
    get_model_routing_resolver,
)
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from narrare.analysis.voice_drift_service import CharacterVoiceDriftService
    from narrare.kb.models import KBEntry
    from narrare_core.profiles.contracts import VoiceProfileConsumer
    from narrare_core.writing.context_models import KBEntity


async def get_voice_drift_service(
    novel_id: UUID,
    session: SessionDep,
    user_id: str = Depends(get_current_user_id),
) -> CharacterVoiceDriftService:
    """Create a CharacterVoiceDriftService with per-user resolved model routing.

    FastAPI dependency: novel_id comes from the route path, user_id and
    session are resolved via Depends. The model resolves through the
    per-user cascade (project intent → project category → user intent →
    user category → user default) on the service's first
    ``ensure_resolved()`` — NOT here (ADR-086): construction happens
    pre-body-validation, and eager resolution would preempt 422s.
    ``ConfigurationError`` still propagates loudly at first use (analysis
    routers are auth-mandatory).

    Production wiring:
    - NovelRepository for novel access control + language/metadata resolution.
    - ChapterRepository for chapter content fetching (novel-scoped list).
    - KBRepository-backed VoiceProfileConsumer provider for stored profiles
      (the same consumer contract WRITE-010 uses — ADR-050, no SSOT bypass).
    - ModelRegistry + lazy model resolution (ADR-086) for the drift agent.
      The resolved credentials reach the ``registry.prepare`` resolution
      point at consumption time.
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
    from narrare.analysis.voice_drift_service import CharacterVoiceDriftService
    from narrare.chapters.repository import ChapterRepository
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare.novels.repository import NovelRepository
    from narrare.writing.voice_profile_adapter import make_voice_profile_consumer

    resolver = get_model_routing_resolver(session)
    model_resolution = LazyModelResolution(
        lambda: resolver.resolve(
            LLMIntent.VOICE,
            UUID(user_id),
            novel_id,
        )
    )

    registry = get_model_registry()
    composer = get_composer()

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
        model_resolution=model_resolution,
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
