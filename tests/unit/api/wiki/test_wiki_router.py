"""Unit tests for WikiRouter — HTTP endpoint validation.

Tests the FastAPI router via httpx.AsyncClient with mocked service layer.
Validates status codes, response schemas, and error handling.
Follows the pattern from tests/unit/api/writing/test_summary_router.py.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from narrare._app.database import get_async_session
from narrare._app.dependencies import get_current_user_id
from narrare._app.main import create_app
from narrare.wiki.dependencies import get_wiki_service
from narrare.wiki.schemas import (
    WikiChapterSummaryResponse,
    WikiIndexResponse,
    WikiRefreshResponse,
    WikiSummaryListResponse,
    WikiSummaryResponse,
)

TEST_USER_ID = "00000000-0000-0000-0000-0000000000ff"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    """Create test app with overridden dependencies for unit testing."""
    application = create_app()

    # Override get_async_session to prevent DB connection attempts
    async def _mock_session():
        mock = AsyncMock()
        mock.execute = AsyncMock()
        yield mock

    # Override auth to bypass JWT validation
    async def _mock_auth() -> str:
        return TEST_USER_ID

    application.dependency_overrides[get_async_session] = _mock_session
    application.dependency_overrides[get_current_user_id] = _mock_auth
    return application


@pytest.fixture
async def client(app):
    """Async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uid() -> uuid.UUID:
    """Generate a random UUID."""
    return uuid.uuid4()


def _make_summary_response(
    novel_id: uuid.UUID | None = None,
    entity_id: uuid.UUID | None = None,
) -> WikiSummaryResponse:
    """Create a WikiSummaryResponse for testing."""
    now = datetime.now(UTC)
    return WikiSummaryResponse(
        id=_uid(),
        novel_id=novel_id or _uid(),
        entity_id=entity_id or _uid(),
        narrative_summary="A brave warrior who fights for justice.",
        role_in_story="Protagonist",
        key_attributes=["brave", "strong"],
        relationships=[],
        chapter_references=None,
        character_arc="Grows from farmer to hero.",
        status="fresh",
        version=1,
        generated_at=now,
        refreshed_at=None,
    )


def _make_chapter_summary_response(
    chapter_id: uuid.UUID | None = None,
) -> WikiChapterSummaryResponse:
    """Create a WikiChapterSummaryResponse for testing."""
    now = datetime.now(UTC)
    return WikiChapterSummaryResponse(
        id=_uid(),
        chapter_id=chapter_id or _uid(),
        narrative_summary="The hero enters the dark forest.",
        key_events=["Hero enters forest", "Finds ancient relic"],
        entities_involved=[],
        themes=["courage", "discovery"],
        emotional_arc="tense to triumphant",
        status="fresh",
        version=1,
        generated_at=now,
    )


def _mock_wiki_service() -> AsyncMock:
    """Create a mock APIWikiService with pre-configured async methods."""
    service = AsyncMock()
    service.get_summaries = AsyncMock()
    service.get_chapter_summary = AsyncMock()
    service.refresh_summary = AsyncMock()
    service.get_wiki_index = AsyncMock()
    service.mark_all_stale = AsyncMock()
    return service


# ---------------------------------------------------------------------------
# Tests: GET /novels/{novel_id}/wiki/summaries
# ---------------------------------------------------------------------------


class TestListSummaries:
    """Tests for GET /api/v1/novels/{novel_id}/wiki/summaries."""

    async def test_get_summaries_returns_list(self, app: Any, client: AsyncClient) -> None:
        """GET /novels/{id}/wiki/summaries returns 200 with list."""
        novel_id = _uid()
        mock_service = _mock_wiki_service()
        mock_service.get_summaries.return_value = WikiSummaryListResponse(
            items=[_make_summary_response(novel_id=novel_id)],
            total=1,
        )
        app.dependency_overrides[get_wiki_service] = lambda: mock_service

        response = await client.get(f"/api/v1/novels/{novel_id}/wiki/summaries")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["narrative_summary"] == "A brave warrior who fights for justice."

    async def test_get_summaries_filtered_by_entity_ids(
        self, app: Any, client: AsyncClient
    ) -> None:
        """GET with entity_ids query param passes parsed IDs to service."""
        novel_id = _uid()
        entity_a = _uid()
        entity_b = _uid()
        mock_service = _mock_wiki_service()
        mock_service.get_summaries.return_value = WikiSummaryListResponse(items=[], total=0)
        app.dependency_overrides[get_wiki_service] = lambda: mock_service

        response = await client.get(
            f"/api/v1/novels/{novel_id}/wiki/summaries",
            params={"entity_ids": f"{entity_a},{entity_b}"},
        )

        assert response.status_code == status.HTTP_200_OK
        mock_service.get_summaries.assert_called_once()
        call_args = mock_service.get_summaries.call_args
        # Verify entity_ids were parsed correctly (3rd positional arg)
        assert call_args[0][2] == [entity_a, entity_b]


# ---------------------------------------------------------------------------
# Tests: GET /novels/{novel_id}/wiki/summaries/{entity_id}
# ---------------------------------------------------------------------------


class TestGetSingleSummary:
    """Tests for GET /api/v1/novels/{novel_id}/wiki/summaries/{entity_id}."""

    async def test_get_single_summary_found(self, app: Any, client: AsyncClient) -> None:
        """GET existing summary returns 200."""
        novel_id = _uid()
        entity_id = _uid()
        summary = _make_summary_response(novel_id=novel_id, entity_id=entity_id)
        mock_service = _mock_wiki_service()
        mock_service.get_summaries.return_value = WikiSummaryListResponse(
            items=[summary],
            total=1,
        )
        app.dependency_overrides[get_wiki_service] = lambda: mock_service

        response = await client.get(f"/api/v1/novels/{novel_id}/wiki/summaries/{entity_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["narrative_summary"] == "A brave warrior who fights for justice."

    async def test_get_single_summary_not_found(self, app: Any, client: AsyncClient) -> None:
        """GET non-existent summary returns 404."""
        novel_id = _uid()
        entity_id = _uid()
        mock_service = _mock_wiki_service()
        mock_service.get_summaries.return_value = WikiSummaryListResponse(
            items=[],
            total=0,
        )
        app.dependency_overrides[get_wiki_service] = lambda: mock_service

        response = await client.get(f"/api/v1/novels/{novel_id}/wiki/summaries/{entity_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Tests: GET /novels/{novel_id}/wiki/chapters/{chapter_id}/summary
# ---------------------------------------------------------------------------


class TestGetChapterSummary:
    """Tests for GET /api/v1/novels/{novel_id}/wiki/chapters/{chapter_id}/summary."""

    async def test_get_chapter_summary_found(self, app: Any, client: AsyncClient) -> None:
        """GET existing chapter summary returns 200."""
        novel_id = _uid()
        chapter_id = _uid()
        mock_service = _mock_wiki_service()
        mock_service.get_chapter_summary.return_value = _make_chapter_summary_response(
            chapter_id=chapter_id,
        )
        app.dependency_overrides[get_wiki_service] = lambda: mock_service

        response = await client.get(f"/api/v1/novels/{novel_id}/wiki/chapters/{chapter_id}/summary")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["narrative_summary"] == "The hero enters the dark forest."
        assert data["key_events"] == ["Hero enters forest", "Finds ancient relic"]

    async def test_get_chapter_summary_not_found(self, app: Any, client: AsyncClient) -> None:
        """GET non-existent chapter summary returns 404."""
        novel_id = _uid()
        chapter_id = _uid()
        mock_service = _mock_wiki_service()
        mock_service.get_chapter_summary.return_value = None
        app.dependency_overrides[get_wiki_service] = lambda: mock_service

        response = await client.get(f"/api/v1/novels/{novel_id}/wiki/chapters/{chapter_id}/summary")

        assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Tests: POST /novels/{novel_id}/wiki/summaries/{entity_id}/refresh
# ---------------------------------------------------------------------------


class TestRefreshSummary:
    """Tests for POST /api/v1/novels/{novel_id}/wiki/summaries/{entity_id}/refresh."""

    async def test_refresh_summary(self, app: Any, client: AsyncClient) -> None:
        """POST refresh returns 200 with refresh response."""
        novel_id = _uid()
        entity_id = _uid()
        summary_id = _uid()
        mock_service = _mock_wiki_service()
        mock_service.refresh_summary.return_value = WikiRefreshResponse(
            summary_id=summary_id,
            status="fresh",
            message="Summary refreshed successfully.",
        )
        app.dependency_overrides[get_wiki_service] = lambda: mock_service

        response = await client.post(
            f"/api/v1/novels/{novel_id}/wiki/summaries/{entity_id}/refresh",
            json={"force": False},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "fresh"
        assert data["message"] == "Summary refreshed successfully."
        mock_service.refresh_summary.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: GET /novels/{novel_id}/wiki/index
# ---------------------------------------------------------------------------


class TestGetWikiIndex:
    """Tests for GET /api/v1/novels/{novel_id}/wiki/index."""

    async def test_get_wiki_index(self, app: Any, client: AsyncClient) -> None:
        """GET wiki index returns 200 with counts."""
        novel_id = _uid()
        now = datetime.now(UTC)
        mock_service = _mock_wiki_service()
        mock_service.get_wiki_index.return_value = WikiIndexResponse(
            novel_id=novel_id,
            total_summaries=5,
            fresh_count=3,
            stale_count=1,
            pending_count=1,
            last_generated_at=now,
        )
        app.dependency_overrides[get_wiki_service] = lambda: mock_service

        response = await client.get(f"/api/v1/novels/{novel_id}/wiki/index")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_summaries"] == 5
        assert data["fresh_count"] == 3
        assert data["stale_count"] == 1
        assert data["pending_count"] == 1


# ---------------------------------------------------------------------------
# Tests: POST /novels/{novel_id}/wiki/mark-stale
# ---------------------------------------------------------------------------


class TestMarkStale:
    """Tests for POST /api/v1/novels/{novel_id}/wiki/mark-stale."""

    async def test_mark_stale(self, app: Any, client: AsyncClient) -> None:
        """POST mark-stale returns 200 with affected count."""
        novel_id = _uid()
        mock_service = _mock_wiki_service()
        mock_service.mark_all_stale.return_value = 3
        app.dependency_overrides[get_wiki_service] = lambda: mock_service

        response = await client.post(
            f"/api/v1/novels/{novel_id}/wiki/mark-stale",
            json={"prompt_version": "2.0.0"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["affected_count"] == 3


# ---------------------------------------------------------------------------
# Tests: Auth
# ---------------------------------------------------------------------------


class TestUnauthorized:
    """Tests for unauthorized access."""

    async def test_unauthorized_returns_401(self, client: AsyncClient) -> None:
        """No auth token returns 401."""
        novel_id = _uid()

        # Use a fresh client without auth override
        bare_app = create_app()

        async def _no_auth_session():
            mock = AsyncMock()
            mock.execute = AsyncMock()
            yield mock

        bare_app.dependency_overrides[get_async_session] = _no_auth_session

        async with AsyncClient(
            transport=ASGITransport(app=bare_app), base_url="http://test"
        ) as bare_client:
            response = await bare_client.get(f"/api/v1/novels/{novel_id}/wiki/summaries")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
