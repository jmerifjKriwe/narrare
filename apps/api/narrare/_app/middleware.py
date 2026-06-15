"""Request/response middleware and CSRF origin validation (AUFG-05-13).

Uses :func:`narrare._app.observability.get_current_trace_context` for
trace context extraction so SSE routers and middleware share a single
source of truth.
"""

from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from narrare._app.observability import get_current_trace_context

if TYPE_CHECKING:
    from fastapi import Request, Response

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# CSRF Origin / Referer validation (AUFG-05-13)
# ---------------------------------------------------------------------------

SAFE_METHODS: frozenset[str] = frozenset({"GET", "HEAD", "OPTIONS"})
"""HTTP methods that are exempt from origin validation."""


def get_trusted_origins(settings: object) -> list[str]:
    """Return the list of trusted origins from application settings.

    In production the operator is responsible for populating
    ``NARRARE_CSRF_TRUSTED_ORIGINS``.  In dev/test the default
    ``["http://localhost:3000"]`` is used.
    """
    return settings.csrf_trusted_origins  # type: ignore[union-attr]  # duck-typed


class OriginValidationMiddleware(BaseHTTPMiddleware):
    """Defense-in-depth: validate Origin/Referer on state-changing HTTP methods.

    Primary CSRF defence is Bearer auth (already in place).  This middleware
    adds a secondary check for browser-originated requests that carry an
    ``Origin`` or ``Referer`` header.

    Behaviour
    ---------
    * **Safe methods** (GET, HEAD, OPTIONS) — always pass through.
    * **Origin present & trusted** — pass through.
    * **Origin present & NOT trusted** — HTTP 403 ``CSRF_ORIGIN_MISMATCH``.
    * **No Origin, Referer present** — parse origin from Referer and re-check.
    * **Neither Origin nor Referer** — allow IF a valid ``Authorization: Bearer``
      token is present (programmatic clients: CLI / MCP / A2A).
    * **No Origin, no Referer, no Bearer** — HTTP 403.
    """

    def __init__(self, app: object, trusted_origins: list[str]) -> None:
        """Initialise with a list of origin strings (no trailing slash)."""
        super().__init__(app)  # type: ignore[arg-type]
        self.trusted_origins = trusted_origins

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        # ── safe methods are always allowed ──────────────────────────────
        if request.method in SAFE_METHODS:
            return await call_next(request)

        origin = request.headers.get("origin", "")
        referer = request.headers.get("referer", "")

        # ── Origin present → exact match check ───────────────────────────
        if origin:
            if origin in self.trusted_origins:
                return await call_next(request)
            return self._reject()

        # ── No Origin → fall back to Referer ─────────────────────────────
        if referer:
            parsed = urlparse(referer)
            ref_origin = f"{parsed.scheme}://{parsed.netloc}"
            if ref_origin in self.trusted_origins:
                return await call_next(request)
            return self._reject()

        # ── Neither Origin nor Referer → check Bearer token ──────────────
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            if self._is_valid_bearer(token):
                return await call_next(request)

        # ── No valid credentials → 403 ───────────────────────────────────
        return self._reject()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _reject(self) -> Response:
        """Return a standardised 403 response."""
        from starlette.responses import JSONResponse

        return JSONResponse(
            status_code=403,
            content={"detail": "Origin not allowed", "code": "CSRF_ORIGIN_MISMATCH"},
        )

    @staticmethod
    def _is_valid_bearer(token: str) -> bool:
        """Return ``True`` when *token* is a syntactically valid JWT.

        Uses the same :func:`verify_access_token <narrare.auth.security.verify_access_token>`
        function as the Bearer-auth dependency.
        """
        from narrare._app.config import get_settings
        from narrare.auth.security import verify_access_token

        settings = get_settings()
        payload = verify_access_token(token, settings.secret_key)
        return payload is not None


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with duration, status, and correlation context."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Use full UUID, accept from upstream proxy via X-Request-ID header
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # OTel trace context (if available)
        trace_ctx = get_current_trace_context()
        trace_id = trace_ctx.get("x_trace_id", "")
        span_id = trace_ctx.get("x_span_id", "")

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
