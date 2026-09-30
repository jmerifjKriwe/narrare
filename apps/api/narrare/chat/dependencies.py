"""Chat dependency injection factories.

All dependencies are injected via __init__ (DI pattern).
No business logic lives here — only wiring.

Model acquisition follows the per-user model-routing cascade: the factory
wires ``LLMIntent.CHAT`` (the intent ChatService composes its prompt
with) for the authenticated user as a ``LazyModelResolution`` and passes
it into the service that owns the actual ``get_model`` call. Per ADR-086
the cascade resolves on the service's first use (``ChatService.ask()``),
never at construction — so request-body validation errors surface as 422
before any routing cascade runs.

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
from narrare._app.dependencies_services import (
    LazyModelResolution,
    get_model_routing_resolver,
)
from narrare_core.llm.intents import LLMIntent
from narrare_core.settings import get_core_settings

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
    - LazyModelResolution over the per-user model cascade (CHAT intent,
      ADR-086): zero resolution at construction — the cascade resolves
      at the service's first use, so body-validation errors surface as
      422 and an unconfigured provider stays a loud 400 at the service
      entry point (chat routers are auth-mandatory).
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
    - KBContextProvider as KBContextProviderProtocol (ADR-067) for the
      chat template's per-type KB slots (kb_characters / kb_locations /
      kb_factions / kb_other / kb_relationships). ALWAYS wired — an
      unwired provider would silently keep the slots empty in production;
      per-fetch degradation stays inside the provider (RULE-11).

    Args:
        session: SQLAlchemy async session for DB access.
        user_id: Authenticated user id (FastAPI DI via CurrentUserIdDep).

    Returns:
        Configured ChatService ready for use.
    """
    from narrare.chat.chat_service import ChatService
    from narrare.chat.conversation_store import SQLAlchemyConversationStore
    from narrare.kb._context_provider import KBContextProvider
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare.notes.dependencies import get_note_service
    from narrare.novels.repository import NovelRepository
    from narrare_core.llm.run_limits import DefaultRunLimitResolver

    resolver = get_model_routing_resolver(session)
    model_resolution = LazyModelResolution(
        lambda: resolver.resolve(LLMIntent.CHAT, UUID(user_id), None)
    )

    # ADR-089 Decision 7: the escalation route reuses the SAME resolver
    # instance and user (ANALYSE intent, no project tier — chat has no
    # novel path parameter). Wired ONLY when the pilot flag is on — the
    # default-off DI shape stays byte-identical to the pre-ADR-089 wiring.
    # Nothing resolves here either way (ADR-086: first-use consumption in
    # ChatService.ensure_resolved).
    escalation_resolution: LazyModelResolution | None = None
    if get_core_settings().llm_dynamic_tiering_enabled:
        escalation_resolution = LazyModelResolution(
            lambda: resolver.resolve(LLMIntent.ANALYSE, UUID(user_id), None)
        )

    registry = get_model_registry()
    composer = get_composer()

    # Canonical KB-context provider (ADR-067): single fetch+render source
    # for the chat template's per-type KB slots. Degrades gracefully
    # (RULE-11) — empty bundle on an unavailable repository or empty KB.
    kb_context_provider = KBContextProvider(
        kb_repo=KBRepository(session),
        relationship_repo=RelationshipRepository(session),
    )

    return ChatService(
        prompt_composer=composer,
        model_registry=registry,
        conversation_store=SQLAlchemyConversationStore(session),
        model_resolution=model_resolution,
        invocation_pipeline=get_invocation_pipeline(),
        run_limit_resolver=DefaultRunLimitResolver(),
        note_lookup=get_note_service(session),
        novel_lookup=_NovelOwnedLookup(NovelRepository(session)),
        kb_context_provider=kb_context_provider,
        escalation_resolution=escalation_resolution,
    )
