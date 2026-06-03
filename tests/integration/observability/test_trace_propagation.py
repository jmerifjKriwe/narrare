"""Integration tests for HTTP-level trace propagation.

Validates the observability chain documented in ``docs/development/observability-guide.md``:

- Test 1: HTTP ``X-Request-ID`` is echoed from request → response
- Test 2: ``X-Trace-ID`` header is set when OTel context is present
- Test 3: Middleware performs structured logging (``logger.info()`` call)

SSE-specific tests (Tests 4-5) are in ``test_sse_trace_propagation.py``
(split to comply with RULE-04 400-line limit).

Log record capture note:
    The app's structlog config uses ``wrap_for_formatter`` with
    ``cache_logger_on_first_use=True``.  The lifespan
    (``_configure_production_logging``) clears root handlers at startup,
    and structlog proxies cache the resolved logger after the first use,
    making test handlers added after lifespan ineffective.  Instead of
    capturing ``LogRecord`` objects, we patch the middleware's logger
    directly to verify the ``info()`` call contract.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import ANY, patch

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = [pytest.mark.integration, pytest.mark.requires_db]


# =========================================================================
# Test 1: HTTP X-Request-ID propagation
# =========================================================================


class TestRequestIdPropagation:
    """Verify ``X-Request-ID`` flows from request → response."""

    async def test_with_explicit_header(self, client: AsyncClient) -> None:
        """Send a request with ``X-Request-ID`` — it must be echoed back."""
        request_id = str(uuid.uuid4())
        response = await client.get("/health", headers={"X-Request-ID": request_id})

        assert response.status_code == 200
        assert response.headers.get("X-Request-ID") == request_id

    async def test_without_header_generates_one(self, client: AsyncClient) -> None:
        """Request without ``X-Request-ID`` gets an auto-generated UUID."""
        response = await client.get("/health")

        assert response.status_code == 200
        header = response.headers.get("X-Request-ID")
        assert header is not None, "X-Request-ID header must be present"
        # Verify it's a valid UUID v4
        parsed = uuid.UUID(header)
        assert parsed.version == 4

    async def test_request_id_appears_with_known_verb(self, client: AsyncClient) -> None:
        """``X-Request-ID`` is echoed for POST endpoints too (even on error)."""
        request_id = str(uuid.uuid4())
        response = await client.post(
            "/api/v1/writing/chapters/00000000-0000-0000-0000-000000000000/extend",
            headers={"X-Request-ID": request_id},
            json={"text": "test", "context": ""},
        )
        # Middleware runs before auth — header is set even on 401
        assert response.headers.get("X-Request-ID") == request_id
        assert response.status_code == 401  # no auth header

    async def test_multiple_requests_get_different_ids(self, client: AsyncClient) -> None:
        """Two consecutive requests without explicit IDs get unique IDs."""
        r1 = await client.get("/health")
        r2 = await client.get("/health")
        id1 = r1.headers.get("X-Request-ID")
        id2 = r2.headers.get("X-Request-ID")
        assert id1 is not None
        assert id2 is not None
        assert id1 != id2


# =========================================================================
# Test 2: X-Trace-ID propagation (via mocked OTel context)
# =========================================================================


class TestTraceIdPropagation:
    """Verify ``X-Trace-ID`` header when OTel context is available.

    Without a real OTel Collector, the middleware returns empty trace
    context.  These tests patch ``get_current_trace_context`` to simulate
    an active OTel span.
    """

    async def test_with_mocked_trace_context(self, client: AsyncClient) -> None:
        """When OTel context is present, ``X-Trace-ID`` is set."""
        from narrare._app import middleware as mw_module

        fake_trace_id = "ff" + "a" * 30
        fake_span_id = "bb" + "c" * 14

        with patch.object(
            mw_module,
            "get_current_trace_context",
            return_value={
                "x_trace_id": fake_trace_id,
                "x_span_id": fake_span_id,
            },
        ):
            response = await client.get("/health")

        assert response.status_code == 200
        assert response.headers.get("X-Trace-ID") == fake_trace_id

    async def test_span_id_is_never_a_header(self, client: AsyncClient) -> None:
        """``X-Span-ID`` is NOT set as a response header (it's internal)."""
        from narrare._app import middleware as mw_module

        with patch.object(
            mw_module,
            "get_current_trace_context",
            return_value={
                "x_trace_id": "ff" + "b" * 30,
                "x_span_id": "cc" + "d" * 14,
            },
        ):
            response = await client.get("/health")

        assert "X-Span-ID" not in response.headers
        assert "X-Trace-ID" in response.headers

    async def test_no_trace_id_when_otel_disabled(self, client: AsyncClient) -> None:
        """Without OTel context, ``X-Trace-ID`` is absent."""
        response = await client.get("/health")
        assert "X-Trace-ID" not in response.headers


# =========================================================================
# Test 3: structlog correlation with request_id/trace_id
# =========================================================================


class TestLogCorrelation:
    """Verify the middleware performs structured logging.

    The app's structlog config uses ``wrap_for_formatter`` with
    ``cache_logger_on_first_use=True`` — structlog proxies are cached after
    the first request, and lifespan clears root handlers.  To avoid depending
    on the Python logging dispatch chain in tests, we patch the middleware's
    logger directly and verify the ``info()`` call contract.

    The *values* of structlog context vars (``request_id``, ``trace_id``,
    ``method``, ``path``) are validated by other tests in this class:
    - ``TestRequestIdPropagation`` verifies ``X-Request-ID`` response header
    - ``TestTraceIdPropagation`` verifies ``X-Trace-ID`` response header
    """

    async def test_middleware_logs_every_request(self, client: AsyncClient) -> None:
        """The middleware calls ``logger.info("http_request", ...)``."""
        from narrare._app import middleware as mw_module

        with patch.object(mw_module.logger, "info") as mock_info:
            response = await client.get("/health")

        assert response.status_code == 200
        mock_info.assert_called_once_with(
            "http_request",
            status=200,
            duration_ms=ANY,
        )

    async def test_logging_with_explicit_request_id(self, client: AsyncClient) -> None:
        """Logging works when ``X-Request-ID`` is provided."""
        from narrare._app import middleware as mw_module

        request_id = str(uuid.uuid4())

        with patch.object(mw_module.logger, "info") as mock_info:
            response = await client.get(
                "/health",
                headers={"X-Request-ID": request_id},
            )

        assert response.status_code == 200
        mock_info.assert_called_once_with(
            "http_request",
            status=200,
            duration_ms=ANY,
        )

    async def test_logging_with_otel_trace_context(self, client: AsyncClient) -> None:
        """Logging works when OTel trace context is present."""
        from narrare._app import middleware as mw_module

        with (
            patch.object(
                mw_module,
                "get_current_trace_context",
                return_value={
                    "x_trace_id": "ff" + "a" * 30,
                    "x_span_id": "bb" + "c" * 14,
                },
            ),
            patch.object(mw_module.logger, "info") as mock_info,
        ):
            response = await client.get("/health")

        assert response.status_code == 200
        mock_info.assert_called_once_with(
            "http_request",
            status=200,
            duration_ms=ANY,
        )

    async def test_middleware_logs_on_error_response(self, client: AsyncClient) -> None:
        """The middleware logs ``http_request`` even on 4xx responses.

        FastAPI's exception handler catches ``HTTPException`` before it
        reaches the middleware, so ``call_next`` returns an error response
        instead of raising — the middleware's ``try`` branch runs.
        """
        from narrare._app import middleware as mw_module

        with patch.object(mw_module.logger, "info") as mock_info:
            response = await client.post(
                "/api/v1/writing/chapters/00000000-0000-0000-0000-000000000000/extend",
                json={"text": "test", "context": ""},
            )

        # Auth failure (401) — middleware still logs via ``info``
        assert response.status_code == 401
        mock_info.assert_called_once_with(
            "http_request",
            status=401,
            duration_ms=ANY,
        )
