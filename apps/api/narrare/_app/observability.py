"""Observability helpers — trace context extraction for SSE and logging.

Provides a single source of truth for extracting the current OpenTelemetry
trace context.  All SSE routers and middleware use this function so trace
IDs are consistently propagated.

Graceful degradation:
  - OpenTelemetry package not installed → returns empty dict (no crash)
  - No active span → returns empty dict
  - Active span → returns ``{"x_trace_id": ..., "x_span_id": ...}``
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def get_current_trace_context() -> dict[str, str]:
    """Extract the current OTel trace_id and span_id if available.

    Returns:
        Dict with ``x_trace_id`` and ``x_span_id`` keys if a recording
        span exists, or an empty dict if OTel is not configured or
        there is no active span.
    """
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span.is_recording():
            ctx = span.get_span_context()
            return {
                "x_trace_id": format(ctx.trace_id, "032x"),
                "x_span_id": format(ctx.span_id, "016x"),
            }
    except ImportError:
        pass
    except Exception:
        logger.warning("otel_context_fetch_failed", exc_info=True)
    return {}


def enrich_sse_data(data: dict[str, Any]) -> dict[str, Any]:
    """Enrich an SSE event data dict with trace context.

    Adds ``x_trace_id`` and ``x_span_id`` to the data dict if a
    recording OTel span exists.  Returns a new dict when trace context
    is present, or the original dict unchanged.

    Args:
        data: The event data dict to enrich.

    Returns:
        The enriched dict (or original if no trace context).
    """
    ctx = get_current_trace_context()
    if ctx:
        # Return a shallow copy with trace context merged
        enriched = dict(data)
        enriched.update(ctx)
        return enriched
    return data
