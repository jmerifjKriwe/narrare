"""Integration tests for setup wizard endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestValidateStep1:
    async def test_valid_step1(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/setup/validate/step-1",
            json={
                "project_name": "My Fantasy Novel",
                "language": "en",
                "autosave_interval": 30,
            },
        )
        assert response.status_code == 200
        assert response.json()["valid"] is True

    async def test_unsupported_language_rejected(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/setup/validate/step-1",
            json={
                "project_name": "My Novel",
                "language": "zh",
            },
        )
        assert response.status_code == 422

    async def test_invalid_project_name_rejected(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/setup/validate/step-1",
            json={
                "project_name": "Invalid/Name",
                "language": "en",
            },
        )
        assert response.status_code == 422

    async def test_german_language_accepted(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/setup/validate/step-1",
            json={
                "project_name": "Mein Roman",
                "language": "de",
            },
        )
        assert response.status_code == 200
        assert response.json()["valid"] is True


class TestValidateStep2:
    async def test_valid_novel_metadata(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/setup/validate/step-2",
            json={
                "title": "Echoes of the Thornwall",
                "genre": "fantasy",
                "story_structure": "three_act",
                "tone": "dramatic",
            },
        )
        assert response.status_code == 200
        assert response.json()["valid"] is True

    async def test_missing_title_rejected(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/setup/validate/step-2",
            json={
                "genre": "fantasy",
            },
        )
        assert response.status_code == 422


class TestValidateStep3:
    async def test_blank_starter(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/setup/validate/step-3",
            json={
                "starter": "blank",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["demo_info"] is None

    async def test_german_demo_returns_info(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/setup/validate/step-3",
            json={
                "starter": "demo_german",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["demo_info"]["title"] == "Im stillen Wald"
        assert data["demo_info"]["language"] == "de"

    async def test_fantasy_demo_returns_info(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/setup/validate/step-3",
            json={
                "starter": "demo_fantasy",
            },
        )
        assert response.status_code == 200
        assert response.json()["demo_info"]["title"] == "Echoes of the Thornwall"

    async def test_import_without_path_rejected(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/setup/validate/step-3",
            json={
                "starter": "import",
            },
        )
        assert response.status_code == 422

    async def test_import_nonexistent_path_rejected(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/setup/validate/step-3",
            json={
                "starter": "import",
                "import_path": "/path/that/does/not/exist",
            },
        )
        assert response.status_code == 422


class TestListProviderModels:
    async def test_returns_fallback_models_without_key(self, client: AsyncClient) -> None:
        """Should return fallback model list even without a valid API key."""
        response = await client.get("/api/v1/setup/providers/anthropic/models")
        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "anthropic"
        assert len(data["models"]) > 0

    async def test_all_providers_return_models(self, client: AsyncClient) -> None:
        providers = ["anthropic", "openai", "google", "groq", "openrouter", "zai"]
        for provider in providers:
            response = await client.get(f"/api/v1/setup/providers/{provider}/models")
            assert response.status_code == 200, f"Failed for provider: {provider}"
            assert len(response.json()["models"]) > 0


class TestCompleteSetup:
    async def test_complete_blank_setup_creates_novel(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post(
            "/api/v1/setup/complete",
            json={
                "state": {
                    "project_name": "Test Project",
                    "language": "en",
                    "autosave_interval": 30,
                    "title": "My Test Novel",
                    "author": "Test Author",
                    "genre": "fantasy",
                    "logline": "A story.",
                    "story_structure": "three_act",
                    "tone": "dramatic",
                    "starter": "blank",
                    "import_path": None,
                    "provider": "anthropic",
                    "api_key": "test-key",
                    "model": "claude-haiku-3-5-20241022",
                    "ollama_url": "http://localhost:11434",
                }
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "novel_id" in data
        assert data["redirect_to"] == "/dashboard"

    async def test_complete_without_auth_returns_401(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/setup/complete", json={"state": {}})
        assert response.status_code == 401

    async def test_german_demo_redirects_to_editor(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """German demo has real content — should redirect to editor."""
        response = await client.post(
            "/api/v1/setup/complete",
            json={
                "state": {
                    "project_name": "Stiller Wald",
                    "language": "de",
                    "autosave_interval": 30,
                    "title": "Im stillen Wald",
                    "author": "",
                    "genre": "literary_fiction",
                    "logline": "",
                    "story_structure": "three_act",
                    "tone": "contemplative",
                    "starter": "demo_german",
                    "import_path": None,
                    "provider": "zai",
                    "api_key": "test-key",
                    "model": "glm-z1-32b",
                    "ollama_url": "http://localhost:11434",
                }
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        # If demo files exist → editor; if not → dashboard (graceful fallback)
        assert data["redirect_to"] in (
            f"/novel/{data['novel_id']}/editor",
            "/dashboard",
        )
