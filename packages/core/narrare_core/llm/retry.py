"""
Retry logic for LLM calls.

Retryable errors: rate limit, timeout, service unavailable.
Non-retryable: auth failure, context too large, invalid request.
"""

from __future__ import annotations

import asyncio
import os
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

import structlog

from narrare_core.shared.errors import (
    LLMAuthError,
    LLMContextTooLargeError,
    LLMGatewayError,
    LLMInvalidRequestError,
    LLMRateLimitError,
    LLMServiceUnavailableError,
    LLMTimeoutError,
)

logger = structlog.get_logger(__name__)

# Errors that should be retried
RETRYABLE_ERRORS = (
    LLMRateLimitError,
    LLMTimeoutError,
    LLMServiceUnavailableError,
)

# Errors that should NOT be retried
FATAL_ERRORS = (
    LLMAuthError,
    LLMContextTooLargeError,
    LLMInvalidRequestError,
)


@dataclass(frozen=True, slots=True)
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int
    base_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    jitter: bool = True  # add random jitter to avoid thundering herd

    def delay_for_attempt(self, attempt: int) -> float:
        """Calculate delay for a given attempt number (0-indexed)."""
        delay = min(self.base_delay * (2**attempt), self.max_delay)
        if self.jitter:
            delay *= 0.5 + random.random() * 0.5  # nosec: B311
        return delay

    @classmethod
    def from_env(cls, prefix: str = "NARRARE_RETRY_") -> RetryConfig:
        """Create RetryConfig from environment variables with fallback to defaults.

        Environment variables (with configurable prefix):
          {prefix}MAX_ATTEMPTS - int (default: current max_attempts)
          {prefix}BASE_DELAY   - float (default: current base_delay)
          {prefix}MAX_DELAY    - float (default: current max_delay)
          {prefix}JITTER       - "true"/"false" (default: current jitter)

        Args:
            prefix: Environment variable prefix. Defaults to "NARRARE_RETRY_".

        Returns:
            RetryConfig with values from environment, falling back to defaults
            when env vars are not set.
        """

        def _env_int(name: str, default: int) -> int:
            val = os.environ.get(name)
            if val is not None:
                try:
                    return int(val)
                except ValueError:
                    logger.warning("invalid_env_int", var=name, value=val)
            return default

        def _env_float(name: str, default: float) -> float:
            val = os.environ.get(name)
            if val is not None:
                try:
                    return float(val)
                except ValueError:
                    logger.warning("invalid_env_float", var=name, value=val)
            return default

        def _env_bool(name: str, default: bool) -> bool:
            val = os.environ.get(name)
            if val is not None:
                return val.lower() in ("true", "1", "yes")
            return default

        return cls(
            max_attempts=_env_int(f"{prefix}MAX_ATTEMPTS", 3),
            base_delay=_env_float(f"{prefix}BASE_DELAY", 1.0),
            max_delay=_env_float(f"{prefix}MAX_DELAY", 60.0),
            jitter=_env_bool(f"{prefix}JITTER", True),
        )


# Standard retry configurations
DEFAULT_RETRY = RetryConfig(max_attempts=3, base_delay=1.0)
FAST_RETRY = RetryConfig(max_attempts=2, base_delay=0.5)
PATIENT_RETRY = RetryConfig(max_attempts=5, base_delay=2.0)
NO_RETRY = RetryConfig(max_attempts=1)


def is_retryable(error: LLMGatewayError) -> bool:
    """Determine if an LLM error should trigger a retry."""
    return isinstance(error, RETRYABLE_ERRORS)


async def with_retry[T](
    operation: Callable[[], Awaitable[T]],
    config: RetryConfig,
    *,
    intent: str = "",
) -> T:
    """
    Execute an async operation with retry logic.

    Args:
        operation: Async callable to execute.
        config: Retry configuration.
        intent: LLM intent name for logging.

    Returns:
        Result of the operation on success.

    Raises:
        LLMGatewayError: After all retry attempts are exhausted,
                         or immediately for non-retryable errors.
    """
    last_error: LLMGatewayError | None = None

    for attempt in range(config.max_attempts):
        try:
            return await operation()
        except FATAL_ERRORS as e:
            # Non-retryable — fail immediately
            logger.error(
                "llm_fatal_error",
                intent=intent,
                error_type=type(e).__name__,
                error=str(e),
                attempt=attempt + 1,
            )
            raise
        except RETRYABLE_ERRORS as e:
            last_error = e
            if attempt + 1 == config.max_attempts:
                break
            delay = config.delay_for_attempt(attempt)
            logger.warning(
                "llm_retry",
                intent=intent,
                error_type=type(e).__name__,
                attempt=attempt + 1,
                max_attempts=config.max_attempts,
                retry_after=round(delay, 2),
            )
            await asyncio.sleep(delay)
        except LLMGatewayError as e:
            # Unknown gateway error — retry conservatively
            last_error = e
            if attempt + 1 == config.max_attempts:
                break
            delay = config.delay_for_attempt(attempt)
            logger.warning(
                "llm_unknown_error_retry",
                intent=intent,
                error_type=type(e).__name__,
                attempt=attempt + 1,
                retry_after=round(delay, 2),
            )
            await asyncio.sleep(delay)

    logger.error(
        "llm_all_retries_exhausted",
        intent=intent,
        attempts=config.max_attempts,
        last_error=str(last_error),
    )
    raise last_error or LLMGatewayError("All retry attempts exhausted")
