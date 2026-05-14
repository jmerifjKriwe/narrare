"""Integration tests for auth endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare.auth.schemas import TokenResponse, UserResponse

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestRegister:
    async def test_register_returns_tokens(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "new@example.com",
                "password": "password123",
            },
        )
        assert response.status_code == 201
        data = response.json()
        validated = TokenResponse.model_validate(data)
        assert validated.access_token
        assert validated.refresh_token
        assert validated.token_type == "bearer"

    async def test_register_duplicate_email_returns_409(self, client: AsyncClient) -> None:
        payload = {"email": "dup@example.com", "password": "password123"}
        await client.post("/api/v1/auth/register", json=payload)
        response = await client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 409

    async def test_register_short_password_returns_422(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "short@example.com",
                "password": "abc",
            },
        )
        assert response.status_code == 422

    async def test_register_invalid_email_returns_422(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "password": "password123",
            },
        )
        assert response.status_code == 422


class TestLogin:
    async def test_login_valid_credentials_returns_tokens(self, client: AsyncClient) -> None:
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "login@example.com",
                "password": "password123",
            },
        )
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "login@example.com",
                "password": "password123",
            },
        )
        assert response.status_code == 200
        validated = TokenResponse.model_validate(response.json())
        assert validated.access_token

    async def test_login_wrong_password_returns_401(self, client: AsyncClient) -> None:
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "wrongpw@example.com",
                "password": "correctpassword",
            },
        )
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "wrongpw@example.com",
                "password": "wrongpassword",
            },
        )
        assert response.status_code == 401

    async def test_login_unknown_email_returns_401(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "nobody@example.com",
                "password": "password123",
            },
        )
        assert response.status_code == 401


class TestRefresh:
    async def test_refresh_valid_token_returns_new_tokens(self, client: AsyncClient) -> None:
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "refresh@example.com",
                "password": "password123",
            },
        )
        refresh_token = reg.json()["refresh_token"]
        response = await client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token": refresh_token,
            },
        )
        assert response.status_code == 200
        validated = TokenResponse.model_validate(response.json())
        assert validated.access_token

    async def test_refresh_invalid_token_returns_401(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token": "not.a.valid.token",
            },
        )
        assert response.status_code == 401


class TestGetCurrentUser:
    async def test_me_returns_user_profile(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        validated = UserResponse.model_validate(data)
        assert validated.id
        assert validated.email

    async def test_me_without_token_returns_401(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401


class TestHasProviders:
    async def test_me_without_setup_has_providers_false(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """New user with no providers has has_providers=False."""
        response = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["has_providers"] is False

    async def test_me_after_setup_has_providers_true(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """After completing setup, has_providers becomes True."""
        # Complete setup first
        setup_response = await client.post(
            "/api/v1/setup/complete",
            json={
                "state": {
                    "project_name": "Provider Test",
                    "language": "en",
                    "autosave_interval": 30,
                    "title": "Test Novel",
                    "author": "Test",
                    "genre": "fantasy",
                    "logline": "Test",
                    "story_structure": "three_act",
                    "tone": "dramatic",
                    "starter": "blank",
                    "import_path": None,
                    "provider": "anthropic",
                    "api_key": "sk-test-key",
                    "model": "claude-haiku",
                    "ollama_url": "http://localhost:11434",
                    "zai_endpoint": "general",
                }
            },
            headers=auth_headers,
        )
        assert setup_response.status_code == 200

        # Now check /auth/me
        response = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["has_providers"] is True
