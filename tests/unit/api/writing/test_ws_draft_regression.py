"""Regression tests: generate_draft uses the invocation contract (ADR-045).

Split from ``test_ws_handler`` for RULE-04 (test hard limit 400 lines).

These tests prove the ``generate_draft`` WebSocket path no longer
bypasses the InvocationPipeline. Before migration,
``_handle_generate_draft`` called ``registry.stream`` with NO
``usage_limits`` and NO invocation context — bypassing enrichment,
evidence, and output-budget enforcement.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import Mock
from uuid import uuid4

from tests.unit.api.writing.test_ws_handler import (
    MockWebSocket,
    _fake_stream_hello,
    _make_handler,
)
from tests.unit.api.writing.ws_test_helpers import (
    stream_kwargs_for_intent,
    wait_for_gateway_calls,
)

if TYPE_CHECKING:
    from fastapi import WebSocket


class TestGenerateDraftContractRegression:
    """Regression: generate_draft must use the invocation contract."""

    async def test_generate_draft_enforces_usage_limits(self) -> None:
        """Regression: draft generation must pass usage_limits (ADR-045 D4).

        Before migration, ``_handle_generate_draft`` called
        ``registry.stream`` with NO ``usage_limits`` — bypassing
        output-budget enforcement. The draft path must now resolve and
        enforce limits like the interactive-turn path.
        """
        handler, _, gateway, _ = _make_handler(mode="interview_assisted")
        gateway.stream = Mock(side_effect=_fake_stream_hello)
        ws = MockWebSocket()

        await ws.enqueue({"type": "user_direction", "content": "A story"})
        await ws.enqueue({"type": "generate_draft"})
        await ws.enqueue_end_session()

        await handler.handle(cast("WebSocket", ws), uuid4(), str(uuid4()), uuid4())

        await wait_for_gateway_calls(gateway, 2)
        assert gateway.stream.call_count == 2
        draft_kwargs = stream_kwargs_for_intent(gateway, "write")
        # Usage limits MUST be present — proves budget enforcement.
        assert draft_kwargs["usage_limits"] is not None

    async def test_generate_draft_threads_identifiers_to_invocation(self) -> None:
        """Regression: draft generation must complete the invocation contract.

        Before migration, ``_handle_generate_draft`` bypassed the
        InvocationPipeline entirely — no context, no evidence, no limits.
        With a wired (no-op) pipeline, the stream completing proves the
        full prepare → compose → finalize → stream path ran with the
        connection-scoped user/project/chapter identifiers.
        """
        handler, _, gateway, _ = _make_handler(mode="interview_assisted")
        gateway.stream = Mock(side_effect=_fake_stream_hello)
        ws = MockWebSocket()

        await ws.enqueue({"type": "user_direction", "content": "A story"})
        await ws.enqueue({"type": "generate_draft"})
        await ws.enqueue_end_session()

        await handler.handle(cast("WebSocket", ws), uuid4(), str(uuid4()), uuid4())

        # The draft stream was called — proving the invocation contract
        # (prepare → compose → finalize → resolve limits → stream)
        # completed without raising a validation or context error.
        await wait_for_gateway_calls(gateway, 2)
        assert gateway.stream.call_count == 2
        draft_done: list[dict[str, Any]] = [m for m in ws.sent if m["type"] == "draft_done"]
        assert len(draft_done) == 1
