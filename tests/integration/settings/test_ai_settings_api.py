"""Integration tests for AI settings API endpoints.

Uses real DB (via conftest fixtures), mocked LLM.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare.settings.schemas import UserAiSettingsResponse

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestGetUserAiSettings:
    async def test_get_ai_settings_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """GET /settings/ai → 200, returns user AI settings."""
        response = await client.get(
            "/api/v1/settings/ai",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        validated = UserAiSettingsResponse.model_validate(data)
        assert validated.user_id is not None

    async def test_get_ai_settings_unauthenticated_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        """GET /settings/ai without auth → 401."""
        response = await client.get("/api/v1/settings/ai")
        assert response.status_code == 401


class TestUpdateUserAiSettings:
    async def test_update_default_model_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """PATCH /settings/ai → 200, updates default model."""
        # Create a provider first
        create_response = await client.post(
            "/api/v1/settings/ai/providers",
            json={
                "provider_name": "anthropic",
                "api_key": "sk-ant-test-key",
            },
            headers=auth_headers,
        )
        provider_id = create_response.json()["id"]

        # Set default model
        response = await client.patch(
            "/api/v1/settings/ai",
            json={
                "default_provider_id": provider_id,
                "default_model": "claude-sonnet-4-5-20251020",
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["default_provider_id"] == provider_id
        assert data["default_model"] == "claude-sonnet-4-5-20251020"

    async def test_update_with_invalid_provider_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """PATCH /settings/ai with non-existent provider → 400."""
        import uuid

        response = await client.patch(
            "/api/v1/settings/ai",
            json={
                "default_provider_id": str(uuid.uuid4()),
                "default_model": "gpt-4o",
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_set_category_override(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """PATCH /settings/ai with category override → 200."""
        # Create provider
        create_response = await client.post(
            "/api/v1/settings/ai/providers",
            json={
                "provider_name": "openai",
                "api_key": "sk-test-key",
            },
            headers=auth_headers,
        )
        provider_id = create_response.json()["id"]

        # Set category override
        response = await client.patch(
            "/api/v1/settings/ai",
            json={
                "category_overrides": {
                    "writing": {
                        "provider_id": provider_id,
                        "model_id": "gpt-4o",
                    },
                },
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "writing" in data["category_overrides"]


class TestGetEffectiveSettings:
    async def test_get_settings_after_update_shows_values(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """GET /settings/ai after updates → reflects changes."""
        # Create provider
        create_response = await client.post(
            "/api/v1/settings/ai/providers",
            json={
                "provider_name": "anthropic",
                "api_key": "sk-ant-key",
            },
            headers=auth_headers,
        )
        provider_id = create_response.json()["id"]

        # Update settings
        await client.patch(
            "/api/v1/settings/ai",
            json={
                "default_provider_id": provider_id,
                "default_model": "claude-sonnet-4-5-20251020",
            },
            headers=auth_headers,
        )

        # Get settings
        response = await client.get(
            "/api/v1/settings/ai",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["default_model"] == "claude-sonnet-4-5-20251020"
        assert data["default_provider_id"] == provider_id
