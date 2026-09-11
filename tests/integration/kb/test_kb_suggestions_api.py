"""Integration tests for KB suggestions API endpoint.

Tests GET /novels/{novel_id}/kb/suggestions/{chapter_id} with mocked
KBSuggestService via dependency_overrides.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from narrare.kb.dependencies import get_kb_suggest_service
from narrare.kb.schemas import KBSuggestionResponse
from narrare.kb.suggest_service import KBSuggestService

if TYPE_CHECKING:
    from fastapi import FastAPI
    from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_suggest_service() -> MagicMock:
    """Create a mocked KBSuggestService for dependency override."""
    service = MagicMock(spec=KBSuggestService)
    service.get_suggestions = AsyncMock(return_value=[])
    return service


def _override_service(
    app: FastAPI,
    mock_suggest_service: MagicMock,
) -> None:
    """Wire the mock service into the app's dependency overrides.

    Callers must pop the override in a ``finally`` block — the app fixture
    is session-scoped, so a leftover override leaks into subsequent tests
    (order-dependent flakiness under pytest-randomly). Cleanup convention:
    tests/integration/analysis/test_analysis_api.py.
    """
    app.dependency_overrides[get_kb_suggest_service] = lambda: mock_suggest_service  # type: ignore[assignment]


def _caller_user_id(auth_headers: dict[str, str]) -> UUID:
    """Decode the authenticated caller's id from the bearer token.

    The ``auth_headers`` fixture mints a fresh user per test, so the
    ownership input (``user_id`` threaded since IDOR S9) can only be
    recovered from the token itself.
    """
    from narrare._app.config import get_settings
    from narrare.auth.security import verify_access_token

    token = auth_headers["Authorization"].removeprefix("Bearer ")
    payload = verify_access_token(token, get_settings().secret_key)
    assert payload is not None, "auth_headers fixture must carry a valid token"
    return UUID(payload["sub"])


# ---------------------------------------------------------------------------
# Tests: GET /novels/{novel_id}/kb/suggestions/{chapter_id}
# ---------------------------------------------------------------------------


class TestGetSuggestions:
    """Test GET /novels/{novel_id}/kb/suggestions/{chapter_id}."""

    async def test_suggestions_returns_200_with_empty_list(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        mock_suggest_service: MagicMock,
    ) -> None:
        """GET suggestions returns 200 with empty list when no suggestions."""
        _override_service(app, mock_suggest_service)

        novel_id = uuid4()
        chapter_id = uuid4()

        try:
            resp = await client.get(
                f"/api/v1/novels/{novel_id}/kb/suggestions/{chapter_id}",
                headers=auth_headers,
            )
        finally:
            app.dependency_overrides.pop(get_kb_suggest_service, None)

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 0

        mock_suggest_service.get_suggestions.assert_awaited_once_with(
            chapter_id=chapter_id,
            novel_id=novel_id,
            user_id=_caller_user_id(auth_headers),
            max_results=20,
        )

    async def test_suggestions_returns_200_with_results(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        mock_suggest_service: MagicMock,
    ) -> None:
        """GET suggestions returns 200 with KBSuggestionResponse items."""
        from datetime import UTC, datetime

        entry_id_1 = uuid4()
        entry_id_2 = uuid4()
        referenced_at = datetime.now(UTC)

        mock_suggest_service.get_suggestions = AsyncMock(
            return_value=[
                KBSuggestionResponse(
                    entry_id=entry_id_1,
                    entry_type="character",
                    name="Alice",
                    relevance_score=0.9,
                    reason="Main character in scene",
                    similarity=0.85,
                    usage_count=3,
                    last_referenced_at=referenced_at,
                ),
                KBSuggestionResponse(
                    entry_id=entry_id_2,
                    entry_type="location",
                    name="Castle",
                    relevance_score=0.7,
                    reason="Setting for the scene",
                    similarity=0.6,
                    usage_count=1,
                    last_referenced_at=None,
                ),
            ],
        )

        _override_service(app, mock_suggest_service)

        novel_id = uuid4()
        chapter_id = uuid4()

        try:
            resp = await client.get(
                f"/api/v1/novels/{novel_id}/kb/suggestions/{chapter_id}",
                headers=auth_headers,
            )
        finally:
            app.dependency_overrides.pop(get_kb_suggest_service, None)

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2

        # Validate first suggestion schema
        first = data[0]
        assert first["entry_id"] == str(entry_id_1)
        assert first["entry_type"] == "character"
        assert first["name"] == "Alice"
        assert first["relevance_score"] == 0.9
        assert first["reason"] == "Main character in scene"
        assert first["similarity"] == 0.85
        assert first["usage_count"] == 3
        assert first["last_referenced_at"] is not None

        # Validate second suggestion schema
        second = data[1]
        assert second["entry_id"] == str(entry_id_2)
        assert second["entry_type"] == "location"
        assert second["name"] == "Castle"
        assert second["relevance_score"] == 0.7
        assert second["reason"] == "Setting for the scene"
        assert second["similarity"] == 0.6
        assert second["usage_count"] == 1
        assert second["last_referenced_at"] is None

    async def test_suggestions_returns_401_without_auth(
        self,
        client: AsyncClient,
        app: FastAPI,
        mock_suggest_service: MagicMock,
    ) -> None:
        """GET suggestions returns 401 when no auth token is provided."""
        _override_service(app, mock_suggest_service)

        novel_id = uuid4()
        chapter_id = uuid4()

        try:
            resp = await client.get(
                f"/api/v1/novels/{novel_id}/kb/suggestions/{chapter_id}",
            )
        finally:
            app.dependency_overrides.pop(get_kb_suggest_service, None)

        assert resp.status_code == 401

    async def test_suggestions_with_max_results_param(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        mock_suggest_service: MagicMock,
    ) -> None:
        """GET suggestions passes max_results query parameter to service."""
        _override_service(app, mock_suggest_service)

        novel_id = uuid4()
        chapter_id = uuid4()

        try:
            resp = await client.get(
                f"/api/v1/novels/{novel_id}/kb/suggestions/{chapter_id}",
                params={"max_results": 5},
                headers=auth_headers,
            )
        finally:
            app.dependency_overrides.pop(get_kb_suggest_service, None)

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

        mock_suggest_service.get_suggestions.assert_awaited_once_with(
            chapter_id=chapter_id,
            novel_id=novel_id,
            user_id=_caller_user_id(auth_headers),
            max_results=5,
        )

    async def test_suggestions_with_invalid_uuid_returns_422(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        mock_suggest_service: MagicMock,
    ) -> None:
        """GET suggestions returns 422 when path params are not valid UUIDs."""
        _override_service(app, mock_suggest_service)

        try:
            resp = await client.get(
                "/api/v1/novels/not-a-uuid/kb/suggestions/also-not-a-uuid",
                headers=auth_headers,
            )
        finally:
            app.dependency_overrides.pop(get_kb_suggest_service, None)

        assert resp.status_code == 422
