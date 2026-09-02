"""Analysis dependency injection factory — coreference (RULE-04 split).

Extracted from ``dependencies.py`` to keep that file under the 200-line
limit (RULE-04). Production wiring for ``CoreferenceService`` lives here.

Model acquisition follows the per-user model-routing cascade: the factory
resolves ``LLMIntent.ANALYSE`` for the authenticated user and passes the
resolved config + credentials into the service. The coreference router is
chapter-scoped (no novel_id), so the cascade resolves without the project
tier. No business logic lives here — only wiring.
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
    from narrare.analysis.coreference_service import CoreferenceService


async def get_coreference_service(
    session: SessionDep,
    user_id: str = Depends(get_current_user_id),
) -> CoreferenceService:
    """Create a CoreferenceService with per-user resolved model routing.

    FastAPI dependency: user_id and session are resolved via Depends. The
    coreference router is chapter-scoped — the novel id is only known after
    the service loads the chapter — so the cascade resolves WITHOUT the
    project tier (user intent → user category → user default).
    ``ConfigurationError`` propagates when the user has no provider
    configured (analysis routers are auth-mandatory).

    Production wiring:
    - ChapterRepository for chapter content fetching (novel_id-free lookup).
    - NovelRepository for novel access control + language/metadata resolution.
    - Canonical KB-context provider (ADR-067) for the ``kb_characters`` /
      ``kb_locations`` / ``kb_factions`` / ``kb_relationships`` prompt
      variables — rendered through the ADR-050 envelope with provenance
      (FIND-017). Degrades gracefully (RULE-11). Coreference resolution
      needs the character name list to map pronouns → characters, plus
      locations/factions/relationships for disambiguation context.
    - ModelRegistry + ResolvedModelConfig for the CoreferenceAgent
      (AI-powered pronoun resolution, ambiguity detection, mention tracking).
    - PromptComposer for resolving the governed coreference system prompt
      via the cascade (Mode 1, ADR-054).
    - InvocationPipeline for invocation evidence (ADR-040).
    """
    from narrare._app.dependencies import (
        get_composer,
        get_invocation_pipeline,
        get_model_registry,
    )
    from narrare.analysis.coreference_service import CoreferenceService
    from narrare.chapters.repository import ChapterRepository
    from narrare.kb._context_provider import KBContextProvider
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare.novels.repository import NovelRepository

    resolver = get_model_routing_resolver(session)
    resolved = await resolver.resolve(
        LLMIntent.ANALYSE,
        UUID(user_id),
        None,
    )

    registry = get_model_registry()
    composer = get_composer()

    chapter_repo = ChapterRepository(session)
    novel_repo = NovelRepository(session)

    # Canonical KB-context provider (ADR-067): single fetch+render source for
    # all four KB-context slots. Degrades gracefully (RULE-11).
    kb_context_provider = KBContextProvider(
        kb_repo=KBRepository(session),
        relationship_repo=RelationshipRepository(session),
    )

    return CoreferenceService(
        novel_repo=novel_repo,
        chapter_repo=chapter_repo,
        model_registry=registry,
        model_config=resolved.config,
        composer=composer,
        kb_context_provider=kb_context_provider,
        invocation_pipeline=get_invocation_pipeline(),
        api_key=resolved.api_key,
        base_url=resolved.base_url,
    )
