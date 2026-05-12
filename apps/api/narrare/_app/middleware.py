"""Request/response middleware."""

from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

if TYPE_CHECKING:
    from fastapi import Request, Response

logger = structlog.get_logger(__name__)


def _get_otel_trace_context() -> tuple[str, str]:
    """Extract OpenTelemetry trace_id and span_id if available."""
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span.is_recording():
            ctx = span.get_span_context()
            return format(ctx.trace_id, "032x"), format(ctx.span_id, "016x")
    except ImportError:
        pass
    return "", ""


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with duration, status, and correlation context."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Use full UUID, accept from upstream proxy via X-Request-ID header
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # OTel trace context (if available)
        trace_id, span_id = _get_otel_trace_context()

        start = time.monotonic()

        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            trace_id=trace_id,
            span_id=span_id,
            method=request.method,
            path=request.url.path,
        )

        try:
            response = await call_next(request)
            duration_ms = round((time.monotonic() - start) * 1000)
            logger.info(
                "http_request",
                status=response.status_code,
                duration_ms=duration_ms,
            )
            response.headers["X-Request-ID"] = request_id
            if trace_id:
                response.headers["X-Trace-ID"] = trace_id
            return response
        except Exception as e:
            duration_ms = round((time.monotonic() - start) * 1000)
            logger.error("http_request_error", error=str(e), duration_ms=duration_ms)
            raise
        finally:
            structlog.contextvars.unbind_contextvars(
                "request_id",
                "trace_id",
                "span_id",
                "method",
                "path",
            )
