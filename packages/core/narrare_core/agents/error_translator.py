"""Translate pydantic-ai exceptions into NarrareAgent error classes.

This module is the single place where the mapping from framework
exceptions to domain errors lives.  Both ``run()`` and ``run_stream()``
use the same translator so that streaming and non-streaming paths
produce identical error types.

RULE-04: Extracted from base.py to keep file size manageable.
"""

from __future__ import annotations

import asyncio

import structlog
from pydantic_ai.exceptions import (
    ModelAPIError,
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

logger = structlog.get_logger(__name__)


def classify_error(
    exc: BaseException,
    *,
    agent_name: str = "",
) -> AgentError:
    """Translate a raw exception into a typed NarrareAgent error.

    Args:
        exc: The original exception raised during an agent run.
        agent_name: Qualified name of the agent class (for logging).

    Returns:
        A subclass of AgentError with privacy-safe attributes.

    The function logs the error via structlog with privacy-safe
    attributes (no prompt text, no user content).
    """

    # --- Cancelled (user abort / disconnect) ---
    if isinstance(exc, asyncio.CancelledError):
        error = AgentCancelledError(
            "Agent run was cancelled",
            agent_name=agent_name,
            original=exc,
        )
        logger.warning(
            "agent_run_cancelled",
            **error.log_attrs,
        )
        return error

    # --- Timeout ---
    if isinstance(exc, asyncio.TimeoutError):
        error = AgentTimeoutError(
            "Agent run timed out",
            agent_name=agent_name,
            original=exc,
        )
        logger.warning(
            "agent_run_timeout",
            **error.log_attrs,
        )
        return error

    # --- pydantic-ai specific ---

    # ModelHTTPError (has status_code + body) → ModelExecutionError
    # NOTE: check before ModelAPIError — ModelHTTPError is a subclass.
    if isinstance(exc, ModelHTTPError):
        status = exc.status_code
        provider_code = f"HTTP_{status}" if status else None
        error = ModelExecutionError(
            f"Model provider returned HTTP {status}",
            agent_name=agent_name,
            original=exc,
            provider_code=provider_code,
        )
        logger.error(
            "agent_model_http_error",
            **error.log_attrs,
        )
        return error

    # ModelAPIError (general API failure)
    if isinstance(exc, ModelAPIError):
        error = ModelExecutionError(
            f"Model API error: {exc.message}",
            agent_name=agent_name,
            original=exc,
        )
        logger.error(
            "agent_model_api_error",
            **error.log_attrs,
        )
        return error

    # UnexpectedModelBehavior — could be content filter, incomplete
    # tool call, or exhausted retries.  We classify as retry-exhausted
    # when the message mentions retries; otherwise as model execution.
    if isinstance(exc, UnexpectedModelBehavior):
        msg = str(exc).lower()
        if "retry" in msg or "exceeded" in msg or "too many" in msg:
            error = ModelRetryExhaustedError(
                f"Model retries exhausted: {exc.message}",
                agent_name=agent_name,
                original=exc,
            )
            logger.warning(
                "agent_model_retry_exhausted",
                **error.log_attrs,
            )
            return error

        error = ModelExecutionError(
            f"Unexpected model behavior: {exc.message}",
            agent_name=agent_name,
            original=exc,
        )
        logger.error(
            "agent_unexpected_model_behavior",
            **error.log_attrs,
        )
        return error

    # UsageLimitExceeded → ModelExecutionError
    if isinstance(exc, UsageLimitExceeded):
        error = ModelExecutionError(
            f"Usage limit exceeded: {exc.message}",
            agent_name=agent_name,
            original=exc,
            provider_code="USAGE_LIMIT_EXCEEDED",
        )
        logger.warning(
            "agent_usage_limit_exceeded",
            **error.log_attrs,
        )
        return error

    # UserError (developer misuse) — wrapped in AgentError for
    # uniform handling at service boundaries.
    if isinstance(exc, UserError):
        error = AgentError(
            f"Agent usage error: {exc.message}",
            agent_name=agent_name,
            error_type="user_error",
            original=exc,
        )
        logger.error(
            "agent_user_error",
            **error.log_attrs,
        )
        return error

    # --- Catch-all ---
    error = AgentError(
        f"Agent run failed: {exc}",
        agent_name=agent_name,
        error_type="unknown",
        original=exc,
    )
    logger.error(
        "agent_unknown_error",
        **error.log_attrs,
    )
    return error
