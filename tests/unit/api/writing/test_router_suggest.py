"""Unit tests for suggest router — inline ghost text suggestion SSE endpoint.

Tests the thin delegation layer (RULE-06) ensuring routes delegate to
SuggestService and map errors correctly.

InlineSuggestRequest schema requires: text_before (min 1).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from narrare._app.database import get_async_session
from narrare._app.dependencies import get_current_user_id
from narrare._app.main import create_app
from narrare._app.rate_limits import AI_WRITE_LIMITER

TEST_USER_ID = "00000000-0000-0000-0000-0000000000ff"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    """Create test app with overridden dependencies for unit testing."""
    application = create_app()

    async def _mock_session():
        mock = AsyncMock()
        mock.execute = AsyncMock()
        yield mock

    async def _mock_auth() -> str:
        return TEST_USER_ID

    application.dependency_overrides[get_async_session] = _mock_session
    application.dependency_overrides[get_current_user_id] = _mock_auth
    application.dependency_overrides[AI_WRITE_LIMITER] = lambda: None
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


@pytest.fixture
def chapter_id() -> UUID:
    return uuid4()


@pytest.fixture
def novel_id() -> UUID:
    return uuid4()


def _mock_suggest_service() -> AsyncMock:
    """Create a mock SuggestService with pre-configured methods."""
    from narrare.writing.suggest_service import InlineSuggestService

    service = AsyncMock()
    service.validate_suggest = AsyncMock()
    service.suggest_inline = MagicMock(spec=InlineSuggestService)
    return service


# ---------------------------------------------------------------------------
# Suggest (SSE)
# ---------------------------------------------------------------------------


class TestSuggest:
    """Tests for POST /api/v1/writing/chapters/{chapter_id}/suggest (SSE)."""

    async def test_suggest_returns_200_with_valid_input(
        self,
        app,
        client: AsyncClient,
        chapter_id: UUID,
        novel_id: UUID,
    ) -> None:
        """Happy path: valid suggest request returns 200 with SSE stream."""

        async def _stream():
            chunk = MagicMock(spec=["text", "is_final", "context_meta", "usage"])
            chunk.text = '\\boxed{"suggestion text"}'
            chunk.is_final = True
            chunk.context_meta = None
            chunk.usage = None
            yield chunk

        mock_service = _mock_suggest_service()
        mock_service.validate_suggest = AsyncMock()
        mock_service.suggest_inline.return_value = _stream()

        with patch("narrare.writing.router_suggest.get_suggest_service", return_value=mock_service):
            response = await client.post(
                f"/api/v1/writing/chapters/{chapter_id}/suggest",
                params={"novel_id": str(novel_id)},
                json={
                    "text_before": "The hero entered the dark forest, not knowing what lay ahead",
                },
            )

        assert response.status_code == status.HTTP_200_OK
        assert "text/event-stream" in response.headers.get("content-type", "")

        content = await response.aread()
        assert b"suggestion text" in content
        assert b"[DONE]" in content

    async def test_suggest_returns_422_with_missing_text_before(
        self,
        client: AsyncClient,
        chapter_id: UUID,
        novel_id: UUID,
    ) -> None:
        """Validation: missing text_before returns 422."""
        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/suggest",
            params={"novel_id": str(novel_id)},
            json={},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_suggest_returns_422_with_empty_text_before(
        self,
        client: AsyncClient,
        chapter_id: UUID,
        novel_id: UUID,
    ) -> None:
        """Validation: empty text_before returns 422."""
        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/suggest",
            params={"novel_id": str(novel_id)},
            json={"text_before": ""},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_suggest_returns_422_with_invalid_uuid(
        self,
        client: AsyncClient,
        novel_id: UUID,
    ) -> None:
        """Validation: non-UUID chapter_id returns 422."""
        response = await client.post(
            "/api/v1/writing/chapters/not-a-uuid/suggest",
            params={"novel_id": str(novel_id)},
            json={"text_before": "Some text before cursor"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_suggest_returns_404_when_validation_fails(
        self,
        app,
        client: AsyncClient,
        chapter_id: UUID,
        novel_id: UUID,
    ) -> None:
        """Error: non-existent chapter/novel returns 404."""
        from narrare_core.shared.errors import NotFoundError

        mock_service = _mock_suggest_service()
        mock_service.validate_suggest.side_effect = NotFoundError(
            "Chapter",
            identifier=str(chapter_id),
        )

        with patch("narrare.writing.router_suggest.get_suggest_service", return_value=mock_service):
            response = await client.post(
                f"/api/v1/writing/chapters/{chapter_id}/suggest",
                params={"novel_id": str(novel_id)},
                json={"text_before": "The hero walked into the dark forest"},
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_suggest_multiple_chunks_streamed(
        self,
        app,
        client: AsyncClient,
        chapter_id: UUID,
        novel_id: UUID,
    ) -> None:
        """SSE: suggest route streams text chunks and DONE signal."""

        async def _stream_with_chunks():
            chunk1 = MagicMock(spec=["text", "is_final", "context_meta", "usage"])
            chunk1.text = "first part"
            chunk1.is_final = False
            chunk1.usage = None
            yield chunk1

            chunk2 = MagicMock(spec=["text", "is_final", "context_meta", "usage"])
            chunk2.text = "second part"
            chunk2.is_final = True
            chunk2.usage = None
            yield chunk2

        mock_service = _mock_suggest_service()
        mock_service.validate_suggest = AsyncMock()
        mock_service.suggest_inline.return_value = _stream_with_chunks()

        with patch("narrare.writing.router_suggest.get_suggest_service", return_value=mock_service):
            response = await client.post(
                f"/api/v1/writing/chapters/{chapter_id}/suggest",
                params={"novel_id": str(novel_id)},
                json={"text_before": "The hero walked into the dark forest"},
            )

        assert response.status_code == status.HTTP_200_OK

        content = await response.aread()
        assert b"first part" in content
        assert b"second part" in content
        assert b"is_final" in content
        assert b"[DONE]" in content
