"""WS session bootstrap attribution — STATS-002 / ADR-093 D3 (Task 12).

The HTTP attribution middleware skips websocket scopes (ADR-084: user
identity arrives via ticket validation inside the endpoint), so
``WritingSessionHandler.handle`` binds ``usage_user_id`` /
``usage_novel_id`` once at session bootstrap. The handler task's context
persists for the connection and turn streams spawned via
``asyncio.ensure_future`` (``ws_direction_dispatch``) inherit it — asserted
here at the gateway seam, where ``emit_usage_event`` reads the vars.

Note on entity naming: the WS API names the novel scope ``project_id``
(glossary: "Novel — the top-level project container"); it is bound to
``usage_novel_id`` exactly like the HTTP middleware's ``/novels/{uuid}``
paths.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import Mock
from uuid import UUID, uuid4

from narrare_core.llm.usage_events import (
    set_usage_context,
    usage_novel_id,
    usage_user_id,
)
from tests.unit.api.writing.ws_test_helpers import (
    MockWebSocket,
    _fake_stream_hello,
    _make_handler,
    wait_for_gateway_calls,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastapi import WebSocket

    from narrare_core.llm.result import StreamChunk

UsageSample = tuple[UUID | None, UUID | None]


def _capture_context_at_gateway(gateway: Mock) -> list[UsageSample]:
    """Record usage ContextVars inside the (spawned) turn stream task.

    The gateway seam is where ``emit_usage_event`` reads the vars, so a
    sample taken there proves attribution reaches background dispatch —
    not just the synchronous bootstrap frame.
    """
    samples: list[UsageSample] = []

    def capturing_stream(*args: object, **kwargs: object) -> AsyncIterator[StreamChunk]:
        samples.append((usage_user_id.get(), usage_novel_id.get()))
        return _fake_stream_hello(*args, **kwargs)

    gateway.stream = Mock(side_effect=capturing_stream)
    return samples


class TestWsSessionUsageAttribution:
    """Bootstrap binds usage attribution once — spawned turns inherit it."""

    async def test_fresh_session_bootstrap_attributes_turn_stream(self) -> None:
        """Fresh session: user_direction turn sees the bootstrap attribution."""
        set_usage_context(user_id=None, novel_id=None)  # isolate shared task context
        handler, _, gateway, _ = _make_handler()
        samples = _capture_context_at_gateway(gateway)
        ws = MockWebSocket()
        chapter_id, user_id, project_id = uuid4(), uuid4(), uuid4()

        await ws.enqueue({"type": "user_direction", "content": "Write a scene"})
        await ws.enqueue_end_session()
        await handler.handle(cast("WebSocket", ws), chapter_id, str(user_id), project_id)
        await wait_for_gateway_calls(gateway, 1)

        assert samples == [(user_id, project_id)]
        set_usage_context(user_id=None, novel_id=None)

    async def test_reattach_bootstrap_attributes_turn_stream(self) -> None:
        """Reattach (ADR-052) path: recovered session attributes turns too."""
        set_usage_context(user_id=None, novel_id=None)
        handler, session_manager, gateway, _ = _make_handler()
        samples = _capture_context_at_gateway(gateway)
        ws = MockWebSocket()
        chapter_id, user_id, project_id = uuid4(), uuid4(), uuid4()
        session_id = await session_manager.create_session(
            chapter_id=chapter_id,
            project_id=project_id,
            user_id=user_id,
        )

        await ws.enqueue({"type": "user_direction", "content": "Continue the scene"})
        await ws.enqueue_end_session()
        await handler.handle(
            cast("WebSocket", ws),
            chapter_id,
            str(user_id),
            project_id,
            session_id=session_id,
        )
        await wait_for_gateway_calls(gateway, 1)

        assert ws.sent[0]["type"] == "session_recovered"
        assert samples == [(user_id, project_id)]
        set_usage_context(user_id=None, novel_id=None)

    async def test_recovery_failed_leaves_usage_context_unset(self) -> None:
        """Failed recovery closes before bootstrap — no attribution is bound."""
        set_usage_context(user_id=None, novel_id=None)
        handler, *_ = _make_handler()
        ws = MockWebSocket()

        await handler.handle(
            cast("WebSocket", ws),
            uuid4(),
            str(uuid4()),
            uuid4(),
            session_id=uuid4(),
        )

        assert ws.sent[0]["type"] == "recovery_failed"
        assert usage_user_id.get() is None
        assert usage_novel_id.get() is None
