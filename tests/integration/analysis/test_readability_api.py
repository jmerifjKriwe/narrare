"""Integration tests for ANAL-003 Readability API endpoints.

Tests the full HTTP request/response cycle for:
- POST /api/v1/analysis/readability — auth required
- Empty chapter content (graceful degradation)
- Missing chapter (404)
- Auth requirements (401)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from narrare.analysis.dependencies import get_readability_service
from narrare.analysis.services.readability_service import ReadabilityService
from narrare_core.analysis.types import ReadabilityMetrics, ReadabilityResult

if TYPE_CHECKING:
    from fastapi import FastAPI
    from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_readability_result() -> ReadabilityResult:
    """Create a sample ReadabilityResult for test assertions."""
    return ReadabilityResult(
        metrics=ReadabilityMetrics(
            flesch_reading_ease=72.5,
            flesch_kincaid_grade=6.8,
            gunning_fog=8.2,
            avg_sentence_length=14.3,
            avg_syllables_per_word=1.4,
            complex_word_ratio=0.08,
            word_count=1500,
            sentence_count=105,
        ),
        genre_benchmarks={
            "young_adult": ReadabilityMetrics(
                flesch_reading_ease=70.0,
                flesch_kincaid_grade=7.0,
                gunning_fog=9.0,
                avg_sentence_length=15.0,
                avg_syllables_per_word=1.4,
                complex_word_ratio=0.08,
                word_count=0,
                sentence_count=0,
            ),
        },
        sentence_analyses=[],
        overall_assessment="The text is readable with clear prose.",
    )


@pytest.fixture
def mock_readability_service() -> MagicMock:
    """Create a mocked ReadabilityService for dependency override."""
    service = MagicMock(spec=ReadabilityService)
    service.analyze = AsyncMock(
        return_value=[_make_readability_result()],
    )
    return service


# ---------------------------------------------------------------------------
# POST /api/v1/analysis/readability
# ---------------------------------------------------------------------------


class TestReadabilityAnalysis:
    """Readability analysis endpoint."""

    async def test_readability_returns_200(
        self,
        app: FastAPI,
        client: AsyncClient,
        auth_headers: dict[str, str],
        mock_readability_service: MagicMock,
    ) -> None:
        """POST with valid params/body returns 200 with ReadabilityResult list."""
        app.dependency_overrides[get_readability_service] = lambda: mock_readability_service
        try:
            novel_id = uuid4()
            chapter_id = uuid4()

            resp = await client.post(
                "/api/v1/analysis/readability",
                params={"novel_id": str(novel_id)},
                json={"chapter_ids": [str(chapter_id)], "language": "en"},
                headers=auth_headers,
            )
        finally:
            # The app fixture is session-scoped — an override left behind
            # leaks into subsequent tests (order-dependent flakiness under
            # pytest-randomly). Same cleanup convention as
            # tests/integration/ai_assist/test_dialogue_coach_sse.py.
            app.dependency_overrides.pop(get_readability_service, None)

        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) == 1

        result = body[0]
        assert result["metrics"]["flesch_reading_ease"] == 72.5
        assert result["metrics"]["flesch_kincaid_grade"] == 6.8
        assert result["metrics"]["gunning_fog"] == 8.2
        assert result["metrics"]["word_count"] == 1500
        assert result["metrics"]["sentence_count"] == 105
        assert result["overall_assessment"] == "The text is readable with clear prose."
        assert result["sentence_analyses"] == []
        assert "young_adult" in result["genre_benchmarks"]

        mock_readability_service.analyze.assert_awaited_once()

    async def test_readability_empty_chapter(
        self,
        app: FastAPI,
        client: AsyncClient,
        auth_headers: dict[str, str],
        mock_readability_service: MagicMock,
    ) -> None:
        """Empty chapter returns minimal metrics (graceful degradation)."""
        empty_result = ReadabilityResult(
            metrics=ReadabilityMetrics(
                flesch_reading_ease=0.0,
                flesch_kincaid_grade=0.0,
                gunning_fog=0.0,
                avg_sentence_length=0.0,
                avg_syllables_per_word=0.0,
                complex_word_ratio=0.0,
                word_count=0,
                sentence_count=0,
            ),
            genre_benchmarks={},
            sentence_analyses=[],
            overall_assessment=None,
        )
        mock_readability_service.analyze = AsyncMock(return_value=[empty_result])

        app.dependency_overrides[get_readability_service] = lambda: mock_readability_service
        try:
            novel_id = uuid4()
            chapter_id = uuid4()

            resp = await client.post(
                "/api/v1/analysis/readability",
                params={"novel_id": str(novel_id)},
                json={"chapter_ids": [str(chapter_id)]},
                headers=auth_headers,
            )
        finally:
            # Session-scoped app — pop the override to prevent leakage into
            # subsequent tests (see test_readability_returns_200).
            app.dependency_overrides.pop(get_readability_service, None)

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["metrics"]["word_count"] == 0
        assert body[0]["overall_assessment"] is None

    async def test_readability_missing_chapter_returns_404(
        self,
        app: FastAPI,
        client: AsyncClient,
        auth_headers: dict[str, str],
        mock_readability_service: MagicMock,
    ) -> None:
        """Non-existent chapter returns 404."""
        from narrare_core.shared.errors import NotFoundError

        mock_readability_service.analyze = AsyncMock(
            side_effect=NotFoundError("Chapter", identifier=str(uuid4())),
        )

        app.dependency_overrides[get_readability_service] = lambda: mock_readability_service
        try:
            novel_id = uuid4()
            chapter_id = uuid4()

            resp = await client.post(
                "/api/v1/analysis/readability",
                params={"novel_id": str(novel_id)},
                json={"chapter_ids": [str(chapter_id)]},
                headers=auth_headers,
            )
        finally:
            # Session-scoped app — pop the override to prevent leakage into
            # subsequent tests (see test_readability_returns_200).
            app.dependency_overrides.pop(get_readability_service, None)

        assert resp.status_code == 404

    async def test_readability_unauthorized_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        """POST without auth headers returns 401."""
        resp = await client.post(
            "/api/v1/analysis/readability",
            params={"novel_id": str(uuid4())},
            json={"chapter_ids": [str(uuid4())]},
        )

        assert resp.status_code == 401

    async def test_readability_nonexistent_novel_with_invalid_body_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST readability with an invalid body returns 422 (real chain).

        Regression (ADR-086 S4a): the factory previously resolved the
        per-user routing cascade eagerly at DI-construction time. FastAPI
        solves all sub-dependencies BEFORE body validation, so the P2
        novel guard inside ``resolve()`` (404 for a nonexistent novel)
        preempted the legitimate 422 for the invalid body. With lazy
        first-use resolution (ADR-086) the body is validated first and
        the cascade (including the novel guard) runs only on first use.
        """
        resp = await client.post(
            "/api/v1/analysis/readability",
            params={"novel_id": str(uuid4())},
            json={"chapter_ids": []},
            headers=auth_headers,
        )

        assert resp.status_code == 422

    async def test_readability_returns_422_with_empty_chapter_ids(
        self,
        app: FastAPI,
        client: AsyncClient,
        auth_headers: dict[str, str],
        mock_readability_service: MagicMock,
    ) -> None:
        """POST with empty chapter_ids returns 422."""
        # Body validation happens before the service is invoked — pin the
        # dependency so the test exercises validation, not the routing
        # cascade (the real chain resolves the nonexistent novel first and
        # returns 404 before the 422 can be produced).
        app.dependency_overrides[get_readability_service] = lambda: mock_readability_service
        try:
            resp = await client.post(
                "/api/v1/analysis/readability",
                params={"novel_id": str(uuid4())},
                json={"chapter_ids": []},
                headers=auth_headers,
            )
        finally:
            app.dependency_overrides.pop(get_readability_service, None)

        assert resp.status_code == 422

    async def test_readability_returns_422_without_chapter_ids(
        self,
        app: FastAPI,
        client: AsyncClient,
        auth_headers: dict[str, str],
        mock_readability_service: MagicMock,
    ) -> None:
        """POST with missing chapter_ids returns 422."""
        # See test_readability_returns_422_with_empty_chapter_ids for rationale.
        app.dependency_overrides[get_readability_service] = lambda: mock_readability_service
        try:
            resp = await client.post(
                "/api/v1/analysis/readability",
                params={"novel_id": str(uuid4())},
                json={},
                headers=auth_headers,
            )
        finally:
            app.dependency_overrides.pop(get_readability_service, None)

        assert resp.status_code == 422

    async def test_readability_multiple_chapters(
        self,
        app: FastAPI,
        client: AsyncClient,
        auth_headers: dict[str, str],
        mock_readability_service: MagicMock,
    ) -> None:
        """POST with multiple chapter_ids returns one result per chapter."""
        mock_readability_service.analyze = AsyncMock(
            return_value=[_make_readability_result(), _make_readability_result()],
        )

        app.dependency_overrides[get_readability_service] = lambda: mock_readability_service
        try:
            novel_id = uuid4()
            chapter_ids = [str(uuid4()), str(uuid4())]

            resp = await client.post(
                "/api/v1/analysis/readability",
                params={"novel_id": str(novel_id)},
                json={"chapter_ids": chapter_ids},
                headers=auth_headers,
            )
        finally:
            # Session-scoped app — pop the override to prevent leakage into
            # subsequent tests (see test_readability_returns_200).
            app.dependency_overrides.pop(get_readability_service, None)

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
