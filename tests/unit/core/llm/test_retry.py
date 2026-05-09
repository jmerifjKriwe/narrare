"""Tests for llm/retry.py"""

from __future__ import annotations

import pytest

from narrare_core.llm.retry import (
    DEFAULT_RETRY,
    RetryConfig,
    is_retryable,
    with_retry,
)
from narrare_core.shared.errors import (
    LLMAuthError,
    LLMContextTooLargeError,
    LLMRateLimitError,
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


class TestIsRetryable:
    def test_rate_limit_is_retryable(self) -> None:
        assert is_retryable(LLMRateLimitError()) is True

    def test_timeout_is_retryable(self) -> None:
        assert is_retryable(LLMTimeoutError()) is True

    def test_auth_error_is_not_retryable(self) -> None:
        assert is_retryable(LLMAuthError()) is False

    def test_context_too_large_is_not_retryable(self) -> None:
        assert is_retryable(LLMContextTooLargeError()) is False


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
