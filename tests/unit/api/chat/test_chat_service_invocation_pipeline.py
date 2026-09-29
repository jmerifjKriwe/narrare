"""Unit tests for ChatService with InvocationPipeline (ADR-045/ADR-048).

Verifies:
- ``ChatService.ask()`` works with a wired ``InvocationPipeline``.
- Streaming events (meta, token, done) are produced correctly.
- ``resolve_chat_run_limits()`` passes ``usage_limits`` and
  ``model_settings`` to ``agent.run_stream()``.
- Conversation persistence works with pipeline wired.
- Backward compatibility: ``invocation_pipeline=None`` preserves
  pre-pipeline behavior.

Split from ``test_chat_service_invocation.py`` for RULE-04 compliance.

See:
    ADR-045, ADR-048, CONSTRAINTS.md RULE-04/RULE-13.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    from unittest.mock import AsyncMock

    from narrare.chat.chat_service import ChatService
    from narrare.chat.conversation_store import SQLAlchemyConversationStore
    from narrare_core.chat.conversation_store import InMemoryConversationStore

# ---------------------------------------------------------------------------
# Tests for ChatService integration with pipeline + resolver
# ---------------------------------------------------------------------------


class TestChatServiceWithPipeline:
    """ChatService streaming works correctly with pipeline + resolver wired."""

    async def test_ask_with_pipeline_streams_correctly(
        self,
        mock_composer: AsyncMock,
        mock_registry: AsyncMock,
        in_memory_store: InMemoryConversationStore,
        mock_config: MagicMock,
    ) -> None:
        """With ``invocation_pipeline`` wired, ``ask()`` produces the same
        streaming events (meta, token, done)."""
        from uuid import uuid4

        from tests.unit.api.chat.conftest import _async_gen, _make_request

        from narrare.chat.chat_service import ChatService
        from narrare_core.agents.base import StreamEvent
        from narrare_core.ai_invocation.pipeline import InvocationPipeline
        from narrare_core.chat.chat_agent import ChatAgent

        request = _make_request(message="Hello!")
        user_id = uuid4()

        # Wire a real pipeline (no-op enrichers — always PASS).
        pipeline = InvocationPipeline()

        from tests.unit.api.chat.conftest import _static_resolution

        service = ChatService(
            prompt_composer=mock_composer,
            model_registry=mock_registry,
            conversation_store=cast("SQLAlchemyConversationStore", in_memory_store),
            model_resolution=_static_resolution(mock_config),
            invocation_pipeline=pipeline,
        )

        # Mock ChatAgent to return controlled stream events
        mock_agent = MagicMock(name="mock_agent", spec=ChatAgent)
        mock_agent.run_stream = lambda *a, **kw: _async_gen(
            StreamEvent(type="token", text="Hello there!"),
            StreamEvent(
                type="done",
                text="Hello there!",
                usage={"total_tokens": 10},
                new_messages=[],
            ),
        )

        with patch("narrare_core.chat.chat_agent.ChatAgent", return_value=mock_agent):
            events = []
            async for event in await service.ask(request, user_id):
                events.append(event)

        # Assert event structure is unchanged
        assert events[0]["type"] == "meta"
        assert "conversation_id" in events[0]
        assert events[-1]["type"] == "done"
        assert events[-1]["usage"] == {"total_tokens": 10}

        token_events = [e for e in events if e["type"] == "token"]
        assert len(token_events) == 1
        assert token_events[0]["text"] == "Hello there!"

    async def test_ask_with_pipeline_and_resolver_streams_correctly(
        self,
        mock_composer: AsyncMock,
        mock_registry: AsyncMock,
        in_memory_store: InMemoryConversationStore,
    ) -> None:
        """With both ``invocation_pipeline`` and ``run_limit_resolver`` wired,
        ``ask()`` produces the same streaming events."""
        from uuid import uuid4

        from tests.unit.api.chat.conftest import _async_gen, _make_request

        from narrare.chat.chat_service import ChatService
        from narrare_core.ai_invocation.pipeline import InvocationPipeline
        from narrare_core.chat.chat_agent import ChatAgent
        from narrare_core.llm import ResolvedModelConfig
        from narrare_core.llm.run_limits import DefaultRunLimitResolver

        request = _make_request(message="Hi!")
        user_id = uuid4()

        # Use a real ResolvedModelConfig so DefaultRunLimitResolver can
        # read ``token_limit_profile`` as a valid string.
        config = ResolvedModelConfig(
            provider_name="test",
            model_id="test-model",
            token_limit_profile="quick",
            max_tokens=500,
        )
        pipeline = InvocationPipeline()
        resolver = DefaultRunLimitResolver()

        from tests.unit.api.chat.conftest import _static_resolution

        service = ChatService(
            prompt_composer=mock_composer,
            model_registry=mock_registry,
            conversation_store=cast("SQLAlchemyConversationStore", in_memory_store),
            model_resolution=_static_resolution(config),
            invocation_pipeline=pipeline,
            run_limit_resolver=resolver,
        )

        mock_agent = MagicMock(name="mock_agent", spec=ChatAgent)
        from narrare_core.agents.base import StreamEvent

        # Track what kwargs run_stream was called with
        run_stream_kwargs: dict[str, object] = {}

        def _tracking_run_stream(*args: object, **kwargs: object) -> object:
            nonlocal run_stream_kwargs
            run_stream_kwargs = {
                k: v for k, v in kwargs.items() if k in ("usage_limits", "model_settings")
            }
            return _async_gen(
                StreamEvent(type="token", text="Response"),
                StreamEvent(type="done", text="Response", usage={}, new_messages=[]),
            )

        mock_agent.run_stream = _tracking_run_stream

        with patch("narrare_core.chat.chat_agent.ChatAgent", return_value=mock_agent):
            events = []
            async for event in await service.ask(request, user_id):
                events.append(event)

        # Stream events are correct
        assert events[0]["type"] == "meta"
        assert events[-1]["type"] == "done"

        # Run limits were passed to agent.run_stream
        assert "usage_limits" in run_stream_kwargs
        assert "model_settings" in run_stream_kwargs

    async def test_ask_with_pipeline_creates_conversation_in_store(
        self,
        mock_composer: AsyncMock,
        mock_registry: AsyncMock,
        in_memory_store: InMemoryConversationStore,
        mock_config: MagicMock,
    ) -> None:
        """With pipeline wired, conversation persistence still works."""
        from uuid import UUID, uuid4

        from tests.unit.api.chat.conftest import _async_gen, _make_request

        from narrare.chat.chat_service import ChatService
        from narrare_core.agents.base import StreamEvent
        from narrare_core.ai_invocation.pipeline import InvocationPipeline
        from narrare_core.chat.chat_agent import ChatAgent

        request = _make_request(message="Save this message")
        user_id = uuid4()

        pipeline = InvocationPipeline()

        from tests.unit.api.chat.conftest import _static_resolution

        service = ChatService(
            prompt_composer=mock_composer,
            model_registry=mock_registry,
            conversation_store=cast("SQLAlchemyConversationStore", in_memory_store),
            model_resolution=_static_resolution(mock_config),
            invocation_pipeline=pipeline,
        )

        mock_agent = MagicMock(name="mock_agent", spec=ChatAgent)
        mock_agent.run_stream = lambda *a, **kw: _async_gen(
            StreamEvent(type="token", text="Saved response"),
            StreamEvent(type="done", text="Saved response", usage={}, new_messages=[]),
        )

        conv_id_from_meta: str | None = None
        with patch("narrare_core.chat.chat_agent.ChatAgent", return_value=mock_agent):
            gen = await service.ask(request, user_id)
            async for event in gen:
                if event.get("type") == "meta":
                    conv_id_from_meta = str(event.get("conversation_id", ""))

        assert conv_id_from_meta is not None
        history = await in_memory_store.get_history(UUID(conv_id_from_meta), user_id)
        assert len(history) >= 2
        assert history[0].role == "user"
        assert history[0].content == "Save this message"
        assert history[-1].role == "assistant"


# ---------------------------------------------------------------------------
# Tests for backward compatibility (no pipeline, no resolver)
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    """Without pipeline + resolver, ChatService behaves as before."""

    async def test_ask_without_pipeline_streams_correctly(
        self,
        service: ChatService,
    ) -> None:
        """``ask()`` works with ``invocation_pipeline=None`` (default)."""
        from uuid import uuid4

        from tests.unit.api.chat.conftest import _async_gen, _make_request

        from narrare_core.agents.base import StreamEvent
        from narrare_core.chat.chat_agent import ChatAgent

        request = _make_request(message="No pipeline test")
        user_id = uuid4()

        mock_agent = MagicMock(name="mock_agent", spec=ChatAgent)
        mock_agent.run_stream = lambda *a, **kw: _async_gen(
            StreamEvent(type="token", text="Works!"),
            StreamEvent(type="done", text="Works!", usage={}, new_messages=[]),
        )

        with patch("narrare_core.chat.chat_agent.ChatAgent", return_value=mock_agent):
            events = []
            async for event in await service.ask(request, user_id):
                events.append(event)

        assert events[0]["type"] == "meta"
        assert events[-1]["type"] == "done"
        assert any(e["type"] == "token" for e in events)

    async def test_ask_without_pipeline_creates_conversation(
        self,
        service: ChatService,
        in_memory_store: InMemoryConversationStore,
    ) -> None:
        """Conversation persistence works without pipeline."""
        from uuid import UUID, uuid4

        from tests.unit.api.chat.conftest import _async_gen, _make_request

        from narrare_core.agents.base import StreamEvent
        from narrare_core.chat.chat_agent import ChatAgent

        request = _make_request(message="Persist me")
        user_id = uuid4()

        mock_agent = MagicMock(name="mock_agent", spec=ChatAgent)
        mock_agent.run_stream = lambda *a, **kw: _async_gen(
            StreamEvent(type="token", text="Data"),
            StreamEvent(type="done", text="Data", usage={}, new_messages=[]),
        )

        conv_id_from_meta: str | None = None
        with patch("narrare_core.chat.chat_agent.ChatAgent", return_value=mock_agent):
            gen = await service.ask(request, user_id)
            async for event in gen:
                if event.get("type") == "meta":
                    conv_id_from_meta = str(event.get("conversation_id", ""))

        assert conv_id_from_meta is not None
        history = await in_memory_store.get_history(UUID(conv_id_from_meta), user_id)
        assert len(history) >= 2
