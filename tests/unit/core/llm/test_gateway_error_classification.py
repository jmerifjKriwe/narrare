"""Tests for llm/gateway._classify_error — error classification coverage.

Covers L1 (typed pydantic-ai exceptions), L2 (stdlib exceptions),
L3 (string heuristic), and edge cases.
"""

from __future__ import annotations

import pytest
from pydantic_ai.exceptions import (  # narrare: allow reason="gateway error classification tests"
    ModelHTTPError,
    UnexpectedModelBehavior,
)

from narrare_core.llm.gateway import LLMGateway
from narrare_core.shared.errors import (
    LLMAuthError,
    LLMContextTooLargeError,
    LLMGatewayError,
    LLMInvalidRequestError,
    LLMRateLimitError,
    LLMServiceUnavailableError,
    LLMTimeoutError,
)


@pytest.fixture
def gateway() -> LLMGateway:
    return LLMGateway(default_provider="anthropic")


class TestLLMGatewayClassifyErrorAdditional:
    """Cover all branches of _classify_error."""

    def test_classifies_context_too_large(self, gateway: LLMGateway) -> None:
        err = Exception("context length exceeded maximum token limit")
        result = gateway._classify_error(err)
        assert isinstance(result, LLMContextTooLargeError)

    def test_classifies_service_unavailable(self, gateway: LLMGateway) -> None:
        err = Exception("503 Service overloaded unavailable")
        result = gateway._classify_error(err)
        assert isinstance(result, LLMServiceUnavailableError)

    def test_classifies_bad_gateway(self, gateway: LLMGateway) -> None:
        err = Exception("502 Bad Gateway capacity issue")
        result = gateway._classify_error(err)
        assert isinstance(result, LLMServiceUnavailableError)

    def test_classifies_invalid_request(self, gateway: LLMGateway) -> None:
        err = Exception("400 Bad Request invalid parameter")
        result = gateway._classify_error(err)
        assert isinstance(result, LLMInvalidRequestError)

    def test_classifies_generic_error_as_fallback(self, gateway: LLMGateway) -> None:
        err = Exception("something completely unexpected")
        result = gateway._classify_error(err)
        assert isinstance(result, LLMGatewayError)
        assert "Unexpected" in str(result)


class TestLLMGatewayClassifyErrorLayered:
    """Verify the layered classification: L1 typed -> L2 stdlib -> L3 string heuristic."""

    # --- Layer 1: pydantic-ai typed exceptions ---

    def test_model_http_error_401_classifies_as_auth(self, gateway: LLMGateway) -> None:
        err = ModelHTTPError(status_code=401, model_name="claude-3")
        result = gateway._classify_error(err)
        assert isinstance(result, LLMAuthError)

    def test_model_http_error_429_classifies_as_rate_limit(self, gateway: LLMGateway) -> None:
        err = ModelHTTPError(status_code=429, model_name="claude-3")
        result = gateway._classify_error(err)
        assert isinstance(result, LLMRateLimitError)

    def test_model_http_error_400_classifies_as_invalid_request(self, gateway: LLMGateway) -> None:
        err = ModelHTTPError(status_code=400, model_name="claude-3")
        result = gateway._classify_error(err)
        assert isinstance(result, LLMInvalidRequestError)

    def test_model_http_error_503_classifies_as_service_unavailable(
        self, gateway: LLMGateway
    ) -> None:
        err = ModelHTTPError(status_code=503, model_name="claude-3")
        result = gateway._classify_error(err)
        assert isinstance(result, LLMServiceUnavailableError)

    def test_model_http_error_502_classifies_as_service_unavailable(
        self, gateway: LLMGateway
    ) -> None:
        err = ModelHTTPError(status_code=502, model_name="claude-3")
        result = gateway._classify_error(err)
        assert isinstance(result, LLMServiceUnavailableError)

    def test_model_http_error_500_classifies_as_generic(self, gateway: LLMGateway) -> None:
        err = ModelHTTPError(status_code=500, model_name="claude-3")
        result = gateway._classify_error(err)
        assert isinstance(result, LLMGatewayError)
        assert not isinstance(result, LLMAuthError)
        assert "LLM HTTP error 500" in str(result)

    def test_unexpected_model_behavior_classifies_as_generic(self, gateway: LLMGateway) -> None:
        err = UnexpectedModelBehavior("model returned empty")
        result = gateway._classify_error(err)
        assert isinstance(result, LLMGatewayError)
        assert "Unexpected model behavior" in str(result)

    # --- Layer 2: Standard library exceptions ---

    def test_asyncio_timeout_classifies_as_timeout(self, gateway: LLMGateway) -> None:
        result = gateway._classify_error(TimeoutError())
        assert isinstance(result, LLMTimeoutError)

    def test_builtin_timeout_classifies_as_timeout(self, gateway: LLMGateway) -> None:
        result = gateway._classify_error(TimeoutError("connection expired"))
        assert isinstance(result, LLMTimeoutError)

    # --- Layer 3: String-based fallback (verified via existing tests) ---

    def test_plain_exception_with_auth_keywords_uses_fallback(self, gateway: LLMGateway) -> None:
        """String fallback still works for non-typed exceptions."""
        err = Exception("invalid api key provided")
        result = gateway._classify_error(err)
        assert isinstance(result, LLMAuthError)

    def test_plain_exception_unknown_uses_generic_fallback(self, gateway: LLMGateway) -> None:
        err = Exception("something completely unforeseen")
        result = gateway._classify_error(err)
        assert isinstance(result, LLMGatewayError)
        assert "Unexpected" in str(result)


class TestLLMGatewayClassifyErrorEdgeCases:
    """Cover additional edge cases for _classify_error()."""

    # --- pydantic-ai ModelHTTPError with additional status codes ---

    def test_model_http_error_403_classifies_as_generic(self, gateway: LLMGateway) -> None:
        """403 Forbidden is not a special case -- falls to generic LLMGatewayError."""
        err = ModelHTTPError(status_code=403, model_name="claude-3")
        result = gateway._classify_error(err)
        assert isinstance(result, LLMGatewayError)
        assert not isinstance(result, LLMAuthError)
        assert "LLM HTTP error 403" in str(result)

    # --- Standard library ConnectionError ---

    def test_connection_error_classifies_as_generic(self, gateway: LLMGateway) -> None:
        """ConnectionError has no special handler -- falls through to string heuristic."""
        err = ConnectionError("connection refused")
        result = gateway._classify_error(err)
        # "connection" doesn't match any keyword heuristic, so it's generic
        assert isinstance(result, LLMGatewayError)

    def test_connection_reset_error_classifies_as_generic(self, gateway: LLMGateway) -> None:
        """ConnectionResetError is a subclass of ConnectionError."""
        err = ConnectionResetError("connection reset by peer")
        result = gateway._classify_error(err)
        assert isinstance(result, LLMGatewayError)

    # --- asyncio.TimeoutError ---

    def test_asyncio_timeout_error_classifies_as_timeout(self, gateway: LLMGateway) -> None:
        """asyncio.TimeoutError should classify as LLMTimeoutError."""
        err = TimeoutError()
        result = gateway._classify_error(err)
        assert isinstance(result, LLMTimeoutError)

    # --- Exception with empty message ---

    def test_exception_with_empty_message_classifies_as_generic(self, gateway: LLMGateway) -> None:
        """An exception with no message should fall to the generic handler."""
        err = Exception()
        result = gateway._classify_error(err)
        assert isinstance(result, LLMGatewayError)
        assert "Unexpected" in str(result)

    # --- RuntimeError ---

    def test_runtime_error_classifies_as_generic(self, gateway: LLMGateway) -> None:
        """RuntimeError has no special handler -- falls to generic."""
        err = RuntimeError("CUDA out of memory")
        result = gateway._classify_error(err)
        assert isinstance(result, LLMGatewayError)

    # --- ValueError ---

    def test_value_error_classifies_as_generic(self, gateway: LLMGateway) -> None:
        """ValueError has no special handler -- falls to string heuristic."""
        err = ValueError("invalid parameter")
        result = gateway._classify_error(err)
        # "invalid" keyword in string -> LLMInvalidRequestError
        assert isinstance(result, LLMInvalidRequestError)

    # --- String fallback: rate limit keywords ---

    def test_exception_with_quota_keyword_classifies_as_rate_limit(
        self, gateway: LLMGateway
    ) -> None:
        err = Exception("You have exceeded your quota")
        result = gateway._classify_error(err)
        assert isinstance(result, LLMRateLimitError)

    def test_exception_with_too_many_requests_keyword_classifies_as_rate_limit(
        self, gateway: LLMGateway
    ) -> None:
        err = Exception("Too many requests in the current window")
        result = gateway._classify_error(err)
        assert isinstance(result, LLMRateLimitError)

    # --- String fallback: context/length keywords ---

    def test_exception_with_token_keyword_classifies_as_context_too_large(
        self, gateway: LLMGateway
    ) -> None:
        err = Exception("token count exceeds maximum")
        result = gateway._classify_error(err)
        assert isinstance(result, LLMContextTooLargeError)

    def test_exception_with_too_long_keyword_classifies_as_context_too_large(
        self, gateway: LLMGateway
    ) -> None:
        err = Exception("prompt is too long for this model")
        result = gateway._classify_error(err)
        assert isinstance(result, LLMContextTooLargeError)

    # --- String fallback: timeout keywords ---

    def test_exception_with_timed_out_keyword_classifies_as_timeout(
        self, gateway: LLMGateway
    ) -> None:
        err = Exception("request timed out after 30 seconds")
        result = gateway._classify_error(err)
        assert isinstance(result, LLMTimeoutError)

    def test_exception_with_deadline_keyword_classifies_as_timeout(
        self, gateway: LLMGateway
    ) -> None:
        err = Exception("deadline exceeded before response")
        result = gateway._classify_error(err)
        assert isinstance(result, LLMTimeoutError)

    # --- String fallback: capacity/unavailable keywords ---

    def test_exception_with_overloaded_keyword_classifies_as_service_unavailable(
        self, gateway: LLMGateway
    ) -> None:
        err = Exception("The engine is currently overloaded")
        result = gateway._classify_error(err)
        assert isinstance(result, LLMServiceUnavailableError)

    # --- Classification preserves error message ---

    def test_classified_error_preserves_original_message(self, gateway: LLMGateway) -> None:
        err = ModelHTTPError(status_code=429, model_name="gpt-4")
        result = gateway._classify_error(err)
        # The domain error should contain info from the original
        assert isinstance(result, LLMRateLimitError)
        assert str(result)  # Should have a non-empty message
