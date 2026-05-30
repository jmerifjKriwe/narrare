"""Chat service — orchestrates the chat flow.

Wires core chat logic (narrare_core.chat) to FastAPI infrastructure:
- SQLAlchemy store for persistence
- PromptComposer for prompt assembly
- ModelRegistry for LLM streaming

Follows ChatServiceProtocol from core contracts.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import structlog

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

from narrare_core.chat.chat_service_core import (
    build_chat_context,
    format_history,
    new_conversation_id,
)
from narrare_core.chat.contracts import ChatMessage, ChatRequest, ChatServiceProtocol
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from narrare.chat.conversation_store import SQLAlchemyConversationStore
    from narrare_core.llm import ModelRegistry
    from narrare_core.llm.intents import ResolvedModelConfig
    from narrare_core.prompts import PromptComposer

logger = structlog.get_logger(__name__)


class ChatService(ChatServiceProtocol):
    """Backend chat service — wires core logic to API infrastructure.

    Handles the full chat lifecycle:
    1. Conversation creation or history loading
    2. Context assembly and prompt composition
    3. LLM streaming via ModelRegistry
    4. Message persistence via SQLAlchemyConversationStore
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
            model_registry: For LLM model resolution and streaming.
            conversation_store: For message persistence.
            config: Resolved model configuration (provider, model, params).
        """
        self._composer = prompt_composer
        self._registry = model_registry
        self._store = conversation_store
        self._config = config

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

        # 3. Return the async generator that streams events
        return self._stream_response(conv_id, composed)

    async def _stream_response(
        self,
        conv_id: UUID,
        composed: object,
    ) -> AsyncIterator[dict[str, object]]:
        """Async generator that yields SSE events for the chat response.

        Separated from ``ask()`` to maintain type compatibility with
        ``ChatServiceProtocol`` — async generators cannot be returned
        directly from protocol ``async def`` methods.

        Args:
            conv_id: The conversation UUID.
            composed: The composed prompt (ComposedPrompt).

        Yields:
            Dict-based SSE events for the streaming response.
        """
        # Import here to avoid circular imports at module level
        from narrare_core.prompts.composer import ComposedPrompt

        assert isinstance(composed, ComposedPrompt)

        # Yield meta event with conversation ID
        yield {
            "type": "meta",
            "conversation_id": str(conv_id),
            "request_id": str(uuid4()),
        }

        # Stream LLM response
        full_response = ""
        try:
            async for chunk in self._registry.stream(
                intent=LLMIntent.CHAT,
                system_prompt=composed.system,
                user_prompt=composed.user,
                config=self._config,
            ):
                if chunk.is_final:
                    yield {
                        "type": "done",
                        "usage": {
                            "prompt_tokens": chunk.usage.prompt_tokens if chunk.usage else 0,
                            "completion_tokens": chunk.usage.completion_tokens
                            if chunk.usage
                            else 0,
                            "total_tokens": chunk.usage.total_tokens if chunk.usage else 0,
                        }
                        if chunk.usage
                        else {},
                    }
                else:
                    yield {"type": "token", "text": chunk.text}
                    full_response += chunk.text
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
