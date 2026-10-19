"""Analysis dependency injection factory — voice check (WRITE-010).

Model acquisition follows the per-user model-routing cascade with LAZY
first-use resolution (ADR-086): the factory wires a
``LazyModelResolution`` around ``resolver.resolve(LLMIntent.VOICE,
user_id, None)`` and passes it into the service — no resolution at
construction (FastAPI solves all sub-dependencies BEFORE body
validation, so an eager resolve here would preempt legitimate 422s with
400/500s). The voice-check router is chapter-scoped (no novel_id), so
the cascade resolves without the project tier. The cascade resolves on
the service's first ``ensure_resolved()``; the router keeps pre-header
400 semantics by calling it before the SSE stream starts. No business
logic lives here — only wiring.
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
    from narrare.analysis.voice_check_service import CharacterVoiceCheckerService
    from narrare.kb.models import KBEntry
    from narrare_core.profiles.contracts import VoiceProfileConsumer
    from narrare_core.writing.context_models import KBEntity


async def get_voice_check_service(
    session: SessionDep,
    user_id: str = Depends(get_current_user_id),
) -> CharacterVoiceCheckerService:
    """Create a CharacterVoiceCheckerService with per-user resolved model routing.

    FastAPI dependency: user_id and session are resolved via Depends. The
    voice-check router is chapter-scoped — the novel id is only known after
    the service loads the chapter — so the cascade resolves WITHOUT the
    project tier (user intent → user category → user default) on the
    service's first ``ensure_resolved()`` — NOT here (ADR-086):
    construction happens pre-body-validation, and eager resolution would
    preempt 422s. ``ConfigurationError`` still propagates loudly at first
    use (analysis routers are auth-mandatory).

    Production wiring:
    - NovelRepository for access control + language/metadata resolution.
    - ChapterRepository for chapter content fetching.
    - KBRepository-backed VoiceProfileConsumer provider for stored profiles.
    - KB character-roster provider (``known_character_names``) gating parsed
      utterances against the novel's KB characters (N11).
    - ModelRegistry + lazy model resolution (ADR-086) for the checker
      agent. The resolved credentials reach the ``registry.prepare``
      resolution point at consumption time.
    - PromptComposer for governed ``voice_check`` prompt resolution.
    - InvocationPipeline for invocation evidence.
    """
    from narrare._app.dependencies import (
        get_composer,
        get_invocation_pipeline,
        get_model_registry,
    )
    from narrare.analysis.voice_check_service import CharacterVoiceCheckerService
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
            None,
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

    from narrare.analysis.character_roster import known_character_names

    async def roster_provider(novel_id: UUID) -> set[str]:
        return await known_character_names(kb_repo, novel_id)

    return CharacterVoiceCheckerService(
        novel_repo=novel_repo,
        chapter_repo=chapter_repo,
        model_registry=registry,
        consumer_provider=consumer_provider,
        model_resolution=model_resolution,
        composer=composer,
        relationship_repo=relationship_repo,
        invocation_pipeline=get_invocation_pipeline(),
        roster_provider=roster_provider,
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
