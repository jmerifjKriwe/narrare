"""Error classification for LLM gateway exceptions.

Extracted from gateway.py for RULE-04 compliance.

Converts provider exceptions into domain errors using a three-layer
classification strategy:
    L1: pydantic-ai typed exceptions (ModelHTTPError, UnexpectedModelBehavior)
    L2: Standard library exceptions (TimeoutError, etc.)
    L3: String heuristic fallback
"""

from __future__ import annotations

import asyncio

from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior

from narrare_core.shared.errors import (
    LLMAuthError,
    LLMContextTooLargeError,
    LLMGatewayError,
    LLMInvalidRequestError,
    LLMRateLimitError,
    LLMServiceUnavailableError,
    LLMTimeoutError,
)


def classify_error(error: Exception) -> LLMGatewayError:
    """Convert provider exceptions to domain errors.

    Uses a three-layer classification:
        L1: pydantic-ai typed exceptions
        L2: stdlib exceptions
        L3: string heuristic fallback

    Args:
        error: The raw exception from the provider or transport.

    Returns:
        A domain-specific LLMGatewayError subclass.
    """
    # L1: pydantic-ai typed exceptions
    if isinstance(error, ModelHTTPError):
        status = error.status_code
        if status == 401:
            return LLMAuthError(str(error))
        if status == 429:
            return LLMRateLimitError(str(error))
        if status == 400:
            return LLMInvalidRequestError(str(error))
        if status in (502, 503):
            return LLMServiceUnavailableError(str(error))
        return LLMGatewayError(f"LLM HTTP error {status}: {error}")
    if isinstance(error, UnexpectedModelBehavior):
        return LLMGatewayError(f"Unexpected model behavior: {error}")

    # L2: stdlib exceptions
    if isinstance(error, (asyncio.TimeoutError, TimeoutError)):
        return LLMTimeoutError(str(error))

    # L3: string heuristic fallback
    msg = str(error).lower()
    if any(k in msg for k in ("api key", "authentication", "unauthorized", "401")):
        return LLMAuthError(str(error))
    if any(k in msg for k in ("rate limit", "429", "too many requests", "quota")):
        return LLMRateLimitError(str(error))
    if any(k in msg for k in ("context", "token", "length", "too long", "maximum")):
        return LLMContextTooLargeError(str(error))
    if any(k in msg for k in ("timeout", "timed out", "deadline")):
        return LLMTimeoutError(str(error))
    if any(k in msg for k in ("503", "502", "overloaded", "unavailable", "capacity")):
        return LLMServiceUnavailableError(str(error))
    if any(k in msg for k in ("invalid", "400", "bad request")):
        return LLMInvalidRequestError(str(error))
    return LLMGatewayError(f"Unexpected LLM error: {error}")
