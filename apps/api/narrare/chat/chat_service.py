"""Chat service — orchestrates the chat flow.

Wires core chat logic (narrare_core.chat) to FastAPI infrastructure:
- SQLAlchemy store for persistence
- PromptComposer for prompt assembly
- ChatAgent via ModelRegistry for agent-based LLM streaming

Follows ChatServiceProtocol from core contracts.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

from narrare.chat._context import build_prompt_context
from narrare_core.agents.process_history import ProcessHistory
from narrare_core.chat.chat_service_core import new_conversation_id
from narrare_core.chat.contracts import ChatMessage, ChatRequest, ChatServiceProtocol
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from narrare.chat.conversation_store import SQLAlchemyConversationStore
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ModelRegistry, ResolvedModelConfig
    from narrare_core.llm.run_limits import DefaultRunLimitResolver
    from narrare_core.prompts import PromptComposer
    from narrare_core.prompts.composer import ComposedPrompt
    from narrare_core.prompts.context import PromptContext


class ChatService(ChatServiceProtocol):
    """Backend chat service — wires core logic to API infrastructure.

    Handles the full chat lifecycle:
    1. Conversation creation or history loading
    2. Context assembly and prompt composition
    3. Agent-based LLM streaming via ChatAgent (ADR-024)
    4. ProcessHistory tracking for conversational continuity (ADR-034)
    5. Message persistence via SQLAlchemyConversationStore
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
        """
        self._composer = prompt_composer
        self._registry = model_registry
        self._store = conversation_store
        self._config = config
        self._invocation_pipeline = invocation_pipeline
        self._run_limit_resolver = run_limit_resolver
        self._api_key = api_key
        self._base_url = base_url
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
            request: The chat request (project_id, message, conversation_id).
            user_id: The authenticated user's UUID.

        Returns:
            AsyncIterator of dict-based SSE events.
        """
        conv_id = request.conversation_id or new_conversation_id()
        is_new = request.conversation_id is None

        # 1. Create conversation or add message to existing
        if is_new:
            conv_id = await self._store.create_conversation(
                request.project_id,
                user_id,
                request.message,
            )
            history: list[ChatMessage] = []
        else:
            assert conv_id is not None
            await self._store.add_message(conv_id, "user", request.message)
            history = await self._store.get_history(conv_id)

        # 2. Build context + compose prompt
        context = build_prompt_context(history)

        composed = await self._composer.build(
            LLMIntent.CHAT,
            context,
            user_prompt=request.message,
        )

        # 3. Return the async generator that streams events via ChatAgent
        return self._stream_agent_response(
            conv_id,
            composed,
            context,
            request.message,
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
        project_id: UUID,
    ) -> AsyncIterator[dict[str, object]]:
        """Stream the chat response via ``ChatAgent.run_stream()`` (ADR-024).

        Composes the ADR-048 Mode 2 invocation first for evidence + enrichment
        (flows to ``ChatDeps``); a no-op when ``invocation_pipeline`` is
        ``None`` (backward compatible). See ``chat._invocation`` for details.

        Args:
            conv_id: The conversation UUID.
            composed: The composed prompt (system + user prompts).
            context: The prompt context with project metadata.
            user_prompt: The raw user message text.
            user_id: The authenticated user's UUID (ADR-045 Decision 6).
            project_id: The project UUID for enrichment correlation.

        Yields:
            Dict-based SSE events for the streaming response.
        """
        from narrare.chat._invocation import compose_chat_invocation, resolve_chat_run_limits
        from narrare.chat._sse_stream import stream_agent_events
        from narrare_core.chat.chat_agent import ChatAgent
        from narrare_core.chat.chat_deps import ChatDeps

        # Get model from registry — api_key/base_url carry the resolved
        # per-user credentials (model-routing cascade) into the actual
        # resolution point.
        model = await self._registry.get_model(
            self._config, api_key=self._api_key, base_url=self._base_url
        )

        # Compose the invocation (Mode 2) → enriched context for ChatDeps.
        invocation_id = uuid4()
        effective_context = await compose_chat_invocation(
            invocation_pipeline=self._invocation_pipeline,
            prompt_ctx=context,
            user_id=user_id,
            project_id=project_id,
            conv_id=conv_id,
            invocation_id=invocation_id,
        )

        # Create ChatAgent (HistoryPolicy.CONVERSATIONAL). ADR-046: inject the
        # feature system prompt into the SYSTEM channel via the constructor,
        # never concatenated into the user prompt.
        agent = ChatAgent(model=model, system_prompt=composed.system or None)

        # ChatDeps carries the enriched context to the agent (ADR-048 Mode 2).
        deps = ChatDeps(
            prompt_composer=self._composer,
            context=effective_context,
            user_prompt=user_prompt,
        )

        # Get or create ProcessHistory for this conversation
        history = self._histories.get(conv_id, ProcessHistory())

        # Resolve run limits when a resolver is wired (ADR-045 Decision 4).
        message_history = history.messages if not history.is_empty else None
        stream_kwargs = resolve_chat_run_limits(
            resolver=self._run_limit_resolver,
            config=self._config,
            invocation_id=invocation_id,
        )

        # Map the agent stream to chat SSE events (ADR-024/ADR-034) and
        # persist the response — delegated to the RULE-04 bridge helper.
        async for event in stream_agent_events(
            agent=agent,
            deps=deps,
            prompt=composed.user,
            message_history=message_history,
            stream_kwargs=stream_kwargs,
            conv_id=conv_id,
            history=history,
            histories=self._histories,
            store=self._store,
        ):
            yield event

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
            The project UUID, or None if the conversation does not exist.
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
