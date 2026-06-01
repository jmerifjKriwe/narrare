"""Integration tests for ANAL-004 POV Analysis API endpoints.

Tests the full HTTP request/response cycle for:
- POST /api/v1/analysis/pov — auth required
- POV type hint parameter
- Missing chapter (404)
- Auth requirements (401)
- Invalid request body (422)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from narrare.analysis.dependencies import get_pov_service
from narrare.analysis.services.pov_service import POVService
from narrare_core.analysis.types import (
    POVIssue,
    POVIssueType,
    POVResult,
    POVScene,
)

if TYPE_CHECKING:
    from fastapi import FastAPI
    from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_pov_result() -> POVResult:
    """Create a sample POVResult for test assertions."""
    return POVResult(
        scenes=[
            POVScene(
                scene_index=0,
                start_position=0,
                end_position=500,
                pov_character="Alice",
                confidence=0.92,
            ),
        ],
        issues=[
            POVIssue(
                type=POVIssueType.HEAD_HOP,
                location="Paragraph 3",
                text="Bob felt a cold dread...",
                explanation="Switched to Bob's internal state while in Alice's POV.",
                suggestion="Rephrase as observed behaviour: 'Bob went pale.'",
                severity="warning",
            ),
        ],
        pov_distribution={"Alice": 0.85, "Bob": 0.15},
        switch_count=1,
        analysis_type="third_limited",
    )


@pytest.fixture
def mock_pov_service() -> MagicMock:
    """Create a mocked POVService for dependency override."""
    service = MagicMock(spec=POVService)
    service.analyze = AsyncMock(
        return_value=_make_pov_result(),
    )
    return service


# ---------------------------------------------------------------------------
# POST /api/v1/analysis/pov
# ---------------------------------------------------------------------------


class TestPOVAnalysis:
    """POV analysis endpoint."""

    async def test_pov_returns_200(
        self,
        app: FastAPI,
        client: AsyncClient,
        auth_headers: dict[str, str],
        mock_pov_service: MagicMock,
    ) -> None:
        """POST with valid params/body returns 200 with POVResult."""
        app.dependency_overrides[get_pov_service] = lambda: mock_pov_service

        novel_id = uuid4()
        chapter_id = uuid4()

        resp = await client.post(
            "/api/v1/analysis/pov",
            params={"novel_id": str(novel_id)},
            json={"chapter_ids": [str(chapter_id)], "language": "en"},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        body = resp.json()

        assert "scenes" in body
        assert "issues" in body
        assert body["analysis_type"] == "third_limited"
        assert body["switch_count"] == 1
        assert body["pov_distribution"]["Alice"] == 0.85

        assert len(body["scenes"]) == 1
        scene = body["scenes"][0]
        assert scene["scene_index"] == 0
        assert scene["pov_character"] == "Alice"
        assert scene["confidence"] == 0.92

        assert len(body["issues"]) == 1
        issue = body["issues"][0]
        assert issue["type"] == "head_hop"
        assert issue["severity"] == "warning"

        mock_pov_service.analyze.assert_awaited_once()

    async def test_pov_with_type_hint(
        self,
        app: FastAPI,
        client: AsyncClient,
        auth_headers: dict[str, str],
        mock_pov_service: MagicMock,
    ) -> None:
        """POST with pov_type hint passes it through to service."""
        app.dependency_overrides[get_pov_service] = lambda: mock_pov_service

        novel_id = uuid4()
        chapter_id = uuid4()

        resp = await client.post(
            "/api/v1/analysis/pov",
            params={"novel_id": str(novel_id)},
            json={
                "chapter_ids": [str(chapter_id)],
                "language": "en",
                "pov_type": "first_person",
            },
            headers=auth_headers,
        )

        assert resp.status_code == 200

        # Verify pov_type was passed to the service
        call_kwargs = mock_pov_service.analyze.call_args
        assert call_kwargs.kwargs["pov_type"] == "first_person"

    async def test_pov_missing_chapter_returns_404(
        self,
        app: FastAPI,
        client: AsyncClient,
        auth_headers: dict[str, str],
        mock_pov_service: MagicMock,
    ) -> None:
        """Non-existent chapter returns 404."""
        from narrare_core.shared.errors import NotFoundError

        mock_pov_service.analyze = AsyncMock(
            side_effect=NotFoundError("Chapter", identifier=str(uuid4())),
        )

        app.dependency_overrides[get_pov_service] = lambda: mock_pov_service

        novel_id = uuid4()
        chapter_id = uuid4()

        resp = await client.post(
            "/api/v1/analysis/pov",
            params={"novel_id": str(novel_id)},
            json={"chapter_ids": [str(chapter_id)]},
            headers=auth_headers,
        )

        assert resp.status_code == 404

    async def test_pov_unauthorized_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        """POST without auth headers returns 401."""
        resp = await client.post(
            "/api/v1/analysis/pov",
            params={"novel_id": str(uuid4())},
            json={"chapter_ids": [str(uuid4())]},
        )

        assert resp.status_code == 401

    async def test_pov_invalid_request_returns_422(
        self,
        app: FastAPI,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST with empty chapter_ids returns 422."""
        resp = await client.post(
            "/api/v1/analysis/pov",
            params={"novel_id": str(uuid4())},
            json={"chapter_ids": []},
            headers=auth_headers,
        )

        assert resp.status_code == 422

    async def test_pov_returns_422_without_chapter_ids(
        self,
        app: FastAPI,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST with missing chapter_ids returns 422."""
        resp = await client.post(
            "/api/v1/analysis/pov",
            params={"novel_id": str(uuid4())},
            json={},
            headers=auth_headers,
        )

        assert resp.status_code == 422

    async def test_pov_multiple_chapters(
        self,
        app: FastAPI,
        client: AsyncClient,
        auth_headers: dict[str, str],
        mock_pov_service: MagicMock,
    ) -> None:
        """POST with multiple chapter_ids — service receives all IDs."""
        app.dependency_overrides[get_pov_service] = lambda: mock_pov_service

        novel_id = uuid4()
        chapter_ids = [str(uuid4()), str(uuid4()), str(uuid4())]

        resp = await client.post(
            "/api/v1/analysis/pov",
            params={"novel_id": str(novel_id)},
            json={"chapter_ids": chapter_ids},
            headers=auth_headers,
        )

        assert resp.status_code == 200

        # Verify all chapter_ids were passed to service
        call_kwargs = mock_pov_service.analyze.call_args
        assert len(call_kwargs.kwargs["chapter_ids"]) == 3
