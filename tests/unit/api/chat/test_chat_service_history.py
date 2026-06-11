"""Unit tests for ChatService — ProcessHistory and history management.

Tests ``ProcessHistory`` tracking across conversational turns (ADR-034)
and the ``get_history()`` / ``clear_history()`` delegation methods.

See conftest.py for shared fixtures.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from narrare_core.agents.base import StreamEvent
from narrare_core.chat.chat_agent import ChatAgent

if TYPE_CHECKING:
    from narrare.chat.chat_service import ChatService
    from narrare_core.chat.conversation_store import InMemoryConversationStore

# ---------------------------------------------------------------------------
# Test ChatService.ask — ProcessHistory Continuity
# ---------------------------------------------------------------------------


class TestProcessHistory:
    """ProcessHistory is tracked per-conversation across multiple turns."""

    async def test_process_history_accumulates_across_turns(
        self,
        service: ChatService,
    ) -> None:
        """Multiple turns to the same conversation accumulate ProcessHistory."""
        from uuid import UUID, uuid4

        from tests.unit.api.chat.conftest import _async_gen, _make_request

        # First turn — new conversation
        user_id = uuid4()
        request1 = _make_request(message="Hi there!", conversation_id=None)

        call_count = 0
        captured_kwargs: list[dict[str, object]] = []

        def _stream_turn1(*args: object, **kwargs: object) -> object:
            nonlocal call_count
            call_count += 1
            captured_kwargs.append(kwargs)
            return _async_gen(
                StreamEvent(type="token", text="Hello!"),
                StreamEvent(
                    type="done",
                    text="Hello!",
                    usage={},
                    new_messages=[f"mock_message_{call_count}"],
                ),
            )

        mock_agent1 = MagicMock(name="mock_agent1", spec=ChatAgent)
        mock_agent1.run_stream = _stream_turn1

        with patch("narrare_core.chat.chat_agent.ChatAgent", return_value=mock_agent1):
            events1 = []
            async for event in await service.ask(request1, user_id):
                events1.append(event)

        # Get the conversation ID from the meta event
        conv_id_str = events1[0]["conversation_id"]
        conv_id = UUID(conv_id_str)

        # Second turn — existing conversation with ProcessHistory
        request2 = _make_request(message="How are you?", conversation_id=conv_id)

        def _stream_turn2(*args: object, **kwargs: object) -> object:
            nonlocal call_count
            call_count += 1
            captured_kwargs.append(kwargs)
            return _async_gen(
                StreamEvent(type="token", text="I'm great!"),
                StreamEvent(
                    type="done",
                    text="I'm great!",
                    usage={},
                    new_messages=[f"mock_message_{call_count}"],
                ),
            )

        mock_agent2 = MagicMock(name="mock_agent2", spec=ChatAgent)
        mock_agent2.run_stream = _stream_turn2

        with patch("narrare_core.chat.chat_agent.ChatAgent", return_value=mock_agent2):
            async for _ in await service.ask(request2, user_id):
                pass

        # Turn 1 should have been called with no message_history
        assert len(captured_kwargs) >= 2
        first_call_history = captured_kwargs[0].get("message_history")
        assert first_call_history is None, "First turn should have no message_history"

        # Turn 2 should have been called with message_history from turn 1
        second_call_history = captured_kwargs[1].get("message_history")
        assert second_call_history is not None, (
            "Second turn should have message_history from first turn"
        )

    async def test_process_history_clears_on_clear_history(
        self,
        service: ChatService,
        in_memory_store: InMemoryConversationStore,
    ) -> None:
        """Clearing conversation history also clears the ProcessHistory."""
        from uuid import UUID, uuid4

        from tests.unit.api.chat.conftest import _async_gen, _make_request

        # Make a first turn to populate ProcessHistory
        user_id = uuid4()

        request1 = _make_request(message="Turn 1", conversation_id=None)

        mock_agent1 = MagicMock(name="mock_agent1", spec=ChatAgent)
        mock_agent1.run_stream = lambda *a, **kw: _async_gen(
            StreamEvent(type="token", text="Response 1"),
            StreamEvent(
                type="done",
                text="Response 1",
                usage={},
                new_messages=["msg1"],
            ),
        )

        with patch("narrare_core.chat.chat_agent.ChatAgent", return_value=mock_agent1):
            events1 = []
            async for event in await service.ask(request1, user_id):
                events1.append(event)

        conv_id = UUID(events1[0]["conversation_id"])

        # Clear history
        await service.clear_history(conv_id)

        # Verify the store was cleared
        history = await in_memory_store.get_history(conv_id)
        assert len(history) == 0


# ---------------------------------------------------------------------------
# Test ChatService — get_history / clear_history
# ---------------------------------------------------------------------------


class TestHistoryManagement:
    """Tests for get_history and clear_history — pure delegation."""

    async def test_get_history_delegates_to_store(
        self,
        service: ChatService,
        in_memory_store: InMemoryConversationStore,
    ) -> None:
        """get_history returns messages from the store."""
        from uuid import uuid4

        # Create a conversation with a message
        project_id = uuid4()
        user_id = uuid4()
        conv_id = await in_memory_store.create_conversation(project_id, user_id, "Test msg")

        result = await service.get_history(conv_id)

        assert len(result) == 1
        assert result[0].role == "user"
        assert result[0].content == "Test msg"

    async def test_get_history_with_limit(
        self,
        service: ChatService,
        in_memory_store: InMemoryConversationStore,
    ) -> None:
        """get_history respects the limit parameter."""
        from uuid import uuid4

        project_id = uuid4()
        user_id = uuid4()
        conv_id = await in_memory_store.create_conversation(project_id, user_id, "Msg 1")
        await in_memory_store.add_message(conv_id, "user", "Msg 2")
        await in_memory_store.add_message(conv_id, "assistant", "Resp 1")
        await in_memory_store.add_message(conv_id, "user", "Msg 3")

        result = await service.get_history(conv_id, limit=2)

        assert len(result) == 2
        assert result[0].content == "Resp 1"
        assert result[1].content == "Msg 3"

    async def test_clear_history_delegates_to_store(
        self,
        service: ChatService,
        in_memory_store: InMemoryConversationStore,
    ) -> None:
        """clear_history removes all messages via the store."""
        from uuid import uuid4

        project_id = uuid4()
        user_id = uuid4()
        conv_id = await in_memory_store.create_conversation(project_id, user_id, "To be deleted")
        await in_memory_store.add_message(conv_id, "assistant", "Gone soon")

        await service.clear_history(conv_id)

        history = await in_memory_store.get_history(conv_id)
        assert len(history) == 0
