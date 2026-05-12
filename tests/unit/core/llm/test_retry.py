"""Tests for llm/retry.py"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from narrare_core.llm.retry import (
    DEFAULT_RETRY,
    FAST_RETRY,
    NO_RETRY,
    PATIENT_RETRY,
    RetryConfig,
    is_retryable,
    with_retry,
)
from narrare_core.shared.errors import (
    LLMAuthError,
    LLMContextTooLargeError,
    LLMGatewayError,
    LLMInvalidRequestError,
    LLMRateLimitError,
    LLMServiceUnavailableError,
    LLMTimeoutError,
)


class TestRetryConfig:
    def test_delay_increases_with_attempts(self) -> None:
        config = RetryConfig(max_attempts=3, base_delay=1.0, jitter=False)
        assert config.delay_for_attempt(0) == 1.0
        assert config.delay_for_attempt(1) == 2.0
        assert config.delay_for_attempt(2) == 4.0

    def test_delay_capped_at_max(self) -> None:
        config = RetryConfig(max_attempts=5, base_delay=10.0, max_delay=15.0, jitter=False)
        assert config.delay_for_attempt(3) == 15.0

    def test_delay_with_jitter_is_within_range(self) -> None:
        config = RetryConfig(max_attempts=3, base_delay=1.0, jitter=True)
        for attempt in range(5):
            delay = config.delay_for_attempt(attempt)
            # With jitter: delay ∈ [base * 0.5, base * 1.0)
            expected_base = min(1.0 * (2**attempt), 60.0)
            assert expected_base * 0.5 <= delay < expected_base

    def test_no_retry_config_has_one_attempt(self) -> None:
        assert NO_RETRY.max_attempts == 1

    def test_default_retry_has_three_attempts(self) -> None:
        assert DEFAULT_RETRY.max_attempts == 3

    def test_fast_retry_has_two_attempts(self) -> None:
        assert FAST_RETRY.max_attempts == 2

    def test_patient_retry_has_five_attempts(self) -> None:
        assert PATIENT_RETRY.max_attempts == 5


class TestIsRetryable:
    def test_rate_limit_is_retryable(self) -> None:
        assert is_retryable(LLMRateLimitError()) is True

    def test_timeout_is_retryable(self) -> None:
        assert is_retryable(LLMTimeoutError()) is True

    def test_service_unavailable_is_retryable(self) -> None:
        assert is_retryable(LLMServiceUnavailableError()) is True

    def test_auth_error_is_not_retryable(self) -> None:
        assert is_retryable(LLMAuthError()) is False

    def test_context_too_large_is_not_retryable(self) -> None:
        assert is_retryable(LLMContextTooLargeError()) is False

    def test_invalid_request_is_not_retryable(self) -> None:
        assert is_retryable(LLMInvalidRequestError()) is False

    def test_base_gateway_error_is_not_retryable(self) -> None:
        assert is_retryable(LLMGatewayError("generic")) is False


class TestWithRetry:
    async def test_returns_on_first_success(self) -> None:
        calls = 0

        async def operation() -> str:
            nonlocal calls
            calls += 1
            return "success"

        result = await with_retry(operation, DEFAULT_RETRY)
        assert result == "success"
        assert calls == 1

    async def test_retries_on_rate_limit(self) -> None:
        calls = 0

        async def operation() -> str:
            nonlocal calls
            calls += 1
            if calls < 3:
                raise LLMRateLimitError()
            return "success"

        config = RetryConfig(max_attempts=3, base_delay=0.001, jitter=False)
        result = await with_retry(operation, config)
        assert result == "success"
        assert calls == 3

    async def test_raises_immediately_on_auth_error(self) -> None:
        async def operation() -> str:
            raise LLMAuthError()

        with pytest.raises(LLMAuthError):
            await with_retry(operation, DEFAULT_RETRY)

    async def test_raises_after_max_attempts(self) -> None:
        async def operation() -> str:
            raise LLMTimeoutError()

        config = RetryConfig(max_attempts=2, base_delay=0.001, jitter=False)
        with pytest.raises(LLMTimeoutError):
            await with_retry(operation, config)

    async def test_retries_on_timeout(self) -> None:
        """Timeout is retryable — verify retry happens and succeeds."""
        calls = 0

        async def operation() -> str:
            nonlocal calls
            calls += 1
            if calls < 2:
                raise LLMTimeoutError()
            return "recovered"

        config = RetryConfig(max_attempts=3, base_delay=0.001, jitter=False)
        result = await with_retry(operation, config)
        assert result == "recovered"
        assert calls == 2

    async def test_retries_on_service_unavailable(self) -> None:
        """Service unavailable is retryable — verify retry happens."""
        calls = 0

        async def operation() -> str:
            nonlocal calls
            calls += 1
            if calls < 2:
                raise LLMServiceUnavailableError()
            return "back_online"

        config = RetryConfig(max_attempts=3, base_delay=0.001, jitter=False)
        result = await with_retry(operation, config)
        assert result == "back_online"
        assert calls == 2

    async def test_raises_immediately_on_context_too_large(self) -> None:
        """Context too large is non-retryable — no retry."""
        calls = 0

        async def operation() -> str:
            nonlocal calls
            calls += 1
            raise LLMContextTooLargeError()

        with pytest.raises(LLMContextTooLargeError):
            await with_retry(operation, DEFAULT_RETRY)
        assert calls == 1  # Only called once, no retry

    async def test_raises_immediately_on_invalid_request(self) -> None:
        """Invalid request is non-retryable — no retry."""
        calls = 0

        async def operation() -> str:
            nonlocal calls
            calls += 1
            raise LLMInvalidRequestError()

        with pytest.raises(LLMInvalidRequestError):
            await with_retry(operation, DEFAULT_RETRY)
        assert calls == 1

    async def test_unknown_gateway_error_is_retried(self) -> None:
        """Base LLMGatewayError is retried conservatively."""
        calls = 0

        async def operation() -> str:
            nonlocal calls
            calls += 1
            if calls < 2:
                raise LLMGatewayError("unknown issue")
            return "ok"

        config = RetryConfig(max_attempts=3, base_delay=0.001, jitter=False)
        result = await with_retry(operation, config)
        assert result == "ok"
        assert calls == 2

    async def test_no_retry_config_succeeds_without_retry(self) -> None:
        """With NO_RETRY config, operation runs exactly once."""
        calls = 0

        async def operation() -> str:
            nonlocal calls
            calls += 1
            return "first_try"

        result = await with_retry(operation, NO_RETRY)
        assert result == "first_try"
        assert calls == 1

    async def test_no_retry_config_raises_without_retry(self) -> None:
        """With NO_RETRY config, retryable error is raised immediately."""

        async def operation() -> str:
            raise LLMRateLimitError()

        with pytest.raises(LLMRateLimitError):
            await with_retry(operation, NO_RETRY)


class TestWithRetryBackoff:
    """Verify exponential backoff timing."""

    async def test_exponential_backoff_delays_increase(self) -> None:
        """Verify delays increase exponentially across retry attempts."""
        delays: list[float] = []

        original_sleep = asyncio.sleep

        async def mock_sleep(delay: float) -> None:
            delays.append(delay)
            await original_sleep(0)  # Don't actually wait

        calls = 0

        async def operation() -> str:
            nonlocal calls
            calls += 1
            if calls < 4:
                raise LLMRateLimitError()
            return "success"

        config = RetryConfig(max_attempts=4, base_delay=1.0, jitter=False)

        with patch("narrare_core.llm.retry.asyncio.sleep", side_effect=mock_sleep):
            result = await with_retry(operation, config, intent="test")

        assert result == "success"
        assert calls == 4
        assert len(delays) == 3  # 3 retries (attempts 1, 2, 3)

        # Without jitter: delays should be 1.0, 2.0, 4.0
        assert delays[0] == 1.0
        assert delays[1] == 2.0
        assert delays[2] == 4.0

    async def test_backoff_respects_max_delay(self) -> None:
        """Verify delays are capped at max_delay."""
        delays: list[float] = []

        original_sleep = asyncio.sleep

        async def mock_sleep(delay: float) -> None:
            delays.append(delay)
            await original_sleep(0)

        calls = 0

        async def operation() -> str:
            nonlocal calls
            calls += 1
            if calls < 4:
                raise LLMTimeoutError()
            return "done"

        config = RetryConfig(max_attempts=4, base_delay=5.0, max_delay=8.0, jitter=False)

        with patch("narrare_core.llm.retry.asyncio.sleep", side_effect=mock_sleep):
            result = await with_retry(operation, config, intent="test")

        assert result == "done"
        # base=5, delays: 5.0, 10.0(capped to 8.0), 20.0(capped to 8.0)
        assert delays[0] == 5.0
        assert delays[1] == 8.0
        assert delays[2] == 8.0

    async def test_intent_is_logged(self) -> None:
        """Verify intent parameter is accepted and doesn't cause errors."""
        calls = 0

        async def operation() -> str:
            nonlocal calls
            calls += 1
            if calls < 2:
                raise LLMRateLimitError()
            return "ok"

        config = RetryConfig(max_attempts=3, base_delay=0.001, jitter=False)
        result = await with_retry(operation, config, intent="write")
        assert result == "ok"
