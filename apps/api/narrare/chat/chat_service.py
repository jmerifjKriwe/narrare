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

from narrare_core.chat.chat_service_core import new_conversation_id
from narrare_core.chat.contracts import ChatMessage, ChatRequest, ChatServiceProtocol

if TYPE_CHECKING:
    from narrare.chat.conversation_store import SQLAlchemyConversationStore
    from narrare_core.agents.process_history import ProcessHistory
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ModelRegistry, ResolvedModelConfig
    from narrare_core.llm.run_limits import DefaultRunLimitResolver
    from narrare_core.notes.contracts import NoteLookupProtocol
    from narrare_core.prompts import PromptComposer


class ChatService(ChatServiceProtocol):
    """Backend chat service — wires core logic to API infrastructure.

    Handles the full chat lifecycle:
    1. Conversation creation or history loading
    2. Note context injection into the user message (NOTES-001 §6b —
       runtime-input channel, RULE-02)
    3. Context assembly and prompt composition
    4. Agent-based LLM streaming via ChatAgent (ADR-024; delegated to
       ``chat._streaming``)
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
        note_lookup: NoteLookupProtocol | None = None,
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
            note_lookup: Optional ``NoteLookupProtocol`` (NOTES-001 §6b) —
                resolves ``note_id`` requests into a note whose context
                block is prepended to the user message (runtime input,
                RULE-02). ``None`` (default) disables note injection.
        """
        self._composer = prompt_composer
        self._registry = model_registry
        self._store = conversation_store
        self._config = config
        self._invocation_pipeline = invocation_pipeline
        self._run_limit_resolver = run_limit_resolver
        self._note_lookup = note_lookup
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

        from narrare.chat._context import (
            assemble_chat_context,
            compose_chat_prompt,
            resolve_effective_message,
        )
        from narrare.chat._streaming import stream_chat_response

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
            await self._store.add_message(conv_id, "user", message)
            history = await self._store.get_history(conv_id)

        # 2. Build context + compose prompt
        context = assemble_chat_context(history)
        composed = await compose_chat_prompt(self._composer, context, message)

        # 3. Return the async generator that streams events via ChatAgent
        return stream_chat_response(
            registry=self._registry,
            config=self._config,
            composer=self._composer,
            store=self._store,
            histories=self._histories,
            invocation_pipeline=self._invocation_pipeline,
            run_limit_resolver=self._run_limit_resolver,
            conv_id=conv_id,
            composed=composed,
            context=context,
            user_prompt=message,
            user_id=user_id,
            project_id=request.project_id,
        )

    async def get_history(
        self,
        conversation_id: UUID,
        *,
        limit: int = 50,
    ) -> list[ChatMessage]:
        """Get conversation history.

        Args:
            conversation_id: The conversation to retrieve.
            limit: Maximum number of messages (newest first). Defaults to 50.

        Returns:
            List of ChatMessage dataclasses ordered by creation time.
        """
        return await self._store.get_history(conversation_id, limit=limit)

    async def get_project_id_for_conversation(
        self,
        conversation_id: UUID,
    ) -> UUID | None:
        """Get the project_id associated with a conversation.

        Args:
            conversation_id: The conversation to look up.

        Returns:
            The project UUID, or ``None`` (project-less, NOTES-001 §6b, or not found).
        """
        return await self._store.get_conversation_project_id(conversation_id)

    async def clear_history(
        self,
        conversation_id: UUID,
    ) -> None:
        """Clear conversation history (deletes all messages).

        Args:
            conversation_id: The conversation to clear.
        """
        await self._store.clear_history(conversation_id)
