"""Unit tests for coauthor router — co-author revision endpoints.

Tests the thin delegation layer (RULE-06) ensuring routes delegate to
CoAuthorService / CoAuthorApplyService and map errors correctly.
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


def _mock_coauthor_apply_service() -> AsyncMock:
    """Create a mock CoAuthorApplyService with pre-configured methods."""
    service = AsyncMock()
    service.apply_changes = AsyncMock()
    service.record_feedback = AsyncMock()
    return service


# ---------------------------------------------------------------------------
# Apply Co-Author Changes
# ---------------------------------------------------------------------------


class TestApplyCoAuthorChanges:
    """Tests for POST /api/v1/writing/chapters/{chapter_id}/co-author/apply."""

    async def test_apply_returns_200_with_valid_input(
        self,
        app,
        client: AsyncClient,
        chapter_id: UUID,
        novel_id: UUID,
    ) -> None:
        """Happy path: apply changes returns 200 with chapter data."""
        from datetime import datetime

        mock_service = _mock_coauthor_apply_service()
        mock_service.apply_changes.return_value = MagicMock(
            spec=["request_id", "chapter_id", "word_count", "status"],
            id=chapter_id,
            novel_id=novel_id,
            volume_id=None,
            title="Revised Chapter",
            content="Revised content",
            summary="",
            position=1,
            word_count=50,
            status="draft",
            pov_character_id="",
            timeline_position="",
            created_at=datetime(2026, 1, 1),
            updated_at=datetime(2026, 1, 1),
        )

        with patch(
            "narrare.writing.router_coauthor.get_coauthor_apply_service", return_value=mock_service
        ):
            response = await client.post(
                f"/api/v1/writing/chapters/{chapter_id}/co-author/apply",
                params={"novel_id": str(novel_id)},
                json={
                    "request_id": str(uuid4()),
                    "original": "original text",
                    "accepted": [
                        {"original_text": "original", "revised_text": "revised"},
                    ],
                },
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["title"] == "Revised Chapter"
        assert str(data["id"]) == str(chapter_id)

    async def test_apply_returns_422_with_missing_body(
        self,
        client: AsyncClient,
        chapter_id: UUID,
        novel_id: UUID,
    ) -> None:
        """Validation: missing request body returns 422."""
        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/co-author/apply",
            params={"novel_id": str(novel_id)},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_apply_returns_422_with_invalid_uuid(
        self,
        client: AsyncClient,
        novel_id: UUID,
    ) -> None:
        """Validation: non-UUID chapter_id returns 422."""
        response = await client.post(
            "/api/v1/writing/chapters/not-a-uuid/co-author/apply",
            params={"novel_id": str(novel_id)},
            json={"request_id": str(uuid4()), "original": "text", "accepted": []},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_apply_returns_404_when_not_found(
        self,
        app,
        client: AsyncClient,
        chapter_id: UUID,
        novel_id: UUID,
    ) -> None:
        """Error: non-existent chapter returns 404."""
        from narrare_core.shared.errors import NotFoundError

        mock_service = _mock_coauthor_apply_service()
        mock_service.apply_changes.side_effect = NotFoundError(
            "Chapter",
            identifier=str(chapter_id),
        )

        with patch(
            "narrare.writing.router_coauthor.get_coauthor_apply_service", return_value=mock_service
        ):
            response = await client.post(
                f"/api/v1/writing/chapters/{chapter_id}/co-author/apply",
                params={"novel_id": str(novel_id)},
                json={"request_id": str(uuid4()), "original": "text", "accepted": []},
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Co-Author Feedback
# ---------------------------------------------------------------------------


class TestRecordCoAuthorFeedback:
    """Tests for POST /api/v1/writing/chapters/{chapter_id}/co-author/feedback."""

    async def test_feedback_returns_204(
        self,
        app,
        client: AsyncClient,
        chapter_id: UUID,
        novel_id: UUID,
    ) -> None:
        """Happy path: recording feedback returns 204."""
        mock_service = _mock_coauthor_apply_service()
        mock_service.record_feedback = AsyncMock()

        with patch(
            "narrare.writing.router_coauthor.get_coauthor_apply_service", return_value=mock_service
        ):
            response = await client.post(
                f"/api/v1/writing/chapters/{chapter_id}/co-author/feedback",
                params={"novel_id": str(novel_id)},
                json={
                    "request_id": str(uuid4()),
                    "feedback": [
                        {
                            "change_id": "change-1",
                            "action": "accepted",
                            "focus": "word_choice",
                            "original": "old",
                            "revised": "new",
                        },
                    ],
                },
            )

        assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_feedback_returns_422_with_missing_body(
        self,
        client: AsyncClient,
        chapter_id: UUID,
        novel_id: UUID,
    ) -> None:
        """Validation: missing request body returns 422."""
        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/co-author/feedback",
            params={"novel_id": str(novel_id)},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_feedback_returns_422_with_missing_request_id(
        self,
        client: AsyncClient,
        chapter_id: UUID,
        novel_id: UUID,
    ) -> None:
        """Validation: missing request_id returns 422."""
        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/co-author/feedback",
            params={"novel_id": str(novel_id)},
            json={
                "feedback": [
                    {
                        "change_id": "change-1",
                        "action": "accepted",
                        "focus": "word_choice",
                        "original": "old",
                        "revised": "new",
                    },
                ],
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_feedback_returns_404_when_generation_not_found(
        self,
        app,
        client: AsyncClient,
        chapter_id: UUID,
        novel_id: UUID,
    ) -> None:
        """Error: non-existent generation request returns 404."""
        from narrare_core.shared.errors import NotFoundError

        mock_service = _mock_coauthor_apply_service()
        mock_service.record_feedback.side_effect = NotFoundError(
            "GenerationRequest",
            identifier=str(uuid4()),
        )

        with patch(
            "narrare.writing.router_coauthor.get_coauthor_apply_service", return_value=mock_service
        ):
            response = await client.post(
                f"/api/v1/writing/chapters/{chapter_id}/co-author/feedback",
                params={"novel_id": str(novel_id)},
                json={
                    "request_id": str(uuid4()),
                    "feedback": [
                        {
                            "change_id": "change-1",
                            "action": "accepted",
                            "focus": "word_choice",
                            "original": "old",
                            "revised": "new",
                        },
                    ],
                },
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND
