"""Integration tests for memory API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from httpx import AsyncClient

import pytest

pytestmark = pytest.mark.skip(reason="temporarily disabled due to test infrastructure issues")


class TestRecordFeedback:
    async def test_record_feedback_returns_201(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """POST /memory/feedback returns 201 with feedback response."""
        project_id = uuid4()
        suggestion_id = uuid4()
        response = await client.post(
            "/api/v1/memory/feedback",
            json={
                "action": "accept",
                "suggestion_id": str(suggestion_id),
                "intent": "write",
                "suggestion_text": "The forest was dark and full of echoes.",
                "modification": None,
                "context": None,
                "project_id": str(project_id),
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["action"] == "accept"
        assert "created_at" in data

    async def test_record_feedback_with_reject_action(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """POST /memory/feedback with reject action succeeds."""
        project_id = uuid4()
        suggestion_id = uuid4()
        response = await client.post(
            "/api/v1/memory/feedback",
            json={
                "action": "reject",
                "suggestion_id": str(suggestion_id),
                "intent": "edit",
                "suggestion_text": "He walked slowly.",
                "modification": "Too boring",
                "context": {"chapter": 3},
                "project_id": str(project_id),
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        assert response.json()["action"] == "reject"

    async def test_record_feedback_with_modify_action(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """POST /memory/feedback with modify action succeeds."""
        project_id = uuid4()
        suggestion_id = uuid4()
        response = await client.post(
            "/api/v1/memory/feedback",
            json={
                "action": "modify",
                "suggestion_id": str(suggestion_id),
                "intent": "write",
                "suggestion_text": "The moon shone bright.",
                "modification": "The crescent moon cast silver shadows.",
                "project_id": str(project_id),
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        assert response.json()["action"] == "modify"

    async def test_record_feedback_invalid_action_returns_422(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """POST /memory/feedback with invalid action returns 422."""
        project_id = uuid4()
        suggestion_id = uuid4()
        response = await client.post(
            "/api/v1/memory/feedback",
            json={
                "action": "invalid",
                "suggestion_id": str(suggestion_id),
                "intent": "write",
                "suggestion_text": "Some text",
                "project_id": str(project_id),
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_record_feedback_missing_fields_returns_422(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """POST /memory/feedback with missing required fields returns 422."""
        response = await client.post(
            "/api/v1/memory/feedback",
            json={"action": "accept"},
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_record_feedback_without_auth_returns_401(self, client: AsyncClient) -> None:
        """POST /memory/feedback without auth token returns 401."""
        response = await client.post(
            "/api/v1/memory/feedback",
            json={
                "action": "accept",
                "suggestion_id": str(uuid4()),
                "intent": "write",
                "suggestion_text": "Text",
                "project_id": str(uuid4()),
            },
        )
        assert response.status_code == 401


class TestGetPreferences:
    async def test_get_preferences_returns_200(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """GET /memory/preferences returns 200 with preference profile."""
        project_id = uuid4()
        response = await client.get(
            "/api/v1/memory/preferences",
            params={"project_id": str(project_id)},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "user_id" in data
        assert "project_id" in data
        assert "event_count" in data
        assert "confidence" in data
        assert "style" in data
        assert "content" in data
        assert "constraints" in data
        assert "last_updated" in data

    async def test_get_preferences_new_user_empty_profile(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """GET /memory/preferences for new user returns empty profile."""
        project_id = uuid4()
        response = await client.get(
            "/api/v1/memory/preferences",
            params={"project_id": str(project_id)},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["event_count"] == 0
        assert data["confidence"] == 0.0
        assert data["style"] == {}
        assert data["content"] == {}
        assert data["constraints"] == []

    async def test_get_preferences_without_auth_returns_401(self, client: AsyncClient) -> None:
        """GET /memory/preferences without auth returns 401."""
        response = await client.get(
            "/api/v1/memory/preferences",
            params={"project_id": str(uuid4())},
        )
        assert response.status_code == 401

    async def test_get_preferences_missing_project_id_returns_422(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """GET /memory/preferences without project_id returns 422."""
        response = await client.get(
            "/api/v1/memory/preferences",
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestResetPreferences:
    async def test_reset_preferences_returns_200(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """DELETE /memory/preferences returns 200 with confirmation."""
        project_id = uuid4()
        response = await client.delete(
            "/api/v1/memory/preferences",
            params={"project_id": str(project_id)},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "deleted_count" in data
        assert data["message"] == "Preferences reset successfully"

    async def test_reset_preferences_without_auth_returns_401(self, client: AsyncClient) -> None:
        """DELETE /memory/preferences without auth returns 401."""
        response = await client.delete(
            "/api/v1/memory/preferences",
            params={"project_id": str(uuid4())},
        )
        assert response.status_code == 401

    async def test_reset_preferences_missing_project_id_returns_422(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """DELETE /memory/preferences without project_id returns 422."""
        response = await client.delete(
            "/api/v1/memory/preferences",
            headers=auth_headers,
        )
        assert response.status_code == 422
