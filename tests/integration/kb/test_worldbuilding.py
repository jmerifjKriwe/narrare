"""Integration tests for Worldbuilding analysis API endpoints.

Tests POST /novels/{id}/kb/worldbuilding/analyze and
POST /novels/{id}/kb/worldbuilding/apply with mocked
WorldbuildingService via dependency_overrides.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from narrare.kb.worldbuilding_contracts import (
    WorldbuildingAnalysisResponse,
    WorldbuildingApplyResponse,
)
from narrare.kb.worldbuilding_service import WorldbuildingService

if TYPE_CHECKING:
    from collections.abc import Callable

    from fastapi import FastAPI
    from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_worldbuilding_service() -> MagicMock:
    """Create a mocked WorldbuildingService for dependency override."""
    service = MagicMock(spec=WorldbuildingService)

    # Default: analyze returns a valid response
    service.analyze = AsyncMock(
        return_value=WorldbuildingAnalysisResponse(
            novel_id=str(uuid4()),
            entity_count=10,
            gap_findings=[],
            connection_suggestions=[],
            consistency_issues=[],
            worldbuilding_score=0.75,
            overall_assessment="Good worldbuilding foundation",
            summary={
                "total_entities": 10,
                "gaps_found": 0,
                "connections_suggested": 0,
                "consistency_issues": 0,
                "entities_in_analysis": 10,
            },
            analyzed_at="2025-01-01T00:00:00Z",
        )
    )

    # Default: apply returns success
    service.apply_connections = AsyncMock(
        return_value=WorldbuildingApplyResponse(
            success=True,
            created_count=1,
            failed_count=0,
            errors=[],
        )
    )

    return service


# ---------------------------------------------------------------------------
# Tests: POST /worldbuilding/analyze
# ---------------------------------------------------------------------------


class TestAnalyzeEndpoint:
    """Test POST /novels/{id}/kb/worldbuilding/analyze."""

    async def test_analyze_endpoint_returns_200(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        mock_worldbuilding_service: MagicMock,
    ) -> None:
        """POST /analyze returns 200 with WorldbuildingAnalysisResponse schema."""
        from narrare.kb.dependencies import get_worldbuilding_service

        novel_id = uuid4()

        app.dependency_overrides[get_worldbuilding_service] = cast(
            "Callable[[], Any]", lambda: mock_worldbuilding_service
        )

        resp = await client.post(
            f"/api/v1/novels/{novel_id}/kb/worldbuilding/analyze",
            json={"include_gaps": True, "include_connections": True},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "gap_findings" in data
        assert "connection_suggestions" in data
        assert "consistency_issues" in data
        assert "worldbuilding_score" in data
        assert data["worldbuilding_score"] == 0.75

    async def test_analyze_endpoint_returns_401_without_auth(
        self,
        client: AsyncClient,
        app: FastAPI,
        mock_worldbuilding_service: MagicMock,
    ) -> None:
        """POST /analyze returns 401 when no auth token is provided."""
        from narrare.kb.dependencies import get_worldbuilding_service

        novel_id = uuid4()

        app.dependency_overrides[get_worldbuilding_service] = cast(
            "Callable[[], Any]", lambda: mock_worldbuilding_service
        )

        resp = await client.post(
            f"/api/v1/novels/{novel_id}/kb/worldbuilding/analyze",
            json={"include_gaps": True},
        )

        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Tests: POST /worldbuilding/apply
# ---------------------------------------------------------------------------


class TestApplyEndpoint:
    """Test POST /novels/{id}/kb/worldbuilding/apply."""

    async def test_apply_endpoint_returns_200(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        mock_worldbuilding_service: MagicMock,
    ) -> None:
        """POST /apply returns 200 with WorldbuildingApplyResponse schema."""
        from narrare.kb.dependencies import get_worldbuilding_service

        novel_id = uuid4()

        app.dependency_overrides[get_worldbuilding_service] = cast(
            "Callable[[], Any]", lambda: mock_worldbuilding_service
        )

        # The apply endpoint requires the analysis response body
        analysis_body = {
            "novel_id": str(novel_id),
            "entity_count": 5,
            "gap_findings": [],
            "connection_suggestions": [],
            "consistency_issues": [],
            "worldbuilding_score": 0.5,
            "overall_assessment": "Decent",
            "summary": {"total_entities": 5},
            "analyzed_at": "2025-01-01T00:00:00Z",
        }

        resp = await client.post(
            f"/api/v1/novels/{novel_id}/kb/worldbuilding/apply",
            json={
                "finding_indices": [0, 1],
                "analysis": analysis_body,
            },
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["created_count"] == 1
        assert data["failed_count"] == 0

    async def test_apply_endpoint_returns_401_without_auth(
        self,
        client: AsyncClient,
        app: FastAPI,
        mock_worldbuilding_service: MagicMock,
    ) -> None:
        """POST /apply returns 401 when no auth token is provided."""
        from narrare.kb.dependencies import get_worldbuilding_service

        novel_id = uuid4()

        app.dependency_overrides[get_worldbuilding_service] = cast(
            "Callable[[], Any]", lambda: mock_worldbuilding_service
        )

        resp = await client.post(
            f"/api/v1/novels/{novel_id}/kb/worldbuilding/apply",
            json={
                "finding_indices": [0],
                "analysis": {
                    "novel_id": str(novel_id),
                    "entity_count": 0,
                    "gap_findings": [],
                    "connection_suggestions": [],
                    "consistency_issues": [],
                    "worldbuilding_score": 0.0,
                    "overall_assessment": "",
                    "summary": {},
                    "analyzed_at": "2025-01-01T00:00:00Z",
                },
            },
        )

        assert resp.status_code == 401

    async def test_apply_endpoint_returns_422_with_invalid_body(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        mock_worldbuilding_service: MagicMock,
    ) -> None:
        """POST /apply returns 422 when body is malformed."""
        from narrare.kb.dependencies import get_worldbuilding_service

        novel_id = uuid4()

        app.dependency_overrides[get_worldbuilding_service] = cast(
            "Callable[[], Any]", lambda: mock_worldbuilding_service
        )

        # Missing analysis field
        resp = await client.post(
            f"/api/v1/novels/{novel_id}/kb/worldbuilding/apply",
            json={"finding_indices": [0]},
            headers=auth_headers,
        )

        assert resp.status_code == 422
