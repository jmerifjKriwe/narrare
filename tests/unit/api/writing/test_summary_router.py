"""Unit tests for summary router — verifies HTTP status codes and error mapping.

Tests the thin delegation layer (RULE-06) ensuring routes delegate to
ChapterSummaryService and map errors correctly.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from narrare._app.database import get_async_session
from narrare._app.dependencies import get_current_user_id
from narrare._app.main import create_app
from narrare.writing.summary_contracts import SummaryResult as SummaryResultDataclass
from narrare.writing.summary_deps import get_summary_service

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
    async with AsyncClient(
        transport=transport, base_url="http://test", headers={"Origin": "http://localhost:3000"}
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_summary_service() -> AsyncMock:
    """Create a mock ChapterSummaryService with a pre-configured summarize."""
    service = AsyncMock()
    service.summarize = AsyncMock()
    return service


# ---------------------------------------------------------------------------
# Test summarization endpoint
# ---------------------------------------------------------------------------


class TestSummarizeChapter:
    """Tests for POST /api/v1/summary/chapters/{chapter_id}."""

    async def test_summarize_returns_200_with_valid_input(
        self,
        app,
        client: AsyncClient,
    ) -> None:
        """Happy path: valid chapter returns 200 with summary."""
        chapter_id = "00000000-0000-0000-0000-000000000001"
        novel_id = "00000000-0000-0000-0000-000000000002"

        mock_service = _mock_summary_service()
        mock_service.summarize.return_value = SummaryResultDataclass(
            summary="A test summary.",
            word_count=4,
            key_points=["Point 1"],
        )

        app.dependency_overrides[get_summary_service] = lambda: mock_service

        response = await client.post(
            f"/api/v1/summary/chapters/{chapter_id}",
            params={"novel_id": novel_id},
            json={"max_sentences": 3, "language": "en"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["summary"] == "A test summary."
        assert data["word_count"] == 4
        assert data["key_points"] == ["Point 1"]

    async def test_summarize_returns_404_when_chapter_not_found(
        self,
        app,
        client: AsyncClient,
    ) -> None:
        """Error: non-existent chapter returns 404."""
        from narrare_core.shared.errors import NotFoundError

        chapter_id = "00000000-0000-0000-0000-000000000001"
        novel_id = "00000000-0000-0000-0000-000000000002"

        mock_service = _mock_summary_service()
        mock_service.summarize.side_effect = NotFoundError("Chapter", identifier=chapter_id)

        app.dependency_overrides[get_summary_service] = lambda: mock_service

        response = await client.post(
            f"/api/v1/summary/chapters/{chapter_id}",
            params={"novel_id": novel_id},
            json={"max_sentences": 3, "language": "en"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_summarize_returns_500_when_service_fails(
        self,
        app,
        client: AsyncClient,
    ) -> None:
        """Error: LLM failure returns 500."""
        from narrare_core.shared.errors import WritingError

        chapter_id = "00000000-0000-0000-0000-000000000001"
        novel_id = "00000000-0000-0000-0000-000000000002"

        mock_service = _mock_summary_service()
        mock_service.summarize.side_effect = WritingError("LLM call failed")

        app.dependency_overrides[get_summary_service] = lambda: mock_service

        response = await client.post(
            f"/api/v1/summary/chapters/{chapter_id}",
            params={"novel_id": novel_id},
            json={"max_sentences": 3, "language": "en"},
        )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
