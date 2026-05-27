"""Integration tests for analysis beta reader API endpoints.

Tests the full HTTP request/response cycle for:
- POST /api/v1/analysis/beta-reader — auth required
- POST /api/v1/analysis/beta-reader/deep-dive — auth required
- Validation errors with auth (422)
- Auth requirements (401)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from narrare.analysis.beta_reader_service import BetaReaderService
from narrare.analysis.contracts import FeedbackCategory
from narrare.analysis.dependencies import get_beta_reader_service
from narrare.analysis.schemas import (
    BetaReaderDeepDiveResponse,
    BetaReaderOverallAssessment,
    BetaReaderResponse,
)

if TYPE_CHECKING:
    from fastapi import FastAPI
    from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_beta_reader_service() -> MagicMock:
    """Create a mocked BetaReaderService for dependency override."""
    service = MagicMock(spec=BetaReaderService)
    service.analyze = AsyncMock(
        return_value=BetaReaderResponse(
            novel_id=str(uuid4()),
            chapter_ids=[str(uuid4())],
            total_word_count=1500,
            strengths=[],
            feedback=[],
            questions=[],
            overall=BetaReaderOverallAssessment(
                summary="Good chapter overall.",
                reader_engagement=7,
                emotional_impact=6,
                pacing_score=8,
                prose_quality=7,
                plot_progression=6,
                character_development=5,
            ),
            analyzed_at="2025-01-01T00:00:00Z",
            cache_key="test-cache-key-123",
        )
    )
    service.deep_dive = AsyncMock(
        return_value=BetaReaderDeepDiveResponse(
            novel_id=str(uuid4()),
            category=FeedbackCategory.PLOT,
            detailed_feedback=[],
            revision_suggestions=["Consider slowing down the opening."],
            category_score=7,
            analyzed_at="2025-01-01T00:00:00Z",
        )
    )
    return service


# ---------------------------------------------------------------------------
# POST /api/v1/analysis/beta-reader
# ---------------------------------------------------------------------------


class TestBetaReaderAnalyze:
    """Beta reader analysis endpoint."""

    async def test_analyze_returns_200_with_response(
        self,
        app: FastAPI,
        client: AsyncClient,
        auth_headers: dict[str, str],
        mock_beta_reader_service: MagicMock,
    ) -> None:
        """POST with valid params/body returns 200 with BetaReaderResponse."""
        app.dependency_overrides[get_beta_reader_service] = lambda: mock_beta_reader_service

        novel_id = uuid4()
        chapter_id = str(uuid4())

        resp = await client.post(
            "/api/v1/analysis/beta-reader",
            params={"novel_id": str(novel_id)},
            json={"chapter_ids": [chapter_id]},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["total_word_count"] == 1500
        assert body["strengths"] == []
        assert body["feedback"] == []
        assert body["questions"] == []
        assert body["overall"]["summary"] == "Good chapter overall."
        assert body["overall"]["reader_engagement"] == 7
        assert body["overall"]["emotional_impact"] == 6
        assert body["overall"]["pacing_score"] == 8
        assert body["overall"]["prose_quality"] == 7
        assert body["overall"]["plot_progression"] == 6
        assert body["overall"]["character_development"] == 5
        assert body["analyzed_at"] == "2025-01-01T00:00:00Z"
        assert body["cache_key"] == "test-cache-key-123"

        mock_beta_reader_service.analyze.assert_awaited_once()

    async def test_analyze_returns_401_without_auth(
        self,
        client: AsyncClient,
    ) -> None:
        """POST without auth headers returns 401."""
        resp = await client.post(
            "/api/v1/analysis/beta-reader",
            params={"novel_id": str(uuid4())},
            json={"chapter_ids": [str(uuid4())]},
        )

        assert resp.status_code == 401

    async def test_analyze_returns_422_with_empty_chapter_ids(
        self,
        app: FastAPI,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST with empty chapter_ids returns 422."""
        resp = await client.post(
            "/api/v1/analysis/beta-reader",
            params={"novel_id": str(uuid4())},
            json={"chapter_ids": []},
            headers=auth_headers,
        )

        assert resp.status_code == 422

    async def test_analyze_returns_422_without_chapter_ids(
        self,
        app: FastAPI,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST with missing chapter_ids returns 422."""
        resp = await client.post(
            "/api/v1/analysis/beta-reader",
            params={"novel_id": str(uuid4())},
            json={},
            headers=auth_headers,
        )

        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/v1/analysis/beta-reader/deep-dive
# ---------------------------------------------------------------------------


class TestBetaReaderDeepDive:
    """Beta reader deep-dive endpoint."""

    async def test_deep_dive_returns_200(
        self,
        app: FastAPI,
        client: AsyncClient,
        auth_headers: dict[str, str],
        mock_beta_reader_service: MagicMock,
    ) -> None:
        """POST with valid params/body returns 200 with BetaReaderDeepDiveResponse."""
        app.dependency_overrides[get_beta_reader_service] = lambda: mock_beta_reader_service

        novel_id = uuid4()
        chapter_id = str(uuid4())

        resp = await client.post(
            "/api/v1/analysis/beta-reader/deep-dive",
            params={"novel_id": str(novel_id)},
            json={
                "chapter_ids": [chapter_id],
                "category": "plot",
                "cache_key": "test-cache-key-123",
            },
            headers=auth_headers,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["category"] == "plot"
        assert body["detailed_feedback"] == []
        assert body["revision_suggestions"] == ["Consider slowing down the opening."]
        assert body["category_score"] == 7
        assert body["analyzed_at"] == "2025-01-01T00:00:00Z"

        mock_beta_reader_service.deep_dive.assert_awaited_once()

    async def test_deep_dive_returns_401_without_auth(
        self,
        client: AsyncClient,
    ) -> None:
        """POST without auth headers returns 401."""
        resp = await client.post(
            "/api/v1/analysis/beta-reader/deep-dive",
            params={"novel_id": str(uuid4())},
            json={
                "chapter_ids": [str(uuid4())],
                "category": "plot",
                "cache_key": "test-cache-key-123",
            },
        )

        assert resp.status_code == 401

    async def test_deep_dive_returns_422_without_cache_key(
        self,
        app: FastAPI,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST without cache_key returns 422."""
        resp = await client.post(
            "/api/v1/analysis/beta-reader/deep-dive",
            params={"novel_id": str(uuid4())},
            json={
                "chapter_ids": [str(uuid4())],
                "category": "plot",
            },
            headers=auth_headers,
        )

        assert resp.status_code == 422

    async def test_deep_dive_returns_422_with_empty_chapter_ids(
        self,
        app: FastAPI,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST with empty chapter_ids returns 422."""
        resp = await client.post(
            "/api/v1/analysis/beta-reader/deep-dive",
            params={"novel_id": str(uuid4())},
            json={
                "chapter_ids": [],
                "category": "plot",
                "cache_key": "test-cache-key-123",
            },
            headers=auth_headers,
        )

        assert resp.status_code == 422
