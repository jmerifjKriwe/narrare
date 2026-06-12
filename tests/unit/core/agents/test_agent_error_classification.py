"""Tests for NarrareAgent error classification — run() and direct classify_error (AUFG-03-06).

Verifies that ``run()`` translates raw pydantic-ai exceptions into typed
NarrareAgent errors, and that ``classify_error()`` produces correct mappings
when called directly.  Uses FunctionModel to inject failures
deterministically — no real LLM calls.
"""

from __future__ import annotations

import asyncio

import pytest
from pydantic_ai.exceptions import (
    ModelHTTPError,
    UnexpectedModelBehavior,
    UsageLimitExceeded,
    UserError,
)

from narrare_core.agents.errors import (
    AgentCancelledError,
    AgentError,
    AgentTimeoutError,
    ModelExecutionError,
    ModelRetryExhaustedError,
)

# ---------------------------------------------------------------------------
# Error classification tests — run()
# ---------------------------------------------------------------------------


class TestRunErrorClassification:
    """Verify classify_error mapping for run() path."""

    async def test_unexpected_model_behavior_with_retry_keyword(
        self,
        make_agent,
        make_error_model,
    ) -> None:
        """UnexpectedModelBehavior with 'retry' → ModelRetryExhaustedError."""
        model = make_error_model(
            UnexpectedModelBehavior("Retry limit exceeded: too many retries"),
        )
        agent = make_agent(model)

        with pytest.raises(ModelRetryExhaustedError) as exc_info:
            await agent.run("test", deps=None)

        assert "retries exhausted" in str(exc_info.value).lower()
        assert exc_info.value.error_type == "model_retry_exhausted"
        assert exc_info.value.original is not None

    async def test_unexpected_model_behavior_generic(
        self,
        make_agent,
        make_error_model,
    ) -> None:
        """UnexpectedModelBehavior without retry keywords → ModelExecutionError."""
        model = make_error_model(
            UnexpectedModelBehavior("Content filter triggered"),
        )
        agent = make_agent(model)

        with pytest.raises(ModelExecutionError) as exc_info:
            await agent.run("test", deps=None)

        assert "unexpected model behavior" in str(exc_info.value).lower()
        assert exc_info.value.error_type == "model_execution"

    async def test_model_http_error(
        self,
        make_agent,
        make_error_model,
    ) -> None:
        """ModelHTTPError → ModelExecutionError with provider_code."""
        model = make_error_model(
            ModelHTTPError(status_code=429, model_name="test-model"),
        )
        agent = make_agent(model)

        with pytest.raises(ModelExecutionError) as exc_info:
            await agent.run("test", deps=None)

        assert "HTTP 429" in str(exc_info.value)
        assert exc_info.value.provider_code == "HTTP_429"

    async def test_model_http_error_5xx(
        self,
        make_agent,
        make_error_model,
    ) -> None:
        """ModelHTTPError 500 → ModelExecutionError with provider_code."""
        model = make_error_model(
            ModelHTTPError(status_code=500, model_name="test-model"),
        )
        agent = make_agent(model)

        with pytest.raises(ModelExecutionError) as exc_info:
            await agent.run("test", deps=None)

        assert "HTTP 500" in str(exc_info.value)
        assert exc_info.value.provider_code == "HTTP_500"

    async def test_usage_limit_exceeded(
        self,
        make_agent,
        make_error_model,
    ) -> None:
        """UsageLimitExceeded → ModelExecutionError with provider_code."""
        model = make_error_model(
            UsageLimitExceeded("Token budget exceeded"),
        )
        agent = make_agent(model)

        with pytest.raises(ModelExecutionError) as exc_info:
            await agent.run("test", deps=None)

        assert "usage limit" in str(exc_info.value).lower()
        assert exc_info.value.provider_code == "USAGE_LIMIT_EXCEEDED"

    async def test_user_error(
        self,
        make_agent,
        make_error_model,
    ) -> None:
        """UserError → AgentError with error_type='user_error'."""
        model = make_error_model(UserError("Invalid output type"))
        agent = make_agent(model)

        with pytest.raises(AgentError) as exc_info:
            await agent.run("test", deps=None)

        assert exc_info.value.error_type == "user_error"

    async def test_cancelled_error(
        self,
        make_agent,
        make_error_model,
    ) -> None:
        """asyncio.CancelledError → AgentCancelledError."""
        model = make_error_model(asyncio.CancelledError())
        agent = make_agent(model)

        with pytest.raises(AgentCancelledError) as exc_info:
            await agent.run("test", deps=None)

        assert exc_info.value.error_type == "agent_cancelled"

    async def test_timeout_error(
        self,
        make_agent,
        make_error_model,
    ) -> None:
        """asyncio.TimeoutError → AgentTimeoutError."""
        model = make_error_model(TimeoutError())
        agent = make_agent(model)

        with pytest.raises(AgentTimeoutError) as exc_info:
            await agent.run("test", deps=None)

        assert exc_info.value.error_type == "agent_timeout"

    async def test_unknown_error(
        self,
        make_agent,
        make_error_model,
    ) -> None:
        """Unknown exception → AgentError with error_type='unknown'."""
        model = make_error_model(ValueError("Something unexpected"))
        agent = make_agent(model)

        with pytest.raises(AgentError) as exc_info:
            await agent.run("test", deps=None)

        assert exc_info.value.error_type == "unknown"
        assert exc_info.value.original is not None

    async def test_error_has_agent_name(
        self,
        make_agent,
        make_error_model,
    ) -> None:
        """All classified errors include the agent class name."""
        model = make_error_model(UnexpectedModelBehavior("test"))
        agent = make_agent(model)

        with pytest.raises(ModelExecutionError) as exc_info:
            await agent.run("test", deps=None)

        assert "_SimpleAgent" in exc_info.value.agent_name


# ---------------------------------------------------------------------------
# classify_error unit tests (direct call)
# ---------------------------------------------------------------------------


class TestClassifyErrorDirect:
    """Test classify_error function directly without agent overhead."""

    def test_classify_cancelled(self) -> None:
        from narrare_core.agents.error_translator import classify_error

        exc = asyncio.CancelledError()
        result = classify_error(exc, agent_name="TestAgent")
        assert isinstance(result, AgentCancelledError)
        assert result.error_type == "agent_cancelled"

    def test_classify_timeout(self) -> None:
        from narrare_core.agents.error_translator import classify_error

        exc = TimeoutError()
        result = classify_error(exc, agent_name="TestAgent")
        assert isinstance(result, AgentTimeoutError)
        assert result.error_type == "agent_timeout"

    def test_classify_model_http_error(self) -> None:
        from narrare_core.agents.error_translator import classify_error

        exc = ModelHTTPError(status_code=401, model_name="test-model")
        result = classify_error(exc, agent_name="TestAgent")
        assert isinstance(result, ModelExecutionError)
        assert result.provider_code == "HTTP_401"

    def test_classify_unexpected_model_behavior_retry(self) -> None:
        from narrare_core.agents.error_translator import classify_error

        exc = UnexpectedModelBehavior("Too many retries exceeded")
        result = classify_error(exc, agent_name="TestAgent")
        assert isinstance(result, ModelRetryExhaustedError)

    def test_classify_unexpected_model_behavior_exceeded(self) -> None:
        from narrare_core.agents.error_translator import classify_error

        exc = UnexpectedModelBehavior("Retry limit exceeded for tool calls")
        result = classify_error(exc, agent_name="TestAgent")
        assert isinstance(result, ModelRetryExhaustedError)

    def test_classify_unexpected_model_behavior_generic(self) -> None:
        from narrare_core.agents.error_translator import classify_error

        exc = UnexpectedModelBehavior("Content filtering blocked response")
        result = classify_error(exc, agent_name="TestAgent")
        assert isinstance(result, ModelExecutionError)
        assert not isinstance(result, ModelRetryExhaustedError)

    def test_classify_usage_limit_exceeded(self) -> None:
        from narrare_core.agents.error_translator import classify_error

        exc = UsageLimitExceeded("Budget exceeded")
        result = classify_error(exc, agent_name="TestAgent")
        assert isinstance(result, ModelExecutionError)
        assert result.provider_code == "USAGE_LIMIT_EXCEEDED"

    def test_classify_user_error(self) -> None:
        from narrare_core.agents.error_translator import classify_error

        exc = UserError("Bad configuration")
        result = classify_error(exc, agent_name="TestAgent")
        assert isinstance(result, AgentError)
        assert result.error_type == "user_error"

    def test_classify_unknown_error(self) -> None:
        from narrare_core.agents.error_translator import classify_error

        exc = RuntimeError("something went wrong")
        result = classify_error(exc, agent_name="TestAgent")
        assert isinstance(result, AgentError)
        assert result.error_type == "unknown"

    def test_no_prompt_text_in_log_attrs(self) -> None:
        """Privacy check: log_attrs must never contain prompt/response text."""
        from narrare_core.agents.error_translator import classify_error

        exc = UnexpectedModelBehavior("Sensitive prompt content leaked")
        result = classify_error(exc, agent_name="TestAgent")
        for value in result.log_attrs.values():
            assert "Sensitive" not in value
            assert "leaked" not in value
