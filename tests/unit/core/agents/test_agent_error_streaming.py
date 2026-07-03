"""Tests for NarrareAgent error classification — run_stream() path (AUFG-03-06).

Verifies that ``run_stream()`` translates raw pydantic-ai exceptions into
typed NarrareAgent errors.  The streaming path must produce the same error
types as ``run()``.  Uses FunctionModel to inject failures
deterministically — no real LLM calls.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import pytest
from pydantic_ai.exceptions import (
    ModelHTTPError,
    UnexpectedModelBehavior,
)

if TYPE_CHECKING:
    from narrare_core.agents.base import NarrareAgent, StreamEvent

from narrare_core.agents.errors import (
    AgentCancelledError,
    AgentError,
    AgentTimeoutError,
    ModelExecutionError,
    ModelRetryExhaustedError,
)


class TestRunStreamErrorClassification:
    """Verify classify_error mapping for run_stream() path.

    The streaming path must produce the same error types as run().
    """

    async def _collect_stream(
        self,
        agent: NarrareAgent[Any, Any],
    ) -> list[StreamEvent]:
        """Collect all StreamEvents from an agent run_stream call."""
        events: list[StreamEvent] = []
        async for event in agent.run_stream("test", deps=None):
            events.append(event)
        return events

    async def test_unexpected_model_behavior_with_retry_keyword_stream(
        self,
        make_agent,
        make_error_model,
    ) -> None:
        """UnexpectedModelBehavior with 'retry' → ModelRetryExhaustedError."""
        model = make_error_model(
            UnexpectedModelBehavior("Retry limit exceeded: too many retries"),
            stream=True,
        )
        agent = make_agent(model)

        with pytest.raises(ModelRetryExhaustedError, match="retries exhausted") as exc_info:
            await self._collect_stream(agent)

        assert "retries exhausted" in str(exc_info.value).lower()

    async def test_model_http_error_stream(
        self,
        make_agent,
        make_error_model,
    ) -> None:
        """ModelHTTPError → ModelExecutionError in streaming."""
        model = make_error_model(
            ModelHTTPError(status_code=503, model_name="test-model"),
            stream=True,
        )
        agent = make_agent(model)

        with pytest.raises(ModelExecutionError, match="HTTP 503") as exc_info:
            await self._collect_stream(agent)

        assert "HTTP 503" in str(exc_info.value)
        assert exc_info.value.provider_code == "HTTP_503"

    async def test_cancelled_error_stream(
        self,
        make_agent,
        make_error_model,
    ) -> None:
        """asyncio.CancelledError → AgentCancelledError in streaming."""
        model = make_error_model(asyncio.CancelledError(), stream=True)
        agent = make_agent(model)

        with pytest.raises(AgentCancelledError, match="cancelled") as exc_info:
            await self._collect_stream(agent)

        assert exc_info.value.error_type == "agent_cancelled"

    async def test_timeout_error_stream(
        self,
        make_agent,
        make_error_model,
    ) -> None:
        """asyncio.TimeoutError → AgentTimeoutError in streaming."""
        model = make_error_model(TimeoutError(), stream=True)
        agent = make_agent(model)

        with pytest.raises(AgentTimeoutError, match="timed out") as exc_info:
            await self._collect_stream(agent)

        assert exc_info.value.error_type == "agent_timeout"

    async def test_unknown_error_stream(
        self,
        make_agent,
        make_error_model,
    ) -> None:
        """Unknown exception → AgentError in streaming."""
        model = make_error_model(RuntimeError("Mystery error"), stream=True)
        agent = make_agent(model)

        with pytest.raises(AgentError, match="Mystery error") as exc_info:
            await self._collect_stream(agent)

        assert exc_info.value.error_type == "unknown"

    async def test_error_has_agent_name_stream(
        self,
        make_agent,
        make_error_model,
    ) -> None:
        """Stream errors also include the agent class name."""
        model = make_error_model(
            UnexpectedModelBehavior("test"),
            stream=True,
        )
        agent = make_agent(model)

        with pytest.raises(ModelExecutionError, match="Unexpected model behavior") as exc_info:
            await self._collect_stream(agent)

        assert "_SimpleAgent" in exc_info.value.agent_name
