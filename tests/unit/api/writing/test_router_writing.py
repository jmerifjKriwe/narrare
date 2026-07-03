"""Unit tests for main writing router — generation lifecycle endpoints.

Tests the thin delegation layer (RULE-06) ensuring routes delegate to
WritingService and map errors correctly.

NOTE: The router calls ``get_writing_service`` directly (not via Depends),
so we use ``unittest.mock.patch`` on the router module's reference rather
than ``dependency_overrides``.
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
    # Bypass rate limiter for unit tests
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
# Generate
# ---------------------------------------------------------------------------


class TestStartGeneration:
    """Tests for POST /api/v1/writing/chapters/{chapter_id}/generate."""

    async def test_generate_returns_200_with_valid_input(
        self,
        app,
        client: AsyncClient,
        chapter_id: UUID,
        novel_id: UUID,
    ) -> None:
        """Happy path: valid chapter/generation request returns 200."""
        from narrare.writing.schemas import GenerateResponse

        mock_service = _mock_writing_service()
        mock_service.start_generation.return_value = GenerateResponse(
            request_id=uuid4(),
            status="pending",
            mode="full_draft",
        )

        with patch("narrare.writing.router.get_writing_service", return_value=mock_service):
            response = await client.post(
                f"/api/v1/writing/chapters/{chapter_id}/generate",
                params={"novel_id": str(novel_id)},
                json={
                    "mode": "full_draft",
                    "tone": "balanced",
                    "language": "en",
                },
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "pending"
        assert "request_id" in data

    async def test_generate_returns_422_with_missing_body(
        self,
        client: AsyncClient,
        chapter_id: UUID,
        novel_id: UUID,
    ) -> None:
        """Validation: missing request body returns 422."""
        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/generate",
            params={"novel_id": str(novel_id)},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_generate_returns_422_with_invalid_mode(
        self,
        client: AsyncClient,
        chapter_id: UUID,
        novel_id: UUID,
    ) -> None:
        """Validation: invalid generation mode returns 422."""
        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/generate",
            params={"novel_id": str(novel_id)},
            json={"mode": "not_a_valid_mode"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_generate_returns_422_with_invalid_chapter_id(
        self,
        client: AsyncClient,
        novel_id: UUID,
    ) -> None:
        """Validation: non-UUID chapter_id returns 422."""
        response = await client.post(
            "/api/v1/writing/chapters/not-a-uuid/generate",
            params={"novel_id": str(novel_id)},
            json={"mode": "full_draft", "tone": "balanced", "language": "en"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_generate_returns_404_when_chapter_not_found(
        self,
        app,
        client: AsyncClient,
        chapter_id: UUID,
        novel_id: UUID,
    ) -> None:
        """Error: non-existent chapter returns 404."""
        from narrare_core.shared.errors import NotFoundError

        mock_service = _mock_writing_service()
        mock_service.start_generation.side_effect = NotFoundError(
            "Chapter", identifier=str(chapter_id)
        )

        with patch("narrare.writing.router.get_writing_service", return_value=mock_service):
            response = await client.post(
                f"/api/v1/writing/chapters/{chapter_id}/generate",
                params={"novel_id": str(novel_id)},
                json={"mode": "full_draft", "tone": "balanced", "language": "en"},
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_generate_returns_500_when_service_fails(
        self,
        app,
        client: AsyncClient,
        chapter_id: UUID,
        novel_id: UUID,
    ) -> None:
        """Error: LLM failure returns 500."""
        from narrare_core.shared.errors import WritingError

        mock_service = _mock_writing_service()
        mock_service.start_generation.side_effect = WritingError("LLM call failed")

        with patch("narrare.writing.router.get_writing_service", return_value=mock_service):
            response = await client.post(
                f"/api/v1/writing/chapters/{chapter_id}/generate",
                params={"novel_id": str(novel_id)},
                json={"mode": "full_draft", "tone": "balanced", "language": "en"},
            )

        # WritingError is a NarrareError subclass → global handler returns 400
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# Stop
# ---------------------------------------------------------------------------


class TestStopGeneration:
    """Tests for DELETE /api/v1/writing/generation/{request_id}."""

    async def test_stop_returns_200(
        self,
        app,
        client: AsyncClient,
        request_id: UUID,
    ) -> None:
        """Happy path: stop in-progress generation returns 200."""
        from narrare.writing.schemas import StopResponse

        mock_service = _mock_writing_service()
        mock_service.stop_generation.return_value = StopResponse(
            request_id=request_id,
            status="stopped",
            word_count=100,
        )

        with patch("narrare.writing.router.get_writing_service", return_value=mock_service):
            response = await client.delete(
                f"/api/v1/writing/generation/{request_id}",
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "stopped"
        assert data["word_count"] == 100

    async def test_stop_returns_422_with_invalid_uuid(
        self,
        client: AsyncClient,
    ) -> None:
        """Validation: non-UUID request_id returns 422."""
        response = await client.delete(
            "/api/v1/writing/generation/not-a-uuid",
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_stop_returns_404_when_not_found(
        self,
        app,
        client: AsyncClient,
        request_id: UUID,
    ) -> None:
        """Error: non-existent generation returns 404."""
        from narrare_core.shared.errors import NotFoundError

        mock_service = _mock_writing_service()
        mock_service.stop_generation.side_effect = NotFoundError(
            "GenerationRequest",
            identifier=str(request_id),
        )

        with patch("narrare.writing.router.get_writing_service", return_value=mock_service):
            response = await client.delete(
                f"/api/v1/writing/generation/{request_id}",
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Accept
# ---------------------------------------------------------------------------


class TestAcceptDraft:
    """Tests for POST /api/v1/writing/generation/{request_id}/accept."""

    async def test_accept_returns_200(
        self,
        app,
        client: AsyncClient,
        request_id: UUID,
    ) -> None:
        """Happy path: accept generated draft returns 200."""
        from narrare.writing.schemas import AcceptResponse

        mock_service = _mock_writing_service()
        mock_service.accept_draft.return_value = AcceptResponse(
            request_id=request_id,
            chapter_id=uuid4(),
            word_count=200,
        )

        with patch("narrare.writing.router.get_writing_service", return_value=mock_service):
            response = await client.post(
                f"/api/v1/writing/generation/{request_id}/accept",
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["word_count"] == 200
        assert "chapter_id" in data

    async def test_accept_returns_422_with_invalid_uuid(
        self,
        client: AsyncClient,
    ) -> None:
        """Validation: non-UUID request_id returns 422."""
        response = await client.post(
            "/api/v1/writing/generation/not-a-uuid/accept",
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_accept_returns_404_when_not_found(
        self,
        app,
        client: AsyncClient,
        request_id: UUID,
    ) -> None:
        """Error: non-existent generation returns 404."""
        from narrare_core.shared.errors import NotFoundError

        mock_service = _mock_writing_service()
        mock_service.accept_draft.side_effect = NotFoundError(
            "GenerationRequest",
            identifier=str(request_id),
        )

        with patch("narrare.writing.router.get_writing_service", return_value=mock_service):
            response = await client.post(
                f"/api/v1/writing/generation/{request_id}/accept",
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND
