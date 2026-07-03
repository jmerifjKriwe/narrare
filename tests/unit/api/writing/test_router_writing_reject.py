"""Unit tests for writing router — reject draft endpoint.

Tests the thin delegation layer (RULE-06) ensuring the reject route delegates to
WritingService and maps errors correctly.
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
def request_id() -> UUID:
    return uuid4()


def _mock_writing_service() -> AsyncMock:
    """Create a mock WritingService with pre-configured methods."""
    from narrare.writing.service import WritingService

    service = AsyncMock(spec=WritingService)
    service.reject_draft = AsyncMock()
    return service


# ---------------------------------------------------------------------------
# Reject
# ---------------------------------------------------------------------------


class TestRejectDraft:
    """Tests for POST /api/v1/writing/generation/{request_id}/reject."""

    async def test_reject_returns_200(
        self,
        app,
        client: AsyncClient,
        request_id: UUID,
    ) -> None:
        """Happy path: reject generated draft returns 200."""
        from narrare.writing.schemas import RejectResponse

        mock_service = _mock_writing_service()
        mock_service.reject_draft.return_value = RejectResponse(
            request_id=request_id,
        )

        with patch("narrare.writing.router.get_writing_service", return_value=mock_service):
            response = await client.post(
                f"/api/v1/writing/generation/{request_id}/reject",
            )

        assert response.status_code == status.HTTP_200_OK
        RejectResponse.model_validate(response.json())
        data = response.json()
        assert data["status"] == "rejected"
        assert data["request_id"] == str(request_id)

    async def test_reject_returns_422_with_invalid_uuid(
        self,
        client: AsyncClient,
    ) -> None:
        """Validation: non-UUID request_id returns 422."""
        response = await client.post(
            "/api/v1/writing/generation/not-a-uuid/reject",
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_reject_returns_404_when_not_found(
        self,
        app,
        client: AsyncClient,
        request_id: UUID,
    ) -> None:
        """Error: non-existent generation returns 404."""
        from narrare_core.shared.errors import NotFoundError

        mock_service = _mock_writing_service()
        mock_service.reject_draft.side_effect = NotFoundError(
            "GenerationRequest",
            identifier=str(request_id),
        )

        with patch("narrare.writing.router.get_writing_service", return_value=mock_service):
            response = await client.post(
                f"/api/v1/writing/generation/{request_id}/reject",
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND
