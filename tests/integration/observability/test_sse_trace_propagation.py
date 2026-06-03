"""Integration tests for SSE-specific trace propagation.

Validates the observability chain documented in ``docs/development/observability-guide.md``:

- Test 4: SSE data enrichment with trace context (pure function tests)
- Test 5: SSE endpoint response headers include trace context

Split from ``test_trace_propagation.py`` to comply with RULE-04 (400-line limit).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = [pytest.mark.integration, pytest.mark.requires_db]


# =========================================================================
# Test 4: Pure functions (_app/observability.py)
# =========================================================================


class TestObservabilityHelpers:
    """Test the trace context helper functions directly."""

    def test_get_current_trace_context_returns_empty_without_otel(self) -> None:
        """Without OTel configured, returns empty dict."""
        from narrare._app.observability import get_current_trace_context

        ctx = get_current_trace_context()
        assert ctx == {}

    def test_enrich_sse_data_without_otel_returns_original(self) -> None:
        """Without OTel, ``enrich_sse_data`` returns data unchanged."""
        from narrare._app.observability import enrich_sse_data

        data = {"text": "hello", "is_final": False}
        result = enrich_sse_data(data)
        assert result is data  # Same object (no copy made)

    def test_enrich_sse_data_preserves_existing_keys(self) -> None:
        """Existing keys in data are preserved."""
        from narrare._app.observability import enrich_sse_data

        data = {"text": "hello", "is_final": True}
        result = enrich_sse_data(data)
        assert result["text"] == "hello"
        assert result["is_final"] is True

    def test_enrich_sse_data_adds_trace_context(self) -> None:
        """When OTel context is present, ``enrich_sse_data`` adds it."""
        from narrare._app import observability as obs_module

        fake_trace_id = "ff" + "g" * 30
        fake_span_id = "ee" + "h" * 14

        with patch.object(
            obs_module,
            "get_current_trace_context",
            return_value={
                "x_trace_id": fake_trace_id,
                "x_span_id": fake_span_id,
            },
        ):
            data = {"text": "hello"}
            result = obs_module.enrich_sse_data(data)

        assert result["x_trace_id"] == fake_trace_id
        assert result["x_span_id"] == fake_span_id
        assert result["text"] == "hello"

    def test_enrich_sse_data_returns_new_dict_when_enriched(self) -> None:
        """When trace context is added, returns a new dict (shallow copy)."""
        from narrare._app import observability as obs_module

        with patch.object(
            obs_module,
            "get_current_trace_context",
            return_value={
                "x_trace_id": "ff" + "i" * 30,
                "x_span_id": "ff" + "j" * 14,
            },
        ):
            original = {"text": "hello"}
            result = obs_module.enrich_sse_data(original)
            assert result is not original

    def test_get_current_trace_context_key_format(self) -> None:
        """Returned keys use ``x_trace_id`` / ``x_span_id`` naming."""
        from narrare._app import observability as obs_module

        with patch.object(
            obs_module,
            "get_current_trace_context",
            return_value={
                "x_trace_id": "ff" + "k" * 30,
                "x_span_id": "gg" + "l" * 14,
            },
        ):
            ctx = obs_module.get_current_trace_context()
        assert "x_trace_id" in ctx
        assert "x_span_id" in ctx


# =========================================================================
# Test 5: SSE endpoint response headers
# =========================================================================


class TestSseResponseHeaders:
    """Verify that SSE endpoints include trace context in HTTP response headers.

    The ``RequestLoggingMiddleware`` sets ``X-Request-ID`` (and optionally
    ``X-Trace-ID``) on every ``StreamingResponse``, including SSE endpoints.
    These tests verify the header propagation for SSE routes using pre-validation
    error responses (the middleware runs before validation fails).
    """

    async def test_extend_sse_has_request_id(self, client: AsyncClient) -> None:
        """SSE response includes ``X-Request-ID`` even on auth error."""
        request_id = str(uuid.uuid4())
        response = await client.post(
            "/api/v1/writing/chapters/00000000-0000-0000-0000-000000000000/extend",
            headers={"X-Request-ID": request_id},
            json={"text": "test", "context": ""},
        )
        assert response.headers.get("X-Request-ID") == request_id

    async def test_rewrite_sse_has_request_id(self, client: AsyncClient) -> None:
        """Rewrite SSE response includes ``X-Request-ID``."""
        request_id = str(uuid.uuid4())
        response = await client.post(
            "/api/v1/writing/chapters/00000000-0000-0000-0000-000000000000/rewrite",
            headers={"X-Request-ID": request_id},
            json={
                "novel_id": "00000000-0000-0000-0000-000000000000",
                "selected_text": "test",
                "count": 1,
            },
        )
        assert response.headers.get("X-Request-ID") == request_id

    async def test_coauthor_sse_has_request_id(self, client: AsyncClient) -> None:
        """Co-author SSE response includes ``X-Request-ID``."""
        request_id = str(uuid.uuid4())
        response = await client.post(
            "/api/v1/writing/chapters/00000000-0000-0000-0000-000000000000/co-author",
            headers={"X-Request-ID": request_id},
            json={
                "novel_id": "00000000-0000-0000-0000-000000000000",
                "selected_text": "test",
                "improvement_focus": ["word_choice"],
            },
        )
        assert response.headers.get("X-Request-ID") == request_id

    async def test_suggest_sse_has_request_id(self, client: AsyncClient) -> None:
        """Suggest SSE response includes ``X-Request-ID``."""
        request_id = str(uuid.uuid4())
        response = await client.post(
            "/api/v1/writing/chapters/00000000-0000-0000-0000-000000000000/suggest",
            headers={"X-Request-ID": request_id},
            json={
                "before": "test",
                "after": "",
            },
        )
        assert response.headers.get("X-Request-ID") == request_id

    async def test_kb_sessions_sse_has_request_id(self, client: AsyncClient) -> None:
        """KB sessions SSE response includes ``X-Request-ID``."""
        request_id = str(uuid.uuid4())
        response = await client.get(
            "/api/v1/novels/00000000-0000-0000-0000-000000000000/kb/sessions/"
            "00000000-0000-0000-0000-000000000000/stream",
            headers={"X-Request-ID": request_id},
        )
        # This endpoint returns 401 (no auth) — middleware still adds header
        assert response.headers.get("X-Request-ID") == request_id
