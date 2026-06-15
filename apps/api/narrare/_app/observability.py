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

# OTel setup-outcome state (AUFG-05-14)
_otel_state: str | None = None  # ``None`` = not recorded yet, then one of:
# "not_configured" | "configured_ok" | "configured_failed" | "package_unavailable"
_endpoint_configured: bool = False


def _probe_once() -> None:
    """Probe OTel availability exactly once; cache the result.

    On the first call, attempts to import ``opentelemetry.trace``.  If the
    import succeeds the module is marked available.  On ``ImportError`` or
    any other exception the module is marked unavailable and exactly one
    structured warning is emitted.  Subsequent calls are a no-op.
    """
    global _otel_available, _failure_reason, _warning_emitted, _otel_state

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
            _otel_state = "package_unavailable"
            _failure_reason = f"ImportError: {exc}"
        except Exception as exc:
            _otel_available = False
            _otel_state = "package_unavailable"
            _failure_reason = f"{type(exc).__name__}: {exc}"

        if not _otel_available and not _warning_emitted:
            logger.warning(
                "otel_unavailable",
                reason=_failure_reason,
                _message="OpenTelemetry is not available; trace context will be empty",
            )
            _warning_emitted = True


def get_observability_status() -> dict[str, Any]:
    """Return the current OTel availability and health-severity status.

    Returns:
        A dict with the following keys:

        - ``available`` (bool): Backward-compat.  ``True`` iff *severity* is
          ``"healthy"``.
        - ``state`` (str): One of ``not_configured``, ``configured_ok``,
          ``configured_failed``, ``package_unavailable``.
        - ``severity`` (str): ``healthy`` | ``degraded`` | ``critical``.
          Derived from *state* per the OTel Health-Severity Policy.
        - ``endpoint_configured`` (bool): ``True`` iff
          ``OTEL_EXPORTER_OTLP_ENDPOINT`` was set when setup was attempted.
        - ``failure_reason`` (str): Non-empty when *state* is a failure state.
        - ``warning_emitted`` (bool): Whether the one-shot warning was fired.
    """
    _probe_once()
    with _state_lock:
        # Determine state — default when no outcome recorded yet
        if _otel_state is not None:
            state = _otel_state
        elif _otel_available is True:
            state = "not_configured"
        else:
            state = "package_unavailable"

        # Map state → severity (§2.1 of the policy)
        if state in ("not_configured", "configured_ok"):
            severity: str = "healthy"
        elif state in ("configured_failed", "package_unavailable"):
            severity = "degraded"
        else:
            severity = "critical"  # reserved for S5 mandatory-telemetry profiles

        return {
            "available": severity == "healthy",
            "state": state,
            "severity": severity,
            "endpoint_configured": _endpoint_configured,
            "failure_reason": _failure_reason,
            "warning_emitted": _warning_emitted,
        }


def record_otel_setup_outcome(
    *,
    endpoint_configured: bool,
    succeeded: bool,
    failure_reason: str = "",
) -> None:
    """Record the OTLP exporter setup outcome.

    Called by ``setup_telemetry`` exactly once after attempting configuration.
    Transitions internal state to ``configured_ok`` / ``configured_failed`` /
    ``not_configured`` and updates severity accordingly.  Thread-safe.

    If the package was already determined unavailable (via ``_probe_once`` or
    ``_mark_unavailable``), that state takes priority and this is a no-op.

    Args:
        endpoint_configured: Whether ``OTEL_EXPORTER_OTLP_ENDPOINT`` was set.
        succeeded: Whether OTLP exporter configuration succeeded.
        failure_reason: Human-readable reason when *succeeded* is ``False``.
    """
    global _otel_state, _endpoint_configured, _failure_reason

    with _state_lock:
        # ``package_unavailable`` takes priority — stronger signal
        if _otel_state == "package_unavailable":
            return

        _endpoint_configured = endpoint_configured

        if not endpoint_configured and succeeded:
            _otel_state = "not_configured"
        elif endpoint_configured and succeeded:
            _otel_state = "configured_ok"
        elif endpoint_configured and not succeeded:
            _otel_state = "configured_failed"
            _failure_reason = failure_reason


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
    global _otel_available, _failure_reason, _warning_emitted, _otel_state

    with _state_lock:
        if _otel_available is False:
            return  # already degraded — no further logging
        _otel_available = False
        _otel_state = "package_unavailable"
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
