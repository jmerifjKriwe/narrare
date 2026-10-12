"""Audit B03 regression — CONS-001 router is registered on the app.

``narrare/consistency/router.py`` ships POST /consistency/check and
POST /consistency/check/stream (ADR-044 Slice 4, CONS-001 feature doc)
but was never included in ``create_app`` — the editor ConsistencyPanel
got 404 on every check (auto-run + Retry loop).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from narrare.consistency.deps import get_consistency_service
from narrare.consistency.schemas import ConsistencyResponse
from narrare.consistency.stage_schemas import ConsistencyStageEvent

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from fastapi import FastAPI
    from httpx import AsyncClient


class _FakeCheckerService:
    """Duck-typed ConsistencyCheckerService for route-level wiring tests."""

    async def ensure_resolved(self) -> None:
        return None

    async def check(self, *, novel_id: UUID, user_id: UUID, request: object) -> ConsistencyResponse:
        return ConsistencyResponse(
            novel_id=novel_id,
            chapter_ids=[],
            check_types=[],
            issues=[],
            overall_assessment="Consistent",
            analyzed_at="2026-10-12T00:00:00Z",
        )

    async def stream_check(
        self, *, novel_id: UUID, user_id: UUID, request: object
    ) -> AsyncIterator[ConsistencyStageEvent | ConsistencyResponse]:
        yield ConsistencyStageEvent(
            stage="extracting_facts", status="start", message="Extracting facts"
        )
        yield ConsistencyResponse(
            novel_id=novel_id,
            chapter_ids=[],
            check_types=[],
            issues=[],
            overall_assessment="Consistent",
            analyzed_at="2026-10-12T00:00:00Z",
        )


def test_consistency_routes_registered() -> None:
    from narrare._app.main import create_app

    app = create_app(test_mode=True)
    # FastAPI ≥0.129 wraps included routers as lazy ``_IncludedRouter``
    # objects, so flat ``app.routes`` enumeration no longer lists included
    # paths (see tests/unit/api/test_analytics_wiring.py). The OpenAPI
    # schema is the public, version-stable surface for the same assertion.
    paths = set(app.openapi()["paths"])
    assert "/api/v1/consistency/check" in paths
    assert "/api/v1/consistency/check/stream" in paths


class TestConsistencyEndpointsReachable:
    async def test_stream_check_returns_sse(
        self,
        app: FastAPI,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        app.dependency_overrides[get_consistency_service] = lambda: _FakeCheckerService()
        try:
            resp = await client.post(
                f"/api/v1/consistency/check/stream?novel_id={uuid4()}",
                json={},
                headers=auth_headers,
            )
        finally:
            app.dependency_overrides.pop(get_consistency_service, None)

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        assert '"type": "stage"' in resp.text
        assert '"type": "result"' in resp.text
        assert "[DONE]" in resp.text

    async def test_check_returns_json(
        self,
        app: FastAPI,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        app.dependency_overrides[get_consistency_service] = lambda: _FakeCheckerService()
        try:
            resp = await client.post(
                f"/api/v1/consistency/check?novel_id={uuid4()}",
                json={},
                headers=auth_headers,
            )
        finally:
            app.dependency_overrides.pop(get_consistency_service, None)

        assert resp.status_code == 200
        assert resp.json()["overall_assessment"] == "Consistent"
