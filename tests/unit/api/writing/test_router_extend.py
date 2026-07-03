"""Unit tests for extend router — chapter extension SSE endpoint.

Tests the thin delegation layer (RULE-06) ensuring routes delegate to
ExtendService and map errors correctly.
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


def _mock_extend_service() -> AsyncMock:
    """Create a mock ExtendService with pre-configured methods."""
    from narrare.writing.extend_service import ExtendService

    service = AsyncMock()
    service.validate_extend = AsyncMock()
    service.stream_extend = MagicMock(spec=ExtendService)
    return service


# ---------------------------------------------------------------------------
# Extend (SSE)
# ---------------------------------------------------------------------------


class TestExtendChapter:
    """Tests for POST /api/v1/writing/chapters/{chapter_id}/extend (SSE)."""

    async def test_extend_returns_200_with_valid_input(
        self,
        app,
        client: AsyncClient,
        chapter_id: UUID,
        novel_id: UUID,
    ) -> None:
        """Happy path: valid extend request returns 200 with SSE stream."""

        async def _stream():
            chunk = MagicMock(spec=["text", "is_final", "context_meta", "usage"])
            chunk.text = "continuation text"
            chunk.is_final = True
            chunk.context_meta = None
            chunk.usage = None
            yield chunk

        mock_service = _mock_extend_service()
        mock_service.validate_extend = AsyncMock()
        mock_service.stream_extend.return_value = _stream()

        with patch("narrare.writing.router_extend.get_extend_service", return_value=mock_service):
            response = await client.post(
                f"/api/v1/writing/chapters/{chapter_id}/extend",
                params={"novel_id": str(novel_id)},
                json={"text_before": "The sun was setting over the horizon as"},
            )

        assert response.status_code == status.HTTP_200_OK
        assert "text/event-stream" in response.headers.get("content-type", "")

        content = await response.aread()
        assert b"continuation text" in content
        assert b"[DONE]" in content

    async def test_extend_returns_422_with_missing_text_before(
        self,
        client: AsyncClient,
        chapter_id: UUID,
        novel_id: UUID,
    ) -> None:
        """Validation: missing text_before returns 422."""
        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/extend",
            params={"novel_id": str(novel_id)},
            json={},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_extend_returns_422_with_invalid_uuid(
        self,
        client: AsyncClient,
        novel_id: UUID,
    ) -> None:
        """Validation: non-UUID chapter_id returns 422."""
        response = await client.post(
            "/api/v1/writing/chapters/not-a-uuid/extend",
            params={"novel_id": str(novel_id)},
            json={"text_before": "Some text before cursor"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_extend_returns_404_when_validation_fails(
        self,
        app,
        client: AsyncClient,
        chapter_id: UUID,
        novel_id: UUID,
    ) -> None:
        """Error: non-existent chapter/novel returns 404."""
        from narrare_core.shared.errors import NotFoundError

        mock_service = _mock_extend_service()
        mock_service.validate_extend.side_effect = NotFoundError(
            "Chapter",
            identifier=str(chapter_id),
        )

        with patch("narrare.writing.router_extend.get_extend_service", return_value=mock_service):
            response = await client.post(
                f"/api/v1/writing/chapters/{chapter_id}/extend",
                params={"novel_id": str(novel_id)},
                json={"text_before": "The sun was setting"},
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_extend_returns_409_on_conflict(
        self,
        app,
        client: AsyncClient,
        chapter_id: UUID,
        novel_id: UUID,
    ) -> None:
        """Error: concurrent edit conflict returns 409."""
        from narrare_core.shared.errors import ConflictError

        mock_service = _mock_extend_service()
        mock_service.validate_extend.side_effect = ConflictError(
            "Chapter has been modified since last read",
        )

        with patch("narrare.writing.router_extend.get_extend_service", return_value=mock_service):
            response = await client.post(
                f"/api/v1/writing/chapters/{chapter_id}/extend",
                params={"novel_id": str(novel_id)},
                json={"text_before": "The sun was setting"},
            )

        assert response.status_code == status.HTTP_409_CONFLICT

    async def test_extend_context_meta_event(
        self,
        app,
        client: AsyncClient,
        chapter_id: UUID,
        novel_id: UUID,
    ) -> None:
        """SSE: first event can be context_meta (CR-07 pattern)."""

        async def _stream_with_meta():
            meta_chunk = MagicMock(spec=["text", "is_final", "context_meta", "usage"])
            meta_chunk.text = ""
            meta_chunk.is_final = False
            meta_chunk.context_meta = {"kb_characters_count": 3}
            meta_chunk.usage = None
            yield meta_chunk

            text_chunk = MagicMock(spec=["text", "is_final", "context_meta", "usage"])
            text_chunk.text = "continuation text"
            text_chunk.is_final = True
            text_chunk.context_meta = None
            text_chunk.usage = None
            yield text_chunk

        mock_service = _mock_extend_service()
        mock_service.validate_extend = AsyncMock()
        mock_service.stream_extend.return_value = _stream_with_meta()

        with patch("narrare.writing.router_extend.get_extend_service", return_value=mock_service):
            response = await client.post(
                f"/api/v1/writing/chapters/{chapter_id}/extend",
                params={"novel_id": str(novel_id)},
                json={"text_before": "The sun was setting"},
            )

        assert response.status_code == status.HTTP_200_OK

        content = await response.aread()
        assert b"context_meta" in content
        assert b"kb_characters_count" in content
        assert b"continuation text" in content
