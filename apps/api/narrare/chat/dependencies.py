"""Chat dependency injection factories.

All dependencies are injected via __init__ (DI pattern).
No business logic lives here — only wiring.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare._app.dependencies import (
    SessionDep,
    get_composer,
    get_invocation_pipeline,
    get_model_registry,
)

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


def get_chat_service(session: SessionDep) -> ChatService:
    """Create a ChatService with injected dependencies.

    Production wiring:
    - ModelRegistry for LLM model resolution
    - PromptComposer for system prompt assembly
    - SQLAlchemyConversationStore for message persistence
    - System-default model config for the chat intent
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

    Returns:
        Configured ChatService ready for use.
    """
    from narrare._app.dependencies_services import (
        SystemModelCategory,
        build_system_default_config,
    )
    from narrare.chat.chat_service import ChatService
    from narrare.chat.conversation_store import SQLAlchemyConversationStore
    from narrare.notes.dependencies import get_note_service
    from narrare.novels.repository import NovelRepository
    from narrare_core.llm.run_limits import DefaultRunLimitResolver

    registry = get_model_registry()
    composer = get_composer()
    config = build_system_default_config(category=SystemModelCategory.ANALYSIS)
    store = SQLAlchemyConversationStore(session)
    invocation_pipeline = get_invocation_pipeline()
    run_limit_resolver = DefaultRunLimitResolver()

    return ChatService(
        prompt_composer=composer,
        model_registry=registry,
        conversation_store=store,
        config=config,
        invocation_pipeline=invocation_pipeline,
        run_limit_resolver=run_limit_resolver,
        note_lookup=get_note_service(session),
        novel_lookup=_NovelOwnedLookup(NovelRepository(session)),
    )
