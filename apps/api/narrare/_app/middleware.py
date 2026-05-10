"""Request/response middleware."""

from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING

import structlog
from starlette.middleware.base import BaseHTTPMiddleware

if TYPE_CHECKING:
    from fastapi import Request, Response

logger = structlog.get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with duration and status code."""

    async def dispatch(self, request: Request, call_next: object) -> Response:
        request_id = str(uuid.uuid4())[:8]
        start = time.monotonic()

        # Bind request context for all log calls in this request
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        try:
            response: Response = await call_next(request)  # type: ignore[operator]
            duration_ms = round((time.monotonic() - start) * 1000)
            logger.info(
                "http_request",
                status=response.status_code,
                duration_ms=duration_ms,
            )
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception as e:
            duration_ms = round((time.monotonic() - start) * 1000)
            logger.error("http_request_error", error=str(e), duration_ms=duration_ms)
            raise
        finally:
            structlog.contextvars.unbind_contextvars("request_id", "method", "path")
