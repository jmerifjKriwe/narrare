"""Chat dependency injection factories.

All dependencies are injected via __init__ (DI pattern).
No business logic lives here — only wiring.

Model acquisition follows the per-user model-routing cascade: the factory
resolves ``LLMIntent.CHAT`` (the intent ChatService composes its prompt
with) for the authenticated user and passes the resolved config +
credentials into the service that owns the actual ``get_model`` call.

Auth posture (plan Task 4 verification): ALL chat router endpoints declare
``CurrentUserIdDep`` — JWT-mandatory (401 on missing/invalid token, see
``narrare._app.dependencies_auth.get_current_user_id``). There is NO
anonymous path, so the migration is FULL — no system-default branch. The
router has no novel path parameter (``project_id`` arrives in the request
body), so the cascade runs WITHOUT the project tier per the migration plan
("where not, resolve without it").
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from narrare._app.dependencies import (
    CurrentUserIdDep,
    SessionDep,
    get_composer,
    get_invocation_pipeline,
    get_model_registry,
)
from narrare._app.dependencies_services import get_model_routing_resolver
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    import uuid

    from narrare.chat.chat_service import ChatService
    from narrare.novels.repository import NovelRepository


class _NovelOwnedLookup:
    """OwnedLinkLookupProtocol adapter over NovelRepository.get_by_id.

    Same pattern as ``narrare.notes.dependencies._NovelOwnedLookup``
    (module-local: notes' adapter is private to its module). get_by_id is
    already ownership-filtered, so this is pure delegation.
    """

    def __init__(self, repo: NovelRepository) -> None:
        self._repo = repo

    async def get_owned(self, entity_id: uuid.UUID, user_id: uuid.UUID) -> object | None:
        return await self._repo.get_by_id(entity_id, user_id)


async def get_chat_service(
    session: SessionDep,
    user_id: CurrentUserIdDep,
) -> ChatService:
    """Create a ChatService with per-user resolved model routing.

    Production wiring:
    - ModelRoutingResolver for the per-user model cascade (CHAT intent);
      ``ConfigurationError`` propagates when the user has no provider
      configured (chat routers are auth-mandatory).
    - ModelRegistry for LLM model resolution
    - PromptComposer for system prompt assembly
    - SQLAlchemyConversationStore for message persistence
    - InvocationPipeline for enrichment, budget, and evidence (ADR-048
      Mode 2 — agent-internal composition via ChatAgent).
    - DefaultRunLimitResolver for output-budget enforcement (ADR-045
      Decision 4).
    - NoteService as NoteLookupProtocol for note context injection
      (NOTES-001 §6b — wiring-level import, precedented by
      ``narrare.novels.router`` importing ``narrare.volumes.repository``).
    - _NovelOwnedLookup as OwnedLinkLookupProtocol for project-link
      ownership validation (P-SEC, notes pattern). ALWAYS wired — the
      service fails open on ``None`` (test contexts only), so a missing
      lookup would silently skip validation (notes T7-review invariant).

    Args:
        session: SQLAlchemy async session for DB access.
        user_id: Authenticated user id (FastAPI DI via CurrentUserIdDep).

    Returns:
        Configured ChatService ready for use.
    """
    from narrare.chat.chat_service import ChatService
    from narrare.chat.conversation_store import SQLAlchemyConversationStore
    from narrare.notes.dependencies import get_note_service
    from narrare.novels.repository import NovelRepository
    from narrare_core.llm.run_limits import DefaultRunLimitResolver

    resolver = get_model_routing_resolver(session)
    resolved = await resolver.resolve(LLMIntent.CHAT, UUID(user_id), None)

    registry = get_model_registry()
    composer = get_composer()

    return ChatService(
        prompt_composer=composer,
        model_registry=registry,
        conversation_store=SQLAlchemyConversationStore(session),
        config=resolved.config,
        invocation_pipeline=get_invocation_pipeline(),
        run_limit_resolver=DefaultRunLimitResolver(),
        api_key=resolved.api_key,
        base_url=resolved.base_url,
        note_lookup=get_note_service(session),
        novel_lookup=_NovelOwnedLookup(NovelRepository(session)),
    )
