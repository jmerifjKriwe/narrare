"""Integration tests for AI provider CRUD API endpoints.

Uses real DB (via conftest fixtures), mocked LLM.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from narrare.settings.schemas import ProviderResponse

if TYPE_CHECKING:
    from httpx import AsyncClient


pytestmark = [pytest.mark.requires_db]


class TestCreateProvider:
    async def test_create_provider_returns_201(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST /settings/ai/providers → 201, creates provider."""
        response = await client.post(
            "/api/v1/settings/ai/providers",
            json={
                "provider_name": "anthropic",
                "api_key": "sk-ant-test-key-12345678",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        validated = ProviderResponse.model_validate(data)
        assert validated.provider_name == "anthropic"
        assert validated.has_api_key is True
        assert validated.is_active is True

    async def test_create_provider_with_base_url(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST /settings/ai/providers with base_url → 201."""
        response = await client.post(
            "/api/v1/settings/ai/providers",
            json={
                "provider_name": "openai",
                "api_key": "sk-test-key",
                "base_url": "https://my-proxy.example.com/v1",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["base_url"] == "https://my-proxy.example.com/v1"

    async def test_create_provider_unauthenticated_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        """POST /settings/ai/providers without auth → 401."""
        response = await client.post(
            "/api/v1/settings/ai/providers",
            json={
                "provider_name": "anthropic",
                "api_key": "sk-test",
            },
        )
        assert response.status_code == 401

    async def test_create_provider_invalid_input_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST /settings/ai/providers with empty api_key → 422."""
        response = await client.post(
            "/api/v1/settings/ai/providers",
            json={
                "provider_name": "anthropic",
                "api_key": "",
            },
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestListProviders:
    async def test_list_providers_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """GET /settings/ai/providers → 200, lists providers."""
        # Create a provider first
        await client.post(
            "/api/v1/settings/ai/providers",
            json={
                "provider_name": "anthropic",
                "api_key": "sk-ant-test-key",
            },
            headers=auth_headers,
        )

        response = await client.get(
            "/api/v1/settings/ai/providers",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

        # Verify masked key — never the full key
        provider = data[0]
        assert "api_key" not in provider
        assert provider["has_api_key"] is True

    async def test_list_providers_unauthenticated_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        """GET /settings/ai/providers without auth → 401."""
        response = await client.get("/api/v1/settings/ai/providers")
        assert response.status_code == 401


class TestUpdateProvider:
    async def test_update_provider_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """PATCH /settings/ai/providers/{id} → 200, updates provider."""
        # Create a provider first
        create_response = await client.post(
            "/api/v1/settings/ai/providers",
            json={
                "provider_name": "openai",
                "api_key": "sk-old-key",
            },
            headers=auth_headers,
        )
        provider_id = create_response.json()["id"]

        # Update it
        response = await client.patch(
            f"/api/v1/settings/ai/providers/{provider_id}",
            json={"api_key": "sk-new-key"},
            headers=auth_headers,
        )
        assert response.status_code == 200

    async def test_update_provider_not_found_returns_validation_error(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """PATCH /settings/ai/providers/{nonexistent} → error."""
        import uuid

        response = await client.patch(
            f"/api/v1/settings/ai/providers/{uuid.uuid4()}",
            json={"api_key": "sk-new"},
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestDeleteProvider:
    async def test_delete_provider_returns_204(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """DELETE /settings/ai/providers/{id} → 204, deletes provider."""
        # Create a provider first
        create_response = await client.post(
            "/api/v1/settings/ai/providers",
            json={
                "provider_name": "groq",
                "api_key": "gsk-test-key",
            },
            headers=auth_headers,
        )
        provider_id = create_response.json()["id"]

        # Delete it
        response = await client.delete(
            f"/api/v1/settings/ai/providers/{provider_id}",
            headers=auth_headers,
        )
        assert response.status_code == 204

    async def test_delete_provider_unauthenticated_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        """DELETE /settings/ai/providers/{id} without auth → 401."""
        import uuid

        response = await client.delete(
            f"/api/v1/settings/ai/providers/{uuid.uuid4()}",
        )
        assert response.status_code == 401
