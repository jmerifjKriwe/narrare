"""Chat service — orchestrates the chat flow.

Wires core chat logic (narrare_core.chat) to FastAPI infrastructure:
- SQLAlchemy store for persistence
- PromptComposer for prompt assembly
- ChatAgent via ModelRegistry for agent-based LLM streaming

Follows ChatServiceProtocol from core contracts.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

from narrare.chat._context import (
    build_prompt_context,
    resolve_chat_kb_vars,
    resolve_effective_message,
    resolve_owned_novel,
)
from narrare_core.chat.chat_service_core import new_conversation_id
from narrare_core.chat.contracts import ChatMessage, ChatRequest, ChatServiceProtocol
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from narrare.chat.conversation_store import SQLAlchemyConversationStore
    from narrare.kb.context_contracts import KBContextProviderProtocol
    from narrare.notes.contracts import OwnedLinkLookupProtocol
    from narrare_core.agents.process_history import ProcessHistory
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ModelRegistry, ResolvedModelConfig
    from narrare_core.llm.run_limits import DefaultRunLimitResolver
    from narrare_core.notes.contracts import NoteLookupProtocol
    from narrare_core.prompts import PromptComposer
    from narrare_core.prompts.composer import ComposedPrompt
    from narrare_core.prompts.context import PromptContext


class ChatService(ChatServiceProtocol):
    """Backend chat service — wires core logic to API infrastructure.

    Handles the full chat lifecycle:
    1. Conversation creation or history loading
    2. Note context injection into the user message (NOTES-001 §6b —
       runtime-input channel, RULE-02)
    3. Context assembly and prompt composition
    4. Agent-based LLM streaming via ChatAgent (ADR-024)
    5. ProcessHistory tracking for conversational continuity (ADR-034)
    6. Message persistence via SQLAlchemyConversationStore
    """

    def __init__(
        self,
        prompt_composer: PromptComposer,
        model_registry: ModelRegistry,
        conversation_store: SQLAlchemyConversationStore,
        config: ResolvedModelConfig,
        invocation_pipeline: InvocationPipeline | None = None,
        run_limit_resolver: DefaultRunLimitResolver | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        note_lookup: NoteLookupProtocol | None = None,
        novel_lookup: OwnedLinkLookupProtocol | None = None,
        kb_context_provider: KBContextProviderProtocol | None = None,
    ) -> None:
        """Initialize the chat service with injected dependencies.

        Args:
            prompt_composer: For assembling system + user prompts.
            model_registry: For LLM model resolution and agent creation.
            conversation_store: For message persistence.
            config: Resolved model configuration (provider, model, params).
            invocation_pipeline: Optional pipeline for chat-invocation evidence
                and enrichment (ADR-045/ADR-048); ``None`` (default) is a no-op.
            run_limit_resolver: Optional run-limit resolver (ADR-045 Decision 4);
                ``None`` (default) applies no limits to the stream.
            api_key: Resolved per-user credential for the model registry call
                (model-routing cascade). ``None`` only in the unit-test
                harness; production wiring always supplies it via the DI
                factory.
            base_url: Resolved base-URL override for OpenAI-compatible
                providers. ``None`` uses the provider default endpoint.
            note_lookup: Optional ``NoteLookupProtocol`` (NOTES-001 §6b) —
                resolves ``note_id`` requests into a note whose context
                block is prepended to the user message (runtime input,
                RULE-02). ``None`` (default) disables note injection.
            novel_lookup: Optional ``OwnedLinkLookupProtocol`` (notes
                pattern) — validates that a non-null ``project_id``
                belongs to the caller BEFORE any write or enrichment
                correlation (IDOR hardening). ``None`` (default) skips the
                check; production wiring (``chat.dependencies``) always
                provides it, mirroring the notes T7-review invariant.
            kb_context_provider: Canonical ``KBContextProviderProtocol``
                (ADR-067) for the chat template's per-type KB slots;
                ``None`` (default, test contexts) keeps them empty.
        """
        self._composer = prompt_composer
        self._registry = model_registry
        self._store = conversation_store
        self._config = config
        self._invocation_pipeline = invocation_pipeline
        self._run_limit_resolver = run_limit_resolver
        self._api_key = api_key
        self._base_url = base_url
        self._note_lookup = note_lookup
        self._novel_lookup = novel_lookup
        self._kb_context_provider = kb_context_provider
        self._histories: dict[UUID, ProcessHistory] = {}

    async def ask(
        self,
        request: ChatRequest,
        user_id: UUID,
    ) -> AsyncIterator[dict[str, object]]:
        """Process a chat message and stream the response.

        Yields SSE events:
        - ``{"type": "meta", "conversation_id": ..., "request_id": ...}``
        - ``{"type": "token", "text": ...}`` (zero or more)
        - ``{"type": "done", "usage": {...}}``

        Uses ``ChatAgent`` (via ``ChatAgent.run_stream()``) with
        ``ProcessHistory`` for conversational continuity across turns.

        Args:
            request: The chat request — ``project_id`` is optional since
                NOTES-001 §6b (project-less chat skips KB/project context
                tiers); ``note_id`` attaches a scratchpad note as a
                runtime context block in the user message (NOTES-001 §6b).
            user_id: The authenticated user's UUID.

        Returns:
            AsyncIterator of dict-based SSE events.
        """
        conv_id = request.conversation_id or new_conversation_id()
        is_new = request.conversation_id is None

        # 0. NOTES-001 §6b: attach a requested note as RUNTIME INPUT — its
        # context block is prepended to the user message, never baked into
        # a prompt template (RULE-02). Missing/unowned notes degrade
        # gracefully inside the resolver (warn + proceed, RULE-11).
        message = await resolve_effective_message(
            note_lookup=self._note_lookup,
            note_id=request.note_id,
            message=request.message,
            user_id=user_id,
        )

        # 0.5 Project link ownership (IDOR hardening, notes ``_validate_link``
        # pattern): a non-null ``project_id`` must belong to the caller —
        # BEFORE the conversation is created/referenced and before the id
        # feeds invocation enrichment correlation. Foreign and unknown
        # novels are indistinguishable (NotFoundError → HTTP 404). The
        # owned novel feeds the prompt-context metadata (FO-7 follow-up:
        # the seam no longer holds zero novel data).
        novel = await resolve_owned_novel(
            novel_lookup=self._novel_lookup,
            project_id=request.project_id,
            user_id=user_id,
        )

        # 1. Create conversation or add message to existing
        if is_new:
            conv_id = await self._store.create_conversation(
                request.project_id,
                user_id,
                message,
            )
            history: list[ChatMessage] = []
        else:
            assert conv_id is not None
            # Ownership gate BEFORE the write (IDOR hardening): a foreign
            # or unknown conversation raises NotFoundError before any
            # message row is appended — no write pollution, and (against
            # PostgreSQL) no FK-violation 500 for unknown ids.
            await self._store.get_conversation(conv_id, user_id)
            await self._store.add_message(conv_id, "user", message)
            history = await self._store.get_history(conv_id, user_id)

        # 1.5 Canonical KB context (ADR-067) — RULE-11 degradation inside.
        kb_vars = await resolve_chat_kb_vars(
            kb_context_provider=self._kb_context_provider,
            novel_id=request.project_id,
        )

        # 2. Build context + compose prompt
        context = build_prompt_context(history, novel=novel, kb_vars=kb_vars)

        composed = await self._composer.build(
            LLMIntent.CHAT,
            context,
            user_prompt=message,
        )

        # 3. Return the async generator that streams events via ChatAgent
        return self._stream_agent_response(
            conv_id=conv_id,
            composed=composed,
            context=context,
            user_prompt=message,
            user_id=user_id,
            project_id=request.project_id,
        )

    async def _stream_agent_response(
        self,
        conv_id: UUID,
        composed: ComposedPrompt,
        context: PromptContext,
        user_prompt: str,
        *,
        user_id: UUID,
        project_id: UUID | None,
    ) -> AsyncIterator[dict[str, object]]:
        """Stream one turn — thin delegation (RULE-04) to ``chat._agent_stream``."""
        from narrare.chat._agent_stream import stream_agent_response

        async for event in stream_agent_response(
            registry=self._registry,
            config=self._config,
            api_key=self._api_key,
            base_url=self._base_url,
            composer=self._composer,
            store=self._store,
            histories=self._histories,
            invocation_pipeline=self._invocation_pipeline,
            run_limit_resolver=self._run_limit_resolver,
            conv_id=conv_id,
            composed=composed,
            context=context,
            user_prompt=user_prompt,
            user_id=user_id,
            project_id=project_id,
        ):
            yield event

    async def get_history(
        self,
        conversation_id: UUID,
        user_id: UUID,
        *,
        limit: int = 50,
    ) -> list[ChatMessage]:
        """Get conversation history for its owner.

        Args:
            conversation_id: The conversation to retrieve.
            user_id: The authenticated user — must own the conversation.
            limit: Maximum number of messages (newest first). Defaults to 50.

        Returns:
            List of ChatMessage dataclasses ordered by creation time.

        Raises:
            NotFoundError: The conversation does not exist or is owned by
                another user (mapped to HTTP 404).
        """
        return await self._store.get_history(conversation_id, user_id, limit=limit)

    async def get_project_id_for_conversation(
        self,
        conversation_id: UUID,
        user_id: UUID,
    ) -> UUID | None:
        """Get the project_id associated with a conversation.

        Args:
            conversation_id: The conversation to look up.
            user_id: The authenticated user — must own the conversation.

        Returns:
            The project UUID, or ``None`` for a project-less conversation
            (NOTES-001 §6b).

        Raises:
            NotFoundError: The conversation does not exist or is owned by
                another user (mapped to HTTP 404).
        """
        return await self._store.get_conversation_project_id(conversation_id, user_id)

    async def clear_history(
        self,
        conversation_id: UUID,
        user_id: UUID,
    ) -> None:
        """Clear conversation history (deletes all messages).

        Args:
            conversation_id: The conversation to clear.
            user_id: The authenticated user — must own the conversation.

        Raises:
            NotFoundError: The conversation does not exist or is owned by
                another user (mapped to HTTP 404).
        """
        await self._store.clear_history(conversation_id, user_id)
