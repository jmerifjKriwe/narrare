"""
Retry logic for LLM calls.

Retryable errors: rate limit, timeout, service unavailable.
Non-retryable: auth failure, context too large, invalid request.
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass

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
            delay *= 0.5 + random.random() * 0.5  # noqa: S311
        return delay


# Standard retry configurations
DEFAULT_RETRY = RetryConfig(max_attempts=3, base_delay=1.0)
FAST_RETRY = RetryConfig(max_attempts=2, base_delay=0.5)
PATIENT_RETRY = RetryConfig(max_attempts=5, base_delay=2.0)
NO_RETRY = RetryConfig(max_attempts=1)


def is_retryable(error: LLMGatewayError) -> bool:
    """Determine if an LLM error should trigger a retry."""
    return isinstance(error, RETRYABLE_ERRORS)


async def with_retry(
    operation: object,
    config: RetryConfig,
    *,
    intent: str = "",
) -> object:
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
            if callable(operation):
                return await operation()  # type: ignore[operator]
            raise TypeError("operation must be callable")
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
