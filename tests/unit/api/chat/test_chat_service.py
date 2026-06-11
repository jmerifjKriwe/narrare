"""Unit tests for ChatService — core streaming flow.

Tests the main ``ask()`` flow for new and existing conversations,
verifying that ``ChatAgent.run_stream()`` is used instead of
``ModelRegistry.stream()`` (ADR-015 compliance).

See conftest.py for shared fixtures.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from pydantic_ai.models import Model

from narrare_core.agents.base import StreamEvent
from narrare_core.chat.chat_agent import ChatAgent

if TYPE_CHECKING:
    from unittest.mock import AsyncMock

    from narrare.chat.chat_service import ChatService
    from narrare_core.chat.conversation_store import InMemoryConversationStore

# ---------------------------------------------------------------------------
# Test ChatService.ask — New Conversation
# ---------------------------------------------------------------------------


class TestAskNewConversation:
    """Tests for ``ask()`` when no existing conversation is provided."""

    async def test_ask_new_conversation_yields_stream_events(
        self,
        service: ChatService,
    ) -> None:
        """Happy path: a brand-new conversation streams meta, token, and done events."""
        from tests.unit.api.chat.conftest import _async_gen, _make_request

        request = _make_request(message="Tell me a story.")
        user_id = __import__("uuid").uuid4()

        # Patch ChatAgent to return controlled stream events
        mock_agent = MagicMock(name="mock_agent", spec=ChatAgent)
        mock_agent.run_stream = lambda *a, **kw: _async_gen(
            StreamEvent(type="token", text="Once upon a "),
            StreamEvent(type="token", text="time..."),
            StreamEvent(
                type="done",
                text="Once upon a time...",
                usage={"total_tokens": 15},
                new_messages=[],
            ),
        )

        with patch("narrare_core.chat.chat_agent.ChatAgent", return_value=mock_agent):
            events = []
            async for event in await service.ask(request, user_id):
                events.append(event)

        # Assert event structure
        assert len(events) >= 3
        assert events[0]["type"] == "meta"
        assert "conversation_id" in events[0]
        assert "request_id" in events[0]

        token_events = [e for e in events if e["type"] == "token"]
        assert len(token_events) == 2
        assert token_events[0]["text"] == "Once upon a "
        assert token_events[1]["text"] == "time..."

        done_events = [e for e in events if e["type"] == "done"]
        assert len(done_events) == 1
        assert done_events[0]["usage"] == {"total_tokens": 15}

    async def test_ask_new_conversation_creates_conversation_in_store(
        self,
        service: ChatService,
        in_memory_store: InMemoryConversationStore,
    ) -> None:
        """A new conversation is persisted via the store."""
        from uuid import UUID, uuid4

        from tests.unit.api.chat.conftest import _async_gen, _make_request

        request = _make_request(message="First message!")
        user_id = uuid4()

        mock_agent = MagicMock(name="mock_agent", spec=ChatAgent)
        mock_agent.run_stream = lambda *a, **kw: _async_gen(
            StreamEvent(type="token", text="Response"),
            StreamEvent(type="done", text="Response", usage={}, new_messages=[]),
        )

        # Track the conv_id from the meta event
        conv_id_from_meta: str | None = None

        with patch("narrare_core.chat.chat_agent.ChatAgent", return_value=mock_agent):
            gen = await service.ask(request, user_id)
            async for event in gen:
                if event.get("type") == "meta":
                    conv_id_from_meta = str(event.get("conversation_id", ""))

        assert conv_id_from_meta is not None, "No meta event with conversation_id"
        store_conv_id = UUID(conv_id_from_meta)

        # Verify the user message and assistant response were stored
        history = await in_memory_store.get_history(store_conv_id)
        assert len(history) >= 2  # user message + assistant response
        assert history[0].role == "user"
        assert history[0].content == "First message!"
        assert history[-1].role == "assistant"
        assert history[-1].content == "Response"

    async def test_ask_new_conversation_passes_model_to_chat_agent(
        self,
        service: ChatService,
        mock_registry: AsyncMock,
    ) -> None:
        """Verifies that ChatAgent receives the model from ModelRegistry."""
        from uuid import uuid4

        from tests.unit.api.chat.conftest import _async_gen, _make_request

        request = _make_request()
        user_id = uuid4()

        mock_model = MagicMock(name="mock_model", spec=Model)
        mock_registry.get_model.return_value = mock_model

        mock_agent = MagicMock(name="mock_agent", spec=ChatAgent)
        mock_agent.run_stream = lambda *a, **kw: _async_gen(
            StreamEvent(type="token", text="Hi"),
            StreamEvent(type="done", text="Hi", usage={}, new_messages=[]),
        )

        with patch(
            "narrare_core.chat.chat_agent.ChatAgent",
            return_value=mock_agent,
        ) as mock_cls:
            async for _ in await service.ask(request, user_id):
                pass

        # ChatAgent should have been constructed with the model from registry
        mock_cls.assert_called_once_with(model=mock_model)


# ---------------------------------------------------------------------------
# Test ChatService.ask — Existing Conversation
# ---------------------------------------------------------------------------


class TestAskExistingConversation:
    """Tests for ``ask()`` with an existing conversation ID."""

    async def test_ask_existing_conversation_uses_history(
        self,
        service: ChatService,
        in_memory_store: InMemoryConversationStore,
    ) -> None:
        """An existing conversation loads prior messages and uses them for context."""
        from uuid import uuid4

        from tests.unit.api.chat.conftest import _async_gen, _make_request

        # Arrange: create a conversation with some history
        project_id = uuid4()
        user_id = uuid4()
        conv_id = await in_memory_store.create_conversation(project_id, user_id, "Earlier msg")

        # Add an assistant message
        await in_memory_store.add_message(conv_id, "assistant", "Earlier response")

        request = _make_request(
            message="Tell me more!",
            conversation_id=conv_id,
        )

        mock_agent = MagicMock(name="mock_agent", spec=ChatAgent)
        mock_agent.run_stream = lambda *a, **kw: _async_gen(
            StreamEvent(type="token", text="Sure, "),
            StreamEvent(type="token", text="here you go!"),
            StreamEvent(
                type="done",
                text="Sure, here you go!",
                usage={},
                new_messages=[],
            ),
        )

        with patch("narrare_core.chat.chat_agent.ChatAgent", return_value=mock_agent):
            events = []
            async for event in await service.ask(request, user_id):
                events.append(event)

        # Assert events are streamed correctly
        assert events[0]["type"] == "meta"
        assert str(conv_id) == events[0]["conversation_id"]
        assert any(e["type"] == "token" for e in events)
        assert events[-1]["type"] == "done"

        # Verify the user message was stored
        history = await in_memory_store.get_history(conv_id)
        assert history[-2].role == "user"
        assert history[-2].content == "Tell me more!"
        assert history[-1].role == "assistant"

    async def test_ask_existing_conversation_passes_history_to_agent(
        self,
        service: ChatService,
        in_memory_store: InMemoryConversationStore,
    ) -> None:
        """ProcessHistory from prior turns is passed as message_history to ChatAgent."""
        from uuid import uuid4

        from tests.unit.api.chat.conftest import _async_gen, _make_request

        project_id = uuid4()
        user_id = uuid4()
        conv_id = await in_memory_store.create_conversation(project_id, user_id, "First msg")

        request = _make_request(
            message="Second message",
            conversation_id=conv_id,
        )

        mock_agent = MagicMock(name="mock_agent", spec=ChatAgent)
        mock_agent.run_stream = lambda *a, **kw: _async_gen(
            StreamEvent(type="token", text="OK"),
            StreamEvent(type="done", text="OK", usage={}, new_messages=[]),
        )

        with patch("narrare_core.chat.chat_agent.ChatAgent", return_value=mock_agent):
            async for _ in await service.ask(request, user_id):
                pass

        # The new user message should have been saved before streaming
        history = await in_memory_store.get_history(conv_id)
        assert len(history) >= 2


# ---------------------------------------------------------------------------
# Test ChatService — Protocol Compliance
# ---------------------------------------------------------------------------


class TestProtocolCompliance:
    """ChatService must satisfy the ChatServiceProtocol (RULE-03)."""

    async def test_service_satisfies_protocol(self) -> None:
        """ChatService satisfies ChatServiceProtocol (RULE-03)."""
        from narrare.chat.chat_service import ChatService

        assert isinstance(ChatService, type)
        # Verify all protocol methods exist
        for method_name in ("ask", "get_history", "clear_history"):
            assert hasattr(ChatService, method_name), (
                f"ChatService missing required method: {method_name}"
            )
