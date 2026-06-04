"""Observability helpers — trace context extraction for SSE and logging.

Provides a single source of truth for extracting the current OpenTelemetry
trace context.  All SSE routers and middleware use this function so trace
IDs are consistently propagated.

Graceful degradation:
  - OpenTelemetry package not installed → returns empty dict (no crash)
  - No active span → returns empty dict
  - Active span → returns ``{"x_trace_id": ..., "x_span_id": ...}``

Degraded-state visibility:
  - On first ``ImportError`` or unexpected exception, exactly one structured
    warning is emitted via structlog.  Subsequent calls return silently.
  - Module-level state (available, failure reason, warning-emitted flag) is
    cached and queryable via :func:`get_observability_status`.
"""

from __future__ import annotations

import threading
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class _NoOpSpan:
    """Minimal span object used when OpenTelemetry is unavailable."""

    def __enter__(self) -> _NoOpSpan:
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def set_attribute(self, _key: str, _value: object) -> None:
        """Ignore attributes in degraded mode."""
        return None


class _NoOpTracer:
    """Tracer fallback preserving ``start_as_current_span`` call sites."""

    def start_as_current_span(self, _name: str, *args: Any, **kwargs: Any) -> _NoOpSpan:
        """Return a no-op context manager span."""
        return _NoOpSpan()

    def start_span(self, _name: str, *args: Any, **kwargs: Any) -> _NoOpSpan:
        """Return a no-op span."""
        return _NoOpSpan()


# ---------------------------------------------------------------------------
# Module-level state tracking
# ---------------------------------------------------------------------------
# Accessed only under _state_lock.  The lock is a stdlib threading.Lock
# (not re-entrant) which is sufficient — we never re-enter while holding it.

_state_lock = threading.Lock()

_otel_available: bool | None = None  # ``None`` = not yet probed
_failure_reason: str = ""
_warning_emitted: bool = False


def _probe_once() -> None:
    """Probe OTel availability exactly once; cache the result.

    On the first call, attempts to import ``opentelemetry.trace``.  If the
    import succeeds the module is marked available.  On ``ImportError`` or
    any other exception the module is marked unavailable and exactly one
    structured warning is emitted.  Subsequent calls are a no-op.
    """
    global _otel_available, _failure_reason, _warning_emitted

    with _state_lock:
        if _otel_available is not None:
            return  # already probed

        try:
            import opentelemetry.trace as _trace_mod

            # Verify the tracer provider is actually functional
            _ = _trace_mod.get_tracer(__name__)
            _otel_available = True
        except ImportError as exc:
            _otel_available = False
            _failure_reason = f"ImportError: {exc}"
        except Exception as exc:
            _otel_available = False
            _failure_reason = f"{type(exc).__name__}: {exc}"

        if not _otel_available and not _warning_emitted:
            logger.warning(
                "otel_unavailable",
                reason=_failure_reason,
                _message="OpenTelemetry is not available; trace context will be empty",
            )
            _warning_emitted = True


def get_observability_status() -> dict[str, Any]:
    """Return the current OTel availability status.

    Returns:
        A dict with the following keys:

        - ``available`` (bool): ``True`` if OTel was successfully probed.
        - ``failure_reason`` (str): Non-empty when *available* is ``False``.
        - ``warning_emitted`` (bool): Whether the one-shot warning was fired.
    """
    _probe_once()
    with _state_lock:
        return {
            "available": bool(_otel_available),
            "failure_reason": _failure_reason,
            "warning_emitted": _warning_emitted,
        }


def get_tracer(name: str) -> Any:
    """Return an OpenTelemetry tracer or a no-op tracer when unavailable.

    This centralizes tracer lookup so callers do not need their own import or
    degradation logic.
    """
    _probe_once()
    with _state_lock:
        if _otel_available is False:
            return _NoOpTracer()

    try:
        from opentelemetry import trace

        return trace.get_tracer(name)
    except ImportError:
        _mark_unavailable("ImportError on tracer lookup")
    except Exception:
        _mark_unavailable("unexpected error during tracer lookup")
    return _NoOpTracer()


def get_current_trace_context() -> dict[str, str]:
    """Extract the current OTel trace_id and span_id if available.

    Returns:
        Dict with ``x_trace_id`` and ``x_span_id`` keys if a recording
        span exists, or an empty dict if OTel is not configured or
        there is no active span.
    """
    _probe_once()

    # Short-circuit when OTel was already determined unavailable.
    with _state_lock:
        if _otel_available is False:
            return {}

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
        # Unlikely after probe success, but handle gracefully.
        _mark_unavailable("ImportError on context extraction")
    except Exception:
        _mark_unavailable("unexpected error during context extraction")
    return {}


def _mark_unavailable(reason: str) -> None:
    """Transition to unavailable state; emit warning on first occurrence."""
    global _otel_available, _failure_reason, _warning_emitted

    with _state_lock:
        if _otel_available is False:
            return  # already degraded — no further logging
        _otel_available = False
        _failure_reason = reason
        if not _warning_emitted:
            logger.warning(
                "otel_degraded",
                reason=reason,
                _message="OpenTelemetry became unavailable at runtime",
            )
            _warning_emitted = True


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
