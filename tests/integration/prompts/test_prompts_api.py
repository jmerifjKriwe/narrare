"""Integration tests for prompts API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = pytest.mark.skip(reason="temporarily disabled due to test infrastructure issues")


class TestListPrompts:
    async def test_list_prompts_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """GET /prompts returns 200 with a list."""
        response = await client.get("/api/v1/prompts", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    async def test_list_prompts_with_category_filter(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """GET /prompts?category=generation returns filtered list."""
        response = await client.get(
            "/api/v1/prompts",
            params={"category": "generation"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        for item in data:
            assert item["category"] == "generation"

    async def test_list_prompts_without_auth_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        """GET /prompts without auth returns 401."""
        response = await client.get("/api/v1/prompts")
        assert response.status_code == 401


class TestGetPrompt:
    async def test_get_prompt_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """GET /prompts/{prompt_id} returns prompt detail if found."""
        # First list to get a valid prompt ID
        list_resp = await client.get("/api/v1/prompts", headers=auth_headers)
        prompts = list_resp.json()

        if not prompts:
            pytest.skip("No prompts available in bundled directory")

        prompt_id = prompts[0]["id"]
        response = await client.get(
            f"/api/v1/prompts/{prompt_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == prompt_id
        assert "content" in data
        assert "base_content" in data
        assert "source" in data
        assert "is_overridden" in data
        assert "variables" in data
        assert "metadata" in data

    async def test_get_prompt_not_found_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """GET /prompts/{prompt_id} returns 404 for nonexistent prompt."""
        response = await client.get(
            "/api/v1/prompts/nonexistent/en/test",
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestSaveOverride:
    async def test_save_override_returns_204(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """PUT /prompts/{prompt_id} saves override and returns 204."""
        # First list to get a valid prompt ID
        list_resp = await client.get("/api/v1/prompts", headers=auth_headers)
        prompts = list_resp.json()

        if not prompts:
            pytest.skip("No prompts available in bundled directory")

        prompt_id = prompts[0]["id"]
        response = await client.put(
            f"/api/v1/prompts/{prompt_id}",
            json={"content": "---\nprompt_version: '1.0.0'\n---\n\nTest override content"},
            headers=auth_headers,
        )
        assert response.status_code == 204

    async def test_save_override_without_auth_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        """PUT /prompts/{prompt_id} without auth returns 401."""
        response = await client.put(
            "/api/v1/prompts/test/en/test",
            json={"content": "test"},
        )
        assert response.status_code == 401

    async def test_save_override_empty_content_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """PUT /prompts/{prompt_id} with empty content returns 422."""
        response = await client.put(
            "/api/v1/prompts/test/en/test",
            json={"content": ""},
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestResetOverride:
    async def test_reset_override_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """DELETE /prompts/{prompt_id}/override returns 200 with bool."""
        response = await client.delete(
            "/api/v1/prompts/test/en/test/override",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, bool)

    async def test_reset_override_without_auth_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        """DELETE /prompts/{prompt_id}/override without auth returns 401."""
        response = await client.delete(
            "/api/v1/prompts/test/en/test/override",
        )
        assert response.status_code == 401


class TestCascadeInfo:
    async def test_cascade_info_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """GET /prompts/{prompt_id}/cascade returns cascade paths."""
        # First list to get a valid prompt ID
        list_resp = await client.get("/api/v1/prompts", headers=auth_headers)
        prompts = list_resp.json()

        if not prompts:
            pytest.skip("No prompts available in bundled directory")

        prompt_id = prompts[0]["id"]
        response = await client.get(
            f"/api/v1/prompts/{prompt_id}/cascade",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        for entry in data:
            assert "level" in entry
            assert "path" in entry
            assert "exists" in entry


class TestDetectUpdates:
    async def test_detect_updates_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """GET /prompts/updates returns 200 with update list."""
        response = await client.get("/api/v1/prompts/updates", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    async def test_detect_updates_without_auth_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        """GET /prompts/updates without auth returns 401."""
        response = await client.get("/api/v1/prompts/updates")
        assert response.status_code == 401
