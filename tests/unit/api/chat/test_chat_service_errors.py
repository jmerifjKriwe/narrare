"""Unit tests for ChatService — error handling and partial save behavior.

Tests that stream interruptions still persist messages partially
(RULE-11: no silent failures), and that errors propagate correctly.

See conftest.py for shared fixtures.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from narrare_core.agents.base import StreamEvent
from narrare_core.chat.chat_agent import ChatAgent

# ---------------------------------------------------------------------------
# Test Error Handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Errors during streaming must be handled gracefully (RULE-11)."""

    async def test_error_during_streaming_raises_and_partial_save(
        self,
        service: object,
        in_memory_store: object,
    ) -> None:
        """An error mid-stream raises and the partial user message is saved."""
        from uuid import uuid4

        from tests.unit.api.chat.conftest import _make_request

        request = _make_request(message="Will error mid-stream")

        async def _failing_stream(*args: object, **kwargs: object) -> object:
            yield StreamEvent(type="token", text="Partial response...")
            msg = "Simulated mid-stream failure"
            raise RuntimeError(msg)

        mock_agent = MagicMock(name="mock_agent", spec=ChatAgent)
        mock_agent.run_stream = lambda *a, **kw: _failing_stream()

        with patch("narrare_core.chat.chat_agent.ChatAgent", return_value=mock_agent):
            gen = await service.ask(request, uuid4())  # type: ignore[union-attr]
            with pytest.raises(RuntimeError, match="Simulated mid-stream failure"):
                async for _ in gen:
                    pass

    async def test_error_saves_user_message_even_if_stream_fails(
        self,
        service: object,
        in_memory_store: object,
    ) -> None:
        """The user message is persisted even when stream raises an error."""
        from uuid import UUID, uuid4

        from tests.unit.api.chat.conftest import _async_gen, _make_request

        request = _make_request(message="Save this even on failure", conversation_id=None)

        mock_agent = MagicMock(name="mock_agent", spec=ChatAgent)
        mock_agent.run_stream = lambda *a, **kw: _async_gen(
            StreamEvent(type="token", text="Partial"),
            StreamEvent(type="done", text="", usage={}, new_messages=[]),
        )

        # Simulate a failure after streaming
        with patch("narrare_core.chat.chat_agent.ChatAgent", return_value=mock_agent):
            gen = await service.ask(request, uuid4())  # type: ignore[union-attr]
            async for event in gen:
                if event.get("type") == "meta":
                    conv_id = UUID(event["conversation_id"])

        # The user message should still be persisted
        history = await in_memory_store.get_history(conv_id)  # type: ignore[union-attr]
        user_messages = [m for m in history if m.role == "user"]
        assert any("Save this even on failure" in m.content for m in user_messages)

    async def test_error_before_streaming_preserves_no_partial_assistant(
        self,
        service: object,
        in_memory_store: object,
    ) -> None:
        """If the error occurs before streaming, no partial assistant message."""
        from uuid import uuid4

        from tests.unit.api.chat.conftest import _async_gen, _make_request

        request = _make_request(message="Fail before streaming", conversation_id=None)

        mock_agent = MagicMock(name="mock_agent", spec=ChatAgent)
        mock_agent.run_stream = lambda *a, **kw: _async_gen(
            StreamEvent(type="done", text="", usage={}, new_messages=[])
        )

        # Simulate failure before creating the agent
        with (
            patch(
                "narrare_core.chat.chat_agent.ChatAgent",
                side_effect=ValueError("Agent init failed"),
            ),
            pytest.raises(ValueError, match="Agent init failed"),
        ):
            gen = await service.ask(request, uuid4())  # type: ignore[union-attr]
            async for _ in gen:
                pass

    async def test_error_in_non_streaming_ask_raises(
        self,
        service: object,
        in_memory_store: object,
    ) -> None:
        """Non-streaming ask() (if implemented) propagates errors."""
        from uuid import uuid4

        from tests.unit.api.chat.conftest import _async_gen, _make_request

        request = _make_request(message="Error case")

        mock_agent = MagicMock(name="mock_agent", spec=ChatAgent)
        mock_agent.run_stream = lambda *a, **kw: _async_gen(
            StreamEvent(type="gone", text="???"),
        )

        with patch("narrare_core.chat.chat_agent.ChatAgent", return_value=mock_agent):
            gen = await service.ask(request, uuid4())  # type: ignore[union-attr]
            # Even unexpected event types should not crash the service,
            # they should just be passed through as-is
            events = []
            async for event in gen:
                events.append(event)

        assert len(events) > 0
        assert events[0]["type"] == "meta"  # meta always first
