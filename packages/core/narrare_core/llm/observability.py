"""LLM observability — Langfuse integration.

Provides optional Langfuse tracing for all LLM calls.
If Langfuse is not configured (no LANGFUSE_SECRET_KEY), all operations are no-ops.

Graceful degradation:
  - No LANGFUSE_SECRET_KEY set → everything is a no-op, zero overhead.
  - Langfuse import fails → warning logged, all methods are no-ops.
  - Langfuse API call fails → debug logged, LLM call continues.
  - Uses flush_async() never flush() — never blocks on Langfuse I/O.

See ADR-010 for rationale.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from narrare_core.llm.intents import LLMIntent
    from narrare_core.llm.result import TokenUsage

logger = structlog.get_logger(__name__)


def _is_configured() -> bool:
    """Check if Langfuse is configured via environment variables."""
    return bool(os.environ.get("LANGFUSE_SECRET_KEY"))


def _create_client() -> Any:
    """Create a Langfuse client if configured, None otherwise.

    Returns None if LANGFUSE_SECRET_KEY is not set or if the langfuse
    package is not importable. Never raises.
    """
    if not _is_configured():
        return None
    try:
        from langfuse import Langfuse  # type: ignore[import-untyped]

        return Langfuse()
    except Exception:
        logger.warning("langfuse_init_failed", exc_info=True)
        return None


class LLMObservability:
    """Optional LLM call tracing via Langfuse.

    All methods are no-ops when Langfuse is not configured.
    Never raises — errors are logged and swallowed so LLM calls are never affected.

    Usage::

        obs = LLMObservability()
        trace = obs.start_trace(intent, model, provider, system_prompt, user_prompt)
        # ... perform LLM call ...
        obs.finish_trace(trace, result_text, token_usage, duration_ms)
        # On error:
        obs.record_error(trace, error_str, error_type_name)
    """

    def __init__(self) -> None:
        self._client: Any = _create_client()

    @property
    def enabled(self) -> bool:
        """Whether Langfuse tracing is active."""
        return self._client is not None

    def start_trace(
        self,
        intent: LLMIntent,
        model: str,
        provider: str,
        system_prompt: str,
        user_prompt: str,
    ) -> Any:
        """Start a Langfuse trace for an LLM call.

        Returns an opaque trace context to pass to finish_trace / record_error,
        or None if tracing is disabled.
        """
        if not self._client:
            return None
        try:
            client: Any = self._client

            trace = client.trace(  # type: ignore[union-attr]
                name=f"llm.{intent.value}",
                metadata={
                    "intent": intent.value,
                    "model": model,
                    "provider": provider,
                },
            )
            generation = trace.generation(  # type: ignore[union-attr]
                name=f"llm.{intent.value}",
                model=model,
                input={
                    "system": system_prompt[:500],  # truncate for storage
                    "user": user_prompt[:1000],
                },
            )
            return {"trace": trace, "generation": generation}  # type: ignore[return-value]
        except Exception:
            logger.debug("langfuse_trace_start_failed", exc_info=True)
            return None

    def finish_trace(
        self,
        trace_context: Any,
        result_text: str,
        usage: TokenUsage,
        duration_ms: float,
    ) -> None:
        """Finish a Langfuse trace with result and usage.

        No-op if trace_context is None or Langfuse is not configured.
        """
        if not trace_context or not self._client:
            return
        try:
            generation = trace_context["generation"]
            generation.end(
                output=result_text[:2000],  # truncate for storage
                usage={
                    "input": usage.prompt_tokens,
                    "output": usage.completion_tokens,
                    "total": usage.total_tokens,
                    "cache_read": usage.cache_read_tokens,
                    "cache_creation": usage.cache_creation_tokens,
                },
                metadata={
                    "duration_ms": duration_ms,
                    "cache_savings_pct": (
                        round(usage.cache_read_tokens / max(usage.prompt_tokens, 1) * 100, 1)
                        if usage.cache_read_tokens > 0
                        else 0
                    ),
                },
            )
            # Flush in background — never block the response
            self._client.flush_async()  # type: ignore[union-attr]
        except Exception:
            logger.debug("langfuse_trace_finish_failed", exc_info=True)

    def record_error(
        self,
        trace_context: Any,
        error: str,
        error_type: str,
    ) -> None:
        """Record an error in a Langfuse trace.

        No-op if trace_context is None or Langfuse is not configured.
        """
        if not trace_context or not self._client:
            return
        try:
            generation = trace_context["generation"]
            generation.end(
                output=None,
                metadata={"error": error, "error_type": error_type},
                status_message=error,
                level="ERROR",
            )
            self._client.flush_async()  # type: ignore[union-attr]
        except Exception:
            logger.debug("langfuse_error_record_failed", exc_info=True)
