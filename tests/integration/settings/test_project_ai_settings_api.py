"""Integration tests for project-level AI settings API endpoints.

Uses real DB (via conftest fixtures), mocked LLM.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from narrare.settings.schemas import ProjectAiSettingsResponse

if TYPE_CHECKING:
    from httpx import AsyncClient


pytestmark = [
    pytest.mark.skip(reason="temporarily disabled due to test infrastructure issues"),
    pytest.mark.requires_db,
]


class TestGetProjectAiSettings:
    async def test_get_project_ai_settings_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """GET /settings/ai/novels/{id} → 200, returns project AI settings."""
        # Create a novel first
        novel_response = await client.post(
            "/api/v1/novels",
            json={"title": "AI Settings Test Novel", "language": "en"},
            headers=auth_headers,
        )
        novel_id = novel_response.json()["id"]

        response = await client.get(
            f"/api/v1/settings/ai/novels/{novel_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        validated = ProjectAiSettingsResponse.model_validate(data)
        assert validated.novel_id is not None
        assert isinstance(validated.category_overrides, dict)

    async def test_get_project_ai_settings_unauthenticated_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        """GET /settings/ai/novels/{id} without auth → 401."""
        import uuid

        response = await client.get(
            f"/api/v1/settings/ai/novels/{uuid.uuid4()}",
        )
        assert response.status_code == 401


class TestUpdateProjectAiSettings:
    async def test_update_project_overrides_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """PATCH /settings/ai/novels/{id} → 200, updates project overrides."""
        # Create a novel
        novel_response = await client.post(
            "/api/v1/novels",
            json={"title": "Project Override Novel", "language": "en"},
            headers=auth_headers,
        )
        novel_id = novel_response.json()["id"]

        # Update project AI settings
        response = await client.patch(
            f"/api/v1/settings/ai/novels/{novel_id}",
            json={
                "category_overrides": {
                    "analysis": {"provider_id": "some-uuid", "model_id": "gpt-4o"},
                },
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "analysis" in data["category_overrides"]

    async def test_project_override_persists(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Project overrides persist across GET requests."""
        # Create novel
        novel_response = await client.post(
            "/api/v1/novels",
            json={"title": "Persist Novel", "language": "en"},
            headers=auth_headers,
        )
        novel_id = novel_response.json()["id"]

        # Set override
        await client.patch(
            f"/api/v1/settings/ai/novels/{novel_id}",
            json={
                "intent_overrides": {
                    "write": {"provider_id": "some-uuid", "model_id": "claude-sonnet-4-5"},
                },
            },
            headers=auth_headers,
        )

        # Read back
        response = await client.get(
            f"/api/v1/settings/ai/novels/{novel_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "write" in data["intent_overrides"]
