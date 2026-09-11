"""Analysis dependency injection factory — character voice (RULE-04 split).

Extracted from ``dependencies.py`` to keep that file under the 200-line
limit (RULE-04). Production wiring for ``CharacterVoiceService`` lives here.

Model acquisition follows the per-user model-routing cascade: the factory
resolves ``LLMIntent.VOICE`` for the authenticated user (+ novel for
project-level overrides) and passes the resolved config + credentials into
the service. No business logic lives here — only wiring.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import Depends

from narrare._app.dependencies import (
    SessionDep,
    get_current_user_id,
)
from narrare._app.dependencies_services import get_model_routing_resolver
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from narrare.analysis.character_voice_service import CharacterVoiceService


async def get_character_voice_service(
    novel_id: UUID,
    session: SessionDep,
    user_id: str = Depends(get_current_user_id),
) -> CharacterVoiceService:
    """Create a CharacterVoiceService with per-user resolved model routing.

    FastAPI dependency: novel_id comes from the route path, user_id and
    session are resolved via Depends. The model is resolved through the
    per-user cascade; ``ConfigurationError`` propagates when the user has
    no provider configured (analysis routers are auth-mandatory).

    Production wiring:
    - NovelRepository for novel access control + language/metadata resolution.
    - ChapterRepository for chapter content fetching.
    - KBRepository for finding character KB entries by name and persisting
      ``voice_analysis`` (Layer-0 storage contract, ADR-055).
    - RelationshipRepository for populating ``kb_relationships`` (character
      relationships are charakterprägend for voice profiling).
    - ModelRegistry + ResolvedModelConfig for the CharacterVoiceAgent
      (AI-powered qualitative voice profiling).
    - PromptComposer for resolving the governed character-voice system
      prompt via the cascade (Mode 1, ADR-054).
    - InvocationPipeline for invocation evidence (ADR-040 / ADR-045).
    """
    from narrare._app.dependencies import (
        get_composer,
        get_invocation_pipeline,
        get_model_registry,
    )
    from narrare.analysis.character_voice_service import CharacterVoiceService
    from narrare.chapters.repository import ChapterRepository
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare.novels.repository import NovelRepository

    resolver = get_model_routing_resolver(session)
    resolved = await resolver.resolve(
        LLMIntent.VOICE,
        UUID(user_id),
        novel_id,
    )

    registry = get_model_registry()
    composer = get_composer()

    chapter_repo = ChapterRepository(session)
    novel_repo = NovelRepository(session)
    kb_repo = KBRepository(session)
    relationship_repo = RelationshipRepository(session)

    return CharacterVoiceService(
        novel_repo=novel_repo,
        chapter_repo=chapter_repo,
        kb_repo=kb_repo,
        relationship_repo=relationship_repo,
        model_registry=registry,
        model_config=resolved.config,
        composer=composer,
        invocation_pipeline=get_invocation_pipeline(),
        api_key=resolved.api_key,
        base_url=resolved.base_url,
    )
