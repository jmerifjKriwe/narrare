"""Integration tests for settings endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestUserSettings:
    async def test_get_user_settings_creates_defaults(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.get("/api/v1/settings/user", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "ui_language" in data
        assert "theme" in data

    async def test_get_user_settings_without_auth_returns_401(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/settings/user")
        assert response.status_code == 401

    async def test_update_user_settings(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.patch(
            "/api/v1/settings/user",
            json={"display_name": "New Name", "theme": "dark"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == "New Name"
        assert data["theme"] == "dark"

    async def test_update_user_settings_invalid_theme_returns_422(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.patch(
            "/api/v1/settings/user",
            json={"theme": "invalid-theme"},
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestProjectSettings:
    async def test_get_project_settings_creates_defaults(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        # Create a novel first
        novel = await client.post(
            "/api/v1/novels",
            json={"title": "Settings Test Novel"},
            headers=auth_headers,
        )
        novel_id = novel.json()["id"]

        response = await client.get(f"/api/v1/settings/novels/{novel_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["autosave_interval"] == 30
        assert data["default_language"] == "en"

    async def test_update_project_settings(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        novel = await client.post(
            "/api/v1/novels",
            json={"title": "Settings Update Novel"},
            headers=auth_headers,
        )
        novel_id = novel.json()["id"]

        response = await client.patch(
            f"/api/v1/settings/novels/{novel_id}",
            json={"ai_provider": "anthropic", "ai_model": "claude-sonnet"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ai_provider"] == "anthropic"
        assert data["ai_model"] == "claude-sonnet"

    async def test_update_project_settings_invalid_interval_returns_422(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        novel = await client.post(
            "/api/v1/novels",
            json={"title": "Settings Invalid Novel"},
            headers=auth_headers,
        )
        novel_id = novel.json()["id"]

        response = await client.patch(
            f"/api/v1/settings/novels/{novel_id}",
            json={"autosave_interval": 9999},
            headers=auth_headers,
        )
        assert response.status_code == 422
