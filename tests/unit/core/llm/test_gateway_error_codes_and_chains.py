"""Tests for gateway_errors.classify_error — error codes, chains, severity, and type validation.

Split from test_gateway_error_classification.py per RULE-04 (file size limits).
The original file covers L1/L2/L3 classification branches; this file covers:
- Error code attributes on classified errors
- Error chain / message preservation
- Error severity (retryable vs non-retryable subclass hierarchy)
- Additional L3 string heuristic keywords
- Type validation (None, string, int inputs)
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


class TestClassifyErrorErrorCodes:
    """Verify that classified errors carry the correct domain error codes."""

    def test_rate_limit_error_has_code(self) -> None:
        err = Exception("429 rate limit exceeded")
        result = classify_error(err)
        assert isinstance(result, LLMRateLimitError)
        assert result.code == "RATE_LIMIT"

    def test_auth_error_has_code(self) -> None:
        err = Exception("401 unauthorized api key")
        result = classify_error(err)
        assert isinstance(result, LLMAuthError)
        assert result.code == "AUTH_FAILED"

    def test_timeout_error_has_code(self) -> None:
        err = TimeoutError("connection timed out")
        result = classify_error(err)
        assert isinstance(result, LLMTimeoutError)
        assert result.code == "TIMEOUT"

    def test_service_unavailable_error_has_code(self) -> None:
        err = Exception("503 service unavailable")
        result = classify_error(err)
        assert isinstance(result, LLMServiceUnavailableError)
        assert result.code == "SERVICE_UNAVAILABLE"

    def test_context_too_large_error_has_code(self) -> None:
        err = Exception("context length exceeds maximum token limit")
        result = classify_error(err)
        assert isinstance(result, LLMContextTooLargeError)
        assert result.code == "CONTEXT_TOO_LARGE"

    def test_invalid_request_error_has_code(self) -> None:
        err = Exception("400 bad request invalid parameter")
        result = classify_error(err)
        assert isinstance(result, LLMInvalidRequestError)
        assert result.code == "INVALID_REQUEST"

    def test_generic_gateway_error_has_no_special_code(self) -> None:
        """LLMGatewayError base class has code=None by default."""
        err = Exception("something completely unforeseen")
        result = classify_error(err)
        assert isinstance(result, LLMGatewayError)
        assert result.code is None

    def test_model_http_error_generic_has_no_special_code(self) -> None:
        """ModelHTTPError with 500 → generic LLMGatewayError, code=None."""
        err = ModelHTTPError(status_code=500, model_name="gpt-4")
        result = classify_error(err)
        assert isinstance(result, LLMGatewayError)
        assert result.code is None


class TestClassifyErrorErrorChain:
    """Verify error chain preservation and message propagation."""

    def test_model_http_error_401_preserves_status_in_message(self) -> None:
        err = ModelHTTPError(status_code=401, model_name="claude-3")
        result = classify_error(err)
        assert isinstance(result, LLMAuthError)
        assert str(result)  # non-empty message

    def test_model_http_error_429_preserves_message(self) -> None:
        err = ModelHTTPError(status_code=429, model_name="gpt-4")
        result = classify_error(err)
        assert isinstance(result, LLMRateLimitError)
        assert str(result)

    def test_model_http_error_400_preserves_message(self) -> None:
        err = ModelHTTPError(status_code=400, model_name="gpt-4")
        result = classify_error(err)
        assert isinstance(result, LLMInvalidRequestError)
        assert str(result)

    def test_unexpected_model_behavior_preserves_message(self) -> None:
        err = UnexpectedModelBehavior("model returned empty response")
        result = classify_error(err)
        assert isinstance(result, LLMGatewayError)
        assert "Unexpected model behavior" in str(result)
        assert "model returned empty response" in str(result)

    def test_string_heuristic_preserves_original_message(self) -> None:
        """L3 fallback preserves the original exception message."""
        original_msg = "API key is invalid, authentication failed"
        err = Exception(original_msg)
        result = classify_error(err)
        assert isinstance(result, LLMAuthError)
        assert original_msg in str(result)

    def test_timeout_error_preserves_message(self) -> None:
        err = TimeoutError("connection timed out after 30s")
        result = classify_error(err)
        assert isinstance(result, LLMTimeoutError)
        assert "connection timed out after 30s" in str(result)


class TestClassifyErrorSeverity:
    """Verify error severity — retryable vs non-retryable subclass hierarchy."""

    def test_rate_limit_is_gateway_subclass(self) -> None:
        err = Exception("429 rate limit")
        result = classify_error(err)
        assert isinstance(result, LLMRateLimitError)
        assert isinstance(result, LLMGatewayError)

    def test_timeout_is_gateway_subclass(self) -> None:
        err = TimeoutError()
        result = classify_error(err)
        assert isinstance(result, LLMTimeoutError)
        assert isinstance(result, LLMGatewayError)

    def test_service_unavailable_is_gateway_subclass(self) -> None:
        err = Exception("503 service unavailable")
        result = classify_error(err)
        assert isinstance(result, LLMServiceUnavailableError)
        assert isinstance(result, LLMGatewayError)

    def test_auth_error_is_gateway_subclass(self) -> None:
        err = Exception("401 unauthorized")
        result = classify_error(err)
        assert isinstance(result, LLMAuthError)
        assert isinstance(result, LLMGatewayError)

    def test_context_too_large_is_gateway_subclass(self) -> None:
        err = Exception("context too large")
        result = classify_error(err)
        assert isinstance(result, LLMContextTooLargeError)
        assert isinstance(result, LLMGatewayError)

    def test_invalid_request_is_gateway_subclass(self) -> None:
        err = Exception("400 invalid request")
        result = classify_error(err)
        assert isinstance(result, LLMInvalidRequestError)
        assert isinstance(result, LLMGatewayError)


class TestClassifyErrorAdditionalL3:
    """Additional L3 string heuristic coverage for edge cases."""

    def test_authentication_keyword(self) -> None:
        err = Exception("authentication failed for user")
        result = classify_error(err)
        assert isinstance(result, LLMAuthError)

    def test_unauthorized_keyword(self) -> None:
        err = Exception("unauthorized access attempt")
        result = classify_error(err)
        assert isinstance(result, LLMAuthError)

    def test_length_keyword_classifies_as_context_too_large(self) -> None:
        err = Exception("maximum context length exceeded")
        result = classify_error(err)
        assert isinstance(result, LLMContextTooLargeError)

    def test_capacity_keyword_classifies_as_service_unavailable(self) -> None:
        err = Exception("capacity exceeded on server")
        result = classify_error(err)
        assert isinstance(result, LLMServiceUnavailableError)

    def test_invalid_keyword_classifies_as_invalid_request(self) -> None:
        err = Exception("invalid request format")
        result = classify_error(err)
        assert isinstance(result, LLMInvalidRequestError)

    def test_bad_request_keyword_classifies_as_invalid_request(self) -> None:
        err = Exception("bad request: missing parameter")
        result = classify_error(err)
        assert isinstance(result, LLMInvalidRequestError)


class TestClassifyErrorTypeValidation:
    """Test classify_error behavior with unusual input types.

    classify_error uses isinstance() checks and str() heuristic, so it
    does NOT enforce type constraints — it processes any object through
    the L3 string fallback. These tests document that behavior.
    """

    def test_classify_error_with_none_falls_through_to_generic(self) -> None:
        """None is not an Exception; str(None) = 'none' → generic fallback."""
        result = classify_error(None)  # type: ignore[arg-type]
        assert isinstance(result, LLMGatewayError)
        assert "Unexpected" in str(result)

    def test_classify_error_with_string_matches_keywords(self) -> None:
        """A bare string is not an Exception, but str() heuristic still matches."""
        result = classify_error("rate limit exceeded")  # type: ignore[arg-type]
        # str("rate limit exceeded").lower() contains "rate limit"
        assert isinstance(result, LLMRateLimitError)

    def test_classify_error_with_int_matches_status_code(self) -> None:
        """An int is not an Exception, but str(429) = '429' matches rate limit."""
        result = classify_error(429)  # type: ignore[arg-type]
        # str(429).lower() = "429" → matches "429" keyword
        assert isinstance(result, LLMRateLimitError)

    def test_classify_error_with_runtime_error(self) -> None:
        """RuntimeError falls through to L3 heuristic, then generic fallback."""
        err = RuntimeError("unexpected runtime failure")
        result = classify_error(err)
        assert isinstance(result, LLMGatewayError)

    def test_classify_error_with_type_error_exception(self) -> None:
        """Python TypeError falls through to L3, then generic fallback."""
        err = TypeError("wrong argument type")
        result = classify_error(err)
        assert isinstance(result, LLMGatewayError)

    def test_classify_error_with_key_error(self) -> None:
        """KeyError falls through to L3, then generic fallback."""
        err = KeyError("missing_key")
        result = classify_error(err)
        assert isinstance(result, LLMGatewayError)
