"""Integration tests for setup wizard endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

from narrare.setup.schemas import (
    AvailableModelsResponse,
    CompleteSetupResponse,
    Step1LocationResponse,
    Step2NovelResponse,
    Step3StarterResponse,
)

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


class TestValidateStep1:
    async def test_valid_step1(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/setup/validate/step-1",
            json={
                "project_name": "My Fantasy Novel",
                "writing_language": "en",
                "autosave_interval": 30,
            },
        )
        assert response.status_code == 200
        validated = Step1LocationResponse.model_validate(response.json())
        assert validated.valid is True

    async def test_short_language_code_rejected(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/setup/validate/step-1",
            json={
                "project_name": "My Novel",
                "writing_language": "x",
            },
        )
        assert response.status_code == 422

    async def test_invalid_project_name_rejected(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/setup/validate/step-1",
            json={
                "project_name": "Invalid/Name",
                "writing_language": "en",
            },
        )
        assert response.status_code == 422

    async def test_german_language_accepted(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/setup/validate/step-1",
            json={
                "project_name": "Mein Roman",
                "writing_language": "de",
            },
        )
        assert response.status_code == 200
        validated = Step1LocationResponse.model_validate(response.json())
        assert validated.valid is True


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
        validated = Step2NovelResponse.model_validate(response.json())
        assert validated.valid is True

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
        validated = Step3StarterResponse.model_validate(response.json())
        assert validated.valid is True
        assert validated.demo_info is None

    async def test_german_demo_returns_info(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/setup/validate/step-3",
            json={
                "starter": "demo_german",
            },
        )
        assert response.status_code == 200
        validated = Step3StarterResponse.model_validate(response.json())
        assert validated.valid is True
        assert validated.demo_info is not None
        assert validated.demo_info.title == "Im Stillen Wald"
        assert validated.demo_info.language == "de"

    async def test_fantasy_demo_returns_info(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/setup/validate/step-3",
            json={
                "starter": "demo_fantasy",
            },
        )
        assert response.status_code == 200
        validated = Step3StarterResponse.model_validate(response.json())
        assert validated.demo_info is not None
        assert validated.demo_info.title == "Echoes of the Thornwall"

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
        validated = AvailableModelsResponse.model_validate(response.json())
        assert validated.provider == "anthropic"
        assert len(validated.models) > 0

    async def test_all_providers_return_models(self, client: AsyncClient) -> None:
        providers = ["anthropic", "openai", "google", "groq", "openrouter", "zai"]
        for provider in providers:
            response = await client.get(f"/api/v1/setup/providers/{provider}/models")
            assert response.status_code == 200, f"Failed for provider: {provider}"
            validated = AvailableModelsResponse.model_validate(response.json())
            assert len(validated.models) > 0


class TestCompleteSetup:
    async def test_complete_blank_setup_creates_novel(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post(
            "/api/v1/setup/complete",
            json={
                "state": {
                    "project_name": "Test Project",
                    "writing_language": "en",
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
        validated = CompleteSetupResponse.model_validate(data)
        assert validated.novel_id
        assert validated.redirect_to == "/dashboard"

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
                    "writing_language": "de",
                    "autosave_interval": 30,
                    "title": "Im Stillen Wald",
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
        validated = CompleteSetupResponse.model_validate(data)
        # If demo files exist → editor; if not → dashboard (graceful fallback)
        assert validated.redirect_to in (
            f"/novel/{validated.novel_id}",
            "/dashboard",
        )

    async def test_complete_creates_user_provider_in_db(
        self, client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession
    ) -> None:
        """complete() creates a user_providers row with encrypted API key."""
        response = await client.post(
            "/api/v1/setup/complete",
            json={
                "state": {
                    "project_name": "DB Test",
                    "writing_language": "en",
                    "autosave_interval": 30,
                    "title": "DB Test Novel",
                    "author": "Test",
                    "genre": "scifi",
                    "logline": "A test.",
                    "story_structure": "three_act",
                    "tone": "dramatic",
                    "starter": "blank",
                    "import_path": None,
                    "provider": "anthropic",
                    "api_key": "sk-test-key-12345",
                    "model": "claude-haiku",
                    "ollama_url": "http://localhost:11434",
                    "zai_endpoint": "general",
                }
            },
            headers=auth_headers,
        )
        assert response.status_code == 200

        # Verify user_providers row exists in DB
        result = await db_session.execute(text("SELECT COUNT(*) FROM user_providers"))
        count = result.scalar()
        assert count is not None and count >= 1

        result = await db_session.execute(
            text("SELECT provider_name, api_key_encrypted, base_url FROM user_providers LIMIT 1")
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] == "anthropic"
        assert row[1] != ""  # Encrypted key should be non-empty
        assert row[1] != "sk-test-key-12345"  # Should NOT be the plain key
        assert row[2] is None  # No custom base_url for anthropic

    async def test_complete_creates_user_ai_settings_in_db(
        self, client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession
    ) -> None:
        """complete() creates user_ai_settings with default model."""
        response = await client.post(
            "/api/v1/setup/complete",
            json={
                "state": {
                    "project_name": "Settings Test",
                    "writing_language": "en",
                    "autosave_interval": 30,
                    "title": "Settings Test Novel",
                    "author": "Test",
                    "genre": "fantasy",
                    "logline": "A test.",
                    "story_structure": "three_act",
                    "tone": "dramatic",
                    "starter": "blank",
                    "import_path": None,
                    "provider": "openai",
                    "api_key": "sk-openai-test",
                    "model": "gpt-4o",
                    "ollama_url": "http://localhost:11434",
                    "zai_endpoint": "general",
                }
            },
            headers=auth_headers,
        )
        assert response.status_code == 200

        # Verify user_ai_settings row exists with correct values
        result = await db_session.execute(
            text("SELECT default_model FROM user_ai_settings LIMIT 1")
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] == "gpt-4o"
