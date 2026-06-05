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

import structlog

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

from narrare_core.agents.process_history import ProcessHistory
from narrare_core.chat.chat_service_core import (
    build_chat_context,
    format_history,
    new_conversation_id,
)
from narrare_core.chat.contracts import ChatMessage, ChatRequest, ChatServiceProtocol
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from narrare.chat.conversation_store import SQLAlchemyConversationStore
    from narrare_core.llm import ModelRegistry, ResolvedModelConfig
    from narrare_core.prompts import PromptComposer
    from narrare_core.prompts.composer import ComposedPrompt
    from narrare_core.prompts.context import PromptContext

logger = structlog.get_logger(__name__)


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
    ) -> None:
        """Initialize the chat service with injected dependencies.

        Args:
            prompt_composer: For assembling system + user prompts.
            model_registry: For LLM model resolution and agent creation.
            conversation_store: For message persistence.
            config: Resolved model configuration (provider, model, params).
        """
        self._composer = prompt_composer
        self._registry = model_registry
        self._store = conversation_store
        self._config = config
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
        context = build_chat_context(
            project_title="",
            genre="",
            language="en",
        )
        context.extra["conversation_history"] = format_history(history)

        composed = await self._composer.build(
            LLMIntent.CHAT,
            context,
            user_prompt=request.message,
        )

        # 3. Return the async generator that streams events via ChatAgent
        return self._stream_agent_response(conv_id, composed, context, request.message)

    async def _stream_agent_response(
        self,
        conv_id: UUID,
        composed: ComposedPrompt,
        context: PromptContext,
        user_prompt: str,
    ) -> AsyncIterator[dict[str, object]]:
        """Async generator that streams the chat response via ``ChatAgent.run_stream()``.

        Replaces the old ``_stream_response`` which used ``ModelRegistry.stream()``
        directly (violating ADR-015). Now uses ``ChatAgent`` for agent-based
        streaming with ``ProcessHistory`` for conversational continuity.

        Args:
            conv_id: The conversation UUID.
            composed: The composed prompt (system + user prompts).
            context: The prompt context with project metadata.
            user_prompt: The raw user message text.

        Yields:
            Dict-based SSE events for the streaming response.
        """
        from narrare_core.chat.chat_agent import ChatAgent
        from narrare_core.chat.chat_deps import ChatDeps

        # Get model from registry
        model = await self._registry.get_model(self._config)

        # Create ChatAgent (uses HistoryPolicy.CONVERSATIONAL by design)
        agent = ChatAgent(model=model)

        # Create ChatDeps for the agent
        deps = ChatDeps(
            prompt_composer=self._composer,
            context=context,
            user_prompt=user_prompt,
        )

        # Combine system + user prompt as the agent prompt
        full_prompt = f"{composed.system}\n\n{composed.user}" if composed.system else composed.user

        # Get or create ProcessHistory for this conversation
        history = self._histories.get(conv_id, ProcessHistory())

        # Yield meta event with conversation ID
        yield {
            "type": "meta",
            "conversation_id": str(conv_id),
            "request_id": str(uuid4()),
        }

        # Stream agent response
        full_response = ""
        try:
            async for event in agent.run_stream(
                prompt=full_prompt,
                deps=deps,
                message_history=history.messages if not history.is_empty else None,
            ):
                if event.type == "token":
                    yield {"type": "token", "text": event.text}
                    full_response += event.text
                elif event.type == "done":
                    # Update ProcessHistory with new messages from this turn
                    if event.new_messages:
                        history.add(event.new_messages)
                        self._histories[conv_id] = history

                    yield {
                        "type": "done",
                        "usage": event.usage or {},
                    }
                    # Use the complete text from the done event
                    if event.text:
                        full_response = event.text
        except Exception as exc:
            logger.error(
                "chat_stream_failed",
                conversation_id=str(conv_id),
                error=str(exc),
                exc_info=True,
            )
            # Save partial response before re-raising
            if full_response:
                await self._store.add_message(conv_id, "assistant", full_response)
            raise

        # Save assistant response
        if full_response:
            await self._store.add_message(conv_id, "assistant", full_response)

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

    async def clear_history(
        self,
        conversation_id: UUID,
    ) -> None:
        """Clear conversation history (deletes all messages).

        Args:
            conversation_id: The conversation to clear.
        """
        await self._store.clear_history(conversation_id)
