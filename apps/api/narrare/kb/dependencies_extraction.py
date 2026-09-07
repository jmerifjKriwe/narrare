"""KB dependency injection — extraction service factory.

Model acquisition follows the per-user model-routing cascade: the factory
resolves ``LLMIntent.KB_EXTRACT`` for the authenticated user (+ novel for
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
    from narrare.kb.extraction_service import ExtractionService


async def get_extraction_service(
    novel_id: UUID,
    session: SessionDep,
    user_id: str = Depends(get_current_user_id),
) -> ExtractionService:
    """Create an ExtractionService with per-user resolved model routing.

    FastAPI dependency: novel_id comes from the route path, user_id and
    session are resolved via Depends. The model is resolved through the
    per-user cascade (project intent → project category → user intent →
    user category → user default); ``ConfigurationError`` propagates when
    the user has no provider configured (kb routers are auth-mandatory).

    Production wiring: uses ModelRegistry for LLM model, PromptComposer
    for system prompts, and ChapterRepository + KBRepository for data.

    Also injects KBService, RelationshipRepository, and the request-scoped
    session for the apply extraction step (KB-007) — the apply service
    wraps each item in a SAVEPOINT on that session.

    Includes InvocationPipeline for invocation evidence (ADR-040) and a
    DefaultRunLimitResolver for ADR-045 output-budget enforcement at the
    ``agent.run`` boundary (same wiring as ``chat/dependencies.py`` and
    ``writing/deps_ws.py``).
    """
    from narrare._app.dependencies import (
        get_composer,
        get_invocation_pipeline,
        get_model_registry,
    )
    from narrare.chapters.repository import ChapterRepository
    from narrare.kb.extraction_service import ExtractionService
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare.kb.service import KBService
    from narrare_core.llm.run_limits import DefaultRunLimitResolver

    resolver = get_model_routing_resolver(session)
    resolved = await resolver.resolve(
        LLMIntent.KB_EXTRACT,
        UUID(user_id),
        novel_id,
    )

    registry = get_model_registry()
    composer = get_composer()

    return ExtractionService(
        registry=registry,
        config=resolved.config,
        chapter_repo=ChapterRepository(session),
        kb_repo=KBRepository(session),
        composer=composer,
        kb_service=KBService(
            repo=KBRepository(session),
            novel_repo=None,
            embedding_hooks=None,
        ),
        rel_repo=RelationshipRepository(session),
        session=session,
        invocation_pipeline=get_invocation_pipeline(),
        api_key=resolved.api_key,
        base_url=resolved.base_url,
        run_limit_resolver=DefaultRunLimitResolver(),
    )
