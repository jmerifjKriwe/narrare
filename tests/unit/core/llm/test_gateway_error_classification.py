"""Tests for llm/gateway_errors.classify_error — error classification coverage.

Covers L1 (typed pydantic-ai exceptions), L2 (stdlib exceptions),
L3 (string heuristic), and edge cases.

The classify_error function was previously tested via LLMGateway._classify_error
but now lives independently in gateway_errors.py.
"""

from __future__ import annotations

from pydantic_ai.exceptions import (  # narrare: allow reason="gateway error classification tests"
    ModelHTTPError,
    UnexpectedModelBehavior,
)

from narrare_core.llm.gateway_errors import classify_error
from narrare_core.shared.errors import (
    LLMAuthError,
    LLMContextTooLargeError,
    LLMGatewayError,
    LLMInvalidRequestError,
    LLMRateLimitError,
    LLMServiceUnavailableError,
    LLMTimeoutError,
)


class TestClassifyErrorAdditional:
    """Cover all branches of classify_error."""

    def test_classifies_rate_limit(self) -> None:
        err = Exception("429 Too Many Requests rate limit exceeded")
        result = classify_error(err)
        assert isinstance(result, LLMRateLimitError)

    def test_classifies_auth_error(self) -> None:
        err = Exception("401 Unauthorized invalid api key")
        result = classify_error(err)
        assert isinstance(result, LLMAuthError)

    def test_classifies_timeout(self) -> None:
        err = Exception("Request timed out after 30s")
        result = classify_error(err)
        assert isinstance(result, LLMTimeoutError)

    def test_classifies_context_too_large(self) -> None:
        err = Exception("context length exceeded maximum token limit")
        result = classify_error(err)
        assert isinstance(result, LLMContextTooLargeError)

    def test_classifies_service_unavailable(self) -> None:
        err = Exception("503 Service overloaded unavailable")
        result = classify_error(err)
        assert isinstance(result, LLMServiceUnavailableError)

    def test_classifies_bad_gateway(self) -> None:
        err = Exception("502 Bad Gateway capacity issue")
        result = classify_error(err)
        assert isinstance(result, LLMServiceUnavailableError)

    def test_classifies_invalid_request(self) -> None:
        err = Exception("400 Bad Request invalid parameter")
        result = classify_error(err)
        assert isinstance(result, LLMInvalidRequestError)

    def test_classifies_generic_error_as_fallback(self) -> None:
        err = Exception("something completely unexpected")
        result = classify_error(err)
        assert isinstance(result, LLMGatewayError)
        assert "Unexpected" in str(result)


class TestClassifyErrorLayered:
    """Verify the layered classification: L1 typed -> L2 stdlib -> L3 string heuristic."""

    # --- Layer 1: pydantic-ai typed exceptions ---

    def test_model_http_error_401_classifies_as_auth(self) -> None:
        err = ModelHTTPError(status_code=401, model_name="claude-3")
        result = classify_error(err)
        assert isinstance(result, LLMAuthError)

    def test_model_http_error_429_classifies_as_rate_limit(self) -> None:
        err = ModelHTTPError(status_code=429, model_name="claude-3")
        result = classify_error(err)
        assert isinstance(result, LLMRateLimitError)

    def test_model_http_error_400_classifies_as_invalid_request(self) -> None:
        err = ModelHTTPError(status_code=400, model_name="claude-3")
        result = classify_error(err)
        assert isinstance(result, LLMInvalidRequestError)

    def test_model_http_error_503_classifies_as_service_unavailable(self) -> None:
        err = ModelHTTPError(status_code=503, model_name="claude-3")
        result = classify_error(err)
        assert isinstance(result, LLMServiceUnavailableError)

    def test_model_http_error_502_classifies_as_service_unavailable(self) -> None:
        err = ModelHTTPError(status_code=502, model_name="claude-3")
        result = classify_error(err)
        assert isinstance(result, LLMServiceUnavailableError)

    def test_model_http_error_500_classifies_as_generic(self) -> None:
        err = ModelHTTPError(status_code=500, model_name="claude-3")
        result = classify_error(err)
        assert isinstance(result, LLMGatewayError)
        assert not isinstance(result, LLMAuthError)
        assert "LLM HTTP error 500" in str(result)

    def test_unexpected_model_behavior_classifies_as_generic(self) -> None:
        err = UnexpectedModelBehavior("model returned empty")
        result = classify_error(err)
        assert isinstance(result, LLMGatewayError)
        assert "Unexpected model behavior" in str(result)

    # --- Layer 2: Standard library exceptions ---

    def test_asyncio_timeout_classifies_as_timeout(self) -> None:
        """asyncio.TimeoutError is classified as LLMTimeoutError (L2).

        In Python 3.11+, asyncio.TimeoutError IS TimeoutError.
        Testing explicitly for documentation clarity.
        """

        result = classify_error(TimeoutError())
        assert isinstance(result, LLMTimeoutError)

    def test_builtin_timeout_classifies_as_timeout(self) -> None:
        result = classify_error(TimeoutError("connection expired"))
        assert isinstance(result, LLMTimeoutError)

    # --- Layer 3: String-based fallback ---

    def test_plain_exception_with_auth_keywords_uses_fallback(self) -> None:
        err = Exception("invalid api key provided")
        result = classify_error(err)
        assert isinstance(result, LLMAuthError)

    def test_plain_exception_unknown_uses_generic_fallback(self) -> None:
        err = Exception("something completely unforeseen")
        result = classify_error(err)
        assert isinstance(result, LLMGatewayError)
        assert "Unexpected" in str(result)


class TestClassifyErrorEdgeCases:
    """Cover additional edge cases for classify_error()."""

    def test_model_http_error_403_classifies_as_generic(self) -> None:
        err = ModelHTTPError(status_code=403, model_name="claude-3")
        result = classify_error(err)
        assert isinstance(result, LLMGatewayError)
        assert not isinstance(result, LLMAuthError)
        assert "LLM HTTP error 403" in str(result)

    def test_connection_error_classifies_as_generic(self) -> None:
        err = ConnectionError("connection refused")
        result = classify_error(err)
        assert isinstance(result, LLMGatewayError)

    def test_connection_reset_error_classifies_as_generic(self) -> None:
        err = ConnectionResetError("connection reset by peer")
        result = classify_error(err)
        assert isinstance(result, LLMGatewayError)

    def test_asyncio_timeout_error_classifies_as_timeout(self) -> None:
        err = TimeoutError()
        result = classify_error(err)
        assert isinstance(result, LLMTimeoutError)

    def test_exception_with_empty_message_classifies_as_generic(self) -> None:
        err = Exception()
        result = classify_error(err)
        assert isinstance(result, LLMGatewayError)
        assert "Unexpected" in str(result)

    def test_runtime_error_classifies_as_generic(self) -> None:
        err = RuntimeError("CUDA out of memory")
        result = classify_error(err)
        assert isinstance(result, LLMGatewayError)

    def test_value_error_classifies_as_generic(self) -> None:
        err = ValueError("invalid parameter")
        result = classify_error(err)
        assert isinstance(result, LLMInvalidRequestError)

    def test_exception_with_quota_keyword_classifies_as_rate_limit(self) -> None:
        err = Exception("You have exceeded your quota")
        result = classify_error(err)
        assert isinstance(result, LLMRateLimitError)

    def test_exception_with_too_many_requests_keyword_classifies_as_rate_limit(self) -> None:
        err = Exception("Too many requests in the current window")
        result = classify_error(err)
        assert isinstance(result, LLMRateLimitError)

    def test_exception_with_token_keyword_classifies_as_context_too_large(self) -> None:
        err = Exception("token count exceeds maximum")
        result = classify_error(err)
        assert isinstance(result, LLMContextTooLargeError)

    def test_exception_with_too_long_keyword_classifies_as_context_too_large(self) -> None:
        err = Exception("prompt is too long for this model")
        result = classify_error(err)
        assert isinstance(result, LLMContextTooLargeError)

    def test_exception_with_timed_out_keyword_classifies_as_timeout(self) -> None:
        err = Exception("request timed out after 30 seconds")
        result = classify_error(err)
        assert isinstance(result, LLMTimeoutError)

    def test_exception_with_deadline_keyword_classifies_as_timeout(self) -> None:
        err = Exception("deadline exceeded before response")
        result = classify_error(err)
        assert isinstance(result, LLMTimeoutError)

    def test_exception_with_overloaded_keyword_classifies_as_service_unavailable(self) -> None:
        err = Exception("The engine is currently overloaded")
        result = classify_error(err)
        assert isinstance(result, LLMServiceUnavailableError)

    def test_classified_error_preserves_original_message(self) -> None:
        err = ModelHTTPError(status_code=429, model_name="gpt-4")
        result = classify_error(err)
        assert isinstance(result, LLMRateLimitError)
        assert str(result)  # Should have a non-empty message
