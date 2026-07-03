"""Unit tests for story suggest router — story-level suggestion SSE endpoint.

Tests the thin delegation layer (RULE-06) ensuring routes delegate to
StorySuggestService and map errors correctly.

StorySuggestRequest schema requires: novel_id (UUID), plus optional
chapter_id and author_instructions.

Route: POST /api/v1/writing/story-suggest/{novel_id}
The route calls `event.model_dump(mode="json")` on each chunk,
so test chunks must support `model_dump()`.
"""

from __future__ import annotations

from typing import Any
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


class _TestEvent:
    """Test double for story suggest stream events.

    Supports ``model_dump(mode="json")`` used in the route to serialize
    each SSE chunk.  Accepts any keyword args and returns them as the
    dump dict.
    """

    def __init__(self, **data) -> None:
        self._data = data

    def model_dump(self, mode: str = "json") -> dict[str, Any]:
        return self._data


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
def novel_id() -> UUID:
    return uuid4()


def _mock_story_suggest_service() -> AsyncMock:
    """Create a mock StorySuggestService with pre-configured methods."""
    from narrare.writing.story_suggest_service import StorySuggestService

    service = AsyncMock()
    service.suggest = MagicMock(spec=StorySuggestService)
    return service


# ---------------------------------------------------------------------------
# Story Suggest (SSE)
# ---------------------------------------------------------------------------


class TestStorySuggest:
    """Tests for POST /api/v1/writing/story-suggest/{novel_id} (SSE)."""

    async def test_story_suggest_returns_200_with_valid_input(
        self,
        app,
        client: AsyncClient,
        novel_id: UUID,
    ) -> None:
        """Happy path: valid story suggest request returns 200 with SSE stream."""

        async def _stream():
            yield _TestEvent(
                event="done",
                suggestions=None,
                is_final=True,
                error=None,
            )

        mock_service = _mock_story_suggest_service()
        mock_service.suggest.return_value = _stream()

        with patch(
            "narrare.writing.router_story_suggest.get_story_suggest_service",
            return_value=mock_service,
        ):
            response = await client.post(
                f"/api/v1/writing/story-suggest/{novel_id}",
                json={
                    "novel_id": str(novel_id),
                    "author_instructions": "Surprise me with a plot twist",
                },
            )

        assert response.status_code == status.HTTP_200_OK
        assert "text/event-stream" in response.headers.get("content-type", "")

        content = await response.aread()
        assert b"[DONE]" in content

    async def test_story_suggest_returns_422_with_missing_novel_id_in_body(
        self,
        client: AsyncClient,
        novel_id: UUID,
    ) -> None:
        """Validation: missing novel_id in body returns 422."""
        response = await client.post(
            f"/api/v1/writing/story-suggest/{novel_id}",
            json={},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_story_suggest_returns_422_with_invalid_novel_uuid(
        self,
        client: AsyncClient,
    ) -> None:
        """Validation: non-UUID novel_id in path returns 422."""
        response = await client.post(
            "/api/v1/writing/story-suggest/not-a-uuid",
            json={
                "novel_id": str(uuid4()),
                "author_instructions": "Surprise me",
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    # NOTE: Error-during-stream tests (e.g. NotFoundError from
    # service.suggest) are not included for SSE routes because the
    # response starts before the stream iterates.  The global exception
    # handler catches the error but cannot change the 200 status code
    # after headers are sent, resulting in a RuntimeError that the test
    # client captures as an error.  This is an inherent SSE limitation —
    # the other SSE routes (rewrite, extend, suggest, co-author) handle
    # this via pre-validation (validate_*() before the StreamingResponse).
    # story_suggest pre-validates novel existence in the factory instead.

    async def test_story_suggest_context_meta_event(
        self,
        app,
        client: AsyncClient,
        novel_id: UUID,
    ) -> None:
        """SSE: stream can contain multiple events."""

        async def _stream_with_events():
            yield _TestEvent(
                event="suggestions",
                suggestions=[
                    {
                        "type": "plot_development",
                        "title": "A Title",
                        "description": "A description",
                        "connection": "Connects to main plot",
                    },
                ],
                is_final=False,
                error=None,
            )
            yield _TestEvent(
                event="done",
                suggestions=None,
                is_final=True,
                error=None,
            )

        mock_service = _mock_story_suggest_service()
        mock_service.suggest.return_value = _stream_with_events()

        with patch(
            "narrare.writing.router_story_suggest.get_story_suggest_service",
            return_value=mock_service,
        ):
            response = await client.post(
                f"/api/v1/writing/story-suggest/{novel_id}",
                json={
                    "novel_id": str(novel_id),
                    "author_instructions": "Surprise me with a plot twist",
                },
            )

        assert response.status_code == status.HTTP_200_OK

        content = await response.aread()
        assert b"suggestions" in content
        assert b"[DONE]" in content
