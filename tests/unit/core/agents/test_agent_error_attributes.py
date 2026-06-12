"""Tests for NarrareAgent error class attributes (AUFG-03-06).

Verifies privacy-safe attributes, repr formatting, and exception chaining
on the error classes defined in ``narrare_core.agents.errors``.
"""

from __future__ import annotations

from narrare_core.agents.errors import (
    AgentError,
    ModelExecutionError,
)


class TestErrorAttributes:
    """Verify privacy-safe attributes on error classes."""

    def test_agent_error_log_attrs_basic(self) -> None:
        error = AgentError("test", agent_name="MyAgent", error_type="test")
        attrs = error.log_attrs
        assert "error_type" in attrs
        assert "agent_name" in attrs
        assert attrs["error_type"] == "test"
        assert attrs["agent_name"] == "MyAgent"

    def test_model_execution_error_log_attrs_with_provider_code(self) -> None:
        error = ModelExecutionError(
            "test",
            agent_name="MyAgent",
            provider_code="HTTP_429",
        )
        attrs = error.log_attrs
        assert attrs["provider_code"] == "HTTP_429"

    def test_model_execution_error_log_attrs_without_provider_code(self) -> None:
        error = ModelExecutionError("test", agent_name="MyAgent")
        attrs = error.log_attrs
        assert "provider_code" not in attrs

    def test_error_repr(self) -> None:
        error = AgentError("test", agent_name="MyAgent", error_type="test")
        r = repr(error)
        assert "AgentError" in r
        assert "test" in r

    def test_original_exception_chaining(self) -> None:
        original = ValueError("root cause")
        error = AgentError("wrapped", agent_name="X", original=original)
        assert error.original is original
