"""Unit tests for stats router — scene-by-scene and generation stats endpoints.

Tests the thin delegation layer (RULE-06) ensuring routes delegate to
the writing service and map errors correctly.

Routes in router_stats.py:
  - POST /api/v1/writing/generation/{request_id}/scene/next
  - POST /api/v1/writing/generation/{request_id}/scene/{scene_number}/accept
  - GET /api/v1/writing/novels/{novel_id}/stats
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from narrare._app.database import get_async_session
from narrare._app.dependencies import get_current_user_id
from narrare._app.main import create_app

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
def request_id() -> UUID:
    return uuid4()


@pytest.fixture
def novel_id() -> UUID:
    return uuid4()


# ---------------------------------------------------------------------------
# Scene Next
# ---------------------------------------------------------------------------


class TestSceneNext:
    """Tests for POST /api/v1/writing/generation/{request_id}/scene/next."""

    async def test_scene_next_returns_200(
        self,
        app,
        client: AsyncClient,
        request_id: UUID,
    ) -> None:
        """Happy path: next scene request returns 200."""
        mock_service = AsyncMock()
        mock_service.next_scene = AsyncMock(
            return_value=MockResponse(
                request_id=request_id,
                scene_number=3,
                status="generated",
            ),
        )

        with patch("narrare.writing.router_stats.get_writing_service", return_value=mock_service):
            response = await client.post(
                f"/api/v1/writing/generation/{request_id}/scene/next",
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["scene_number"] == 3
        assert data["status"] == "generated"

    async def test_scene_next_returns_422_with_invalid_uuid(
        self,
        client: AsyncClient,
    ) -> None:
        """Validation: non-UUID request_id returns 422."""
        response = await client.post(
            "/api/v1/writing/generation/not-a-uuid/scene/next",
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_scene_next_returns_404_when_not_found(
        self,
        app,
        client: AsyncClient,
        request_id: UUID,
    ) -> None:
        """Error: non-existent generation request returns 404."""
        from narrare_core.shared.errors import NotFoundError

        mock_service = AsyncMock()
        mock_service.next_scene.side_effect = NotFoundError(
            "GenerationRequest",
            identifier=str(request_id),
        )

        with patch("narrare.writing.router_stats.get_writing_service", return_value=mock_service):
            response = await client.post(
                f"/api/v1/writing/generation/{request_id}/scene/next",
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_scene_next_returns_400_on_writing_error(
        self,
        app,
        client: AsyncClient,
        request_id: UUID,
    ) -> None:
        """Error: WritingError from service returns 400."""
        from narrare_core.shared.errors import WritingError

        mock_service = AsyncMock()
        mock_service.next_scene.side_effect = WritingError(
            "Cannot generate next scene in current state",
        )

        with patch("narrare.writing.router_stats.get_writing_service", return_value=mock_service):
            response = await client.post(
                f"/api/v1/writing/generation/{request_id}/scene/next",
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# Scene Accept
# ---------------------------------------------------------------------------


class TestSceneAccept:
    """Tests for POST /api/v1/writing/generation/{request_id}/scene/{scene_number}/accept."""

    async def test_scene_accept_returns_200(
        self,
        app,
        client: AsyncClient,
        request_id: UUID,
    ) -> None:
        """Happy path: accept scene returns 200."""
        mock_service = AsyncMock()
        mock_service.accept_scene = AsyncMock(
            return_value=MockResponse(
                request_id=request_id,
                chapter_id=uuid4(),
                word_count=500,
            ),
        )

        with patch("narrare.writing.router_stats.get_writing_service", return_value=mock_service):
            response = await client.post(
                f"/api/v1/writing/generation/{request_id}/scene/2/accept",
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["word_count"] == 500
        assert str(data["request_id"]) == str(request_id)

    async def test_scene_accept_returns_422_with_invalid_uuid(
        self,
        client: AsyncClient,
    ) -> None:
        """Validation: non-UUID request_id returns 422."""
        response = await client.post(
            "/api/v1/writing/generation/not-a-uuid/scene/1/accept",
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_scene_accept_returns_404_when_not_found(
        self,
        app,
        client: AsyncClient,
        request_id: UUID,
    ) -> None:
        """Error: non-existent generation request returns 404."""
        from narrare_core.shared.errors import NotFoundError

        mock_service = AsyncMock()
        mock_service.accept_scene.side_effect = NotFoundError(
            "GenerationRequest",
            identifier=str(request_id),
        )

        with patch("narrare.writing.router_stats.get_writing_service", return_value=mock_service):
            response = await client.post(
                f"/api/v1/writing/generation/{request_id}/scene/2/accept",
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_scene_accept_returns_400_on_writing_error(
        self,
        app,
        client: AsyncClient,
        request_id: UUID,
    ) -> None:
        """Error: WritingError from service returns 400."""
        from narrare_core.shared.errors import WritingError

        mock_service = AsyncMock()
        mock_service.accept_scene.side_effect = WritingError(
            "Cannot accept scene in current state",
        )

        with patch("narrare.writing.router_stats.get_writing_service", return_value=mock_service):
            response = await client.post(
                f"/api/v1/writing/generation/{request_id}/scene/2/accept",
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# Generation Stats
# ---------------------------------------------------------------------------


class TestGenerationStats:
    """Tests for GET /api/v1/writing/novels/{novel_id}/stats."""

    async def test_stats_returns_200(
        self,
        app,
        client: AsyncClient,
        novel_id: UUID,
    ) -> None:
        """Happy path: generation stats request returns 200."""
        mock_service = AsyncMock()
        mock_service.get_stats = AsyncMock(
            return_value=MockResponse(
                total_generations=42,
                success_rate=0.85,
                avg_tokens=1200.5,
                avg_word_count=850.3,
                most_used_model="gpt-4o",
            ),
        )

        with patch("narrare.writing.router_stats.get_writing_service", return_value=mock_service):
            response = await client.get(
                f"/api/v1/writing/novels/{novel_id}/stats",
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_generations"] == 42
        assert data["success_rate"] == 0.85
        assert data["most_used_model"] == "gpt-4o"

    async def test_stats_returns_422_with_invalid_uuid(
        self,
        client: AsyncClient,
    ) -> None:
        """Validation: non-UUID novel_id returns 422."""
        response = await client.get(
            "/api/v1/writing/novels/not-a-uuid/stats",
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_stats_returns_404_when_novel_not_found(
        self,
        app,
        client: AsyncClient,
        novel_id: UUID,
    ) -> None:
        """Error: non-existent novel returns 404."""
        from narrare_core.shared.errors import NotFoundError

        mock_service = AsyncMock()
        mock_service.get_stats.side_effect = NotFoundError(
            "Novel",
            identifier=str(novel_id),
        )

        with patch("narrare.writing.router_stats.get_writing_service", return_value=mock_service):
            response = await client.get(
                f"/api/v1/writing/novels/{novel_id}/stats",
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_stats_returns_400_on_writing_error(
        self,
        app,
        client: AsyncClient,
        novel_id: UUID,
    ) -> None:
        """Error: WritingError from service returns 400."""
        from narrare_core.shared.errors import WritingError

        mock_service = AsyncMock()
        mock_service.get_stats.side_effect = WritingError(
            "Stats not available for this novel",
        )

        with patch("narrare.writing.router_stats.get_writing_service", return_value=mock_service):
            response = await client.get(
                f"/api/v1/writing/novels/{novel_id}/stats",
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class MockResponse:
    """Simple mock object that allows attribute access and dict conversion.

    Mock objects returned by async mocks need to support both attribute access
    (for response_model serialization) and model_validate() compatibility.
    This class provides both via ``__init__`` kwargs and ``__getattr__``.
    """

    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)
