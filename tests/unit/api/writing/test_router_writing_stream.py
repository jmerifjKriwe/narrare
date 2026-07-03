"""Unit tests for main writing router — generation SSE stream endpoint.

Tests the thin delegation layer (RULE-06) ensuring the stream route delegates to
WritingService and maps errors correctly.
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
    """Create test app with overridden DB/auth dependencies for unit testing."""
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


@pytest.fixture
def request_id() -> UUID:
    return uuid4()


def _mock_writing_service() -> AsyncMock:
    """Create a mock WritingService with pre-configured methods.

    NOTE: ``stream_generation`` uses ``MagicMock`` instead of ``AsyncMock``
    because it is an async generator used in ``async for`` (not awaited).
    ``AsyncMock`` wraps the return value in a coroutine, which breaks
    ``async for`` iteration.
    """
    from narrare.writing.service import WritingService

    service = AsyncMock()
    service.start_generation = AsyncMock()
    service.validate_request_access = AsyncMock()
    service.stream_generation = MagicMock(spec=WritingService)
    service.stop_generation = AsyncMock()
    service.accept_draft = AsyncMock()
    service.reject_draft = AsyncMock()
    return service


# ---------------------------------------------------------------------------
# Stream (SSE)
# ---------------------------------------------------------------------------


class TestStreamGeneration:
    """Tests for GET /api/v1/writing/generation/{request_id}/stream (SSE)."""

    async def test_stream_returns_200_with_valid_request(
        self,
        app,
        client: AsyncClient,
        request_id: UUID,
    ) -> None:
        """Happy path: valid request_id returns 200 with SSE stream."""

        async def _stream():
            chunk = MagicMock(spec=["text", "is_final", "context_meta", "usage"])
            chunk.text = "test text"
            chunk.is_final = True
            chunk.context_meta = None
            chunk.usage = None
            yield chunk

        mock_service = _mock_writing_service()
        mock_service.validate_request_access = AsyncMock()
        mock_service.stream_generation.return_value = _stream()

        with patch("narrare.writing.router.get_writing_service", return_value=mock_service):
            response = await client.get(
                f"/api/v1/writing/generation/{request_id}/stream",
            )

        assert response.status_code == status.HTTP_200_OK
        assert "text/event-stream" in response.headers.get("content-type", "")

        content = await response.aread()
        assert b"test text" in content
        assert b"[DONE]" in content

    async def test_stream_returns_422_with_invalid_uuid(
        self,
        client: AsyncClient,
    ) -> None:
        """Validation: non-UUID request_id returns 422."""
        response = await client.get(
            "/api/v1/writing/generation/not-a-uuid/stream",
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_stream_returns_404_when_validation_fails(
        self,
        app,
        client: AsyncClient,
        request_id: UUID,
    ) -> None:
        """Error: non-existent generation request returns 404."""
        from narrare_core.shared.errors import NotFoundError

        mock_service = _mock_writing_service()
        mock_service.validate_request_access.side_effect = NotFoundError(
            "GenerationRequest",
            identifier=str(request_id),
        )

        with patch("narrare.writing.router.get_writing_service", return_value=mock_service):
            response = await client.get(
                f"/api/v1/writing/generation/{request_id}/stream",
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_stream_context_meta_event(
        self,
        app,
        client: AsyncClient,
        request_id: UUID,
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
            text_chunk.text = "generated text"
            text_chunk.is_final = True
            text_chunk.context_meta = None
            text_chunk.usage = None
            yield text_chunk

        mock_service = _mock_writing_service()
        mock_service.validate_request_access = AsyncMock()
        mock_service.stream_generation.return_value = _stream_with_meta()

        with patch("narrare.writing.router.get_writing_service", return_value=mock_service):
            response = await client.get(
                f"/api/v1/writing/generation/{request_id}/stream",
            )

        assert response.status_code == status.HTTP_200_OK

        content = await response.aread()
        assert b"context_meta" in content
        assert b"kb_characters_count" in content
        assert b"generated text" in content
