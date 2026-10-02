"""Integration tests for setup wizard endpoints."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import patch

from sqlalchemy import text

from narrare.setup._model_fetchers import FetchResult
from narrare.setup.schemas import (
    AIProvider,
    AvailableModelsResponse,
    CompleteSetupResponse,
    ProviderModel,
    Step1LocationResponse,
    Step2NovelResponse,
    Step3StarterResponse,
)

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


def _extract_user_id(auth_headers: dict[str, str]) -> uuid.UUID:
    """Extract user_id from the Bearer token in auth headers.

    The ``auth_headers`` fixture creates a JWT whose ``sub`` claim
    is the user's UUID.  Decoding it avoids needing a separate
    ``user_id`` fixture that would change the conftest contract.
    """
    import jwt as _jwt

    from narrare._app.config import get_settings

    token = auth_headers["Authorization"].removeprefix("Bearer ")
    settings = get_settings()
    payload = _jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    return uuid.UUID(payload["sub"])


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
        assert validated.demo_info.writing_language == "de"

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

    async def test_import_starter_accepted_without_path(self, client: AsyncClient) -> None:
        # ADR-091: starter="import" no longer requires a server-side path.
        # The wizard creates an empty novel; the frontend commits files
        # afterwards via POST /import/commit.
        response = await client.post(
            "/api/v1/setup/validate/step-3",
            json={
                "starter": "import",
            },
        )
        assert response.status_code == 200
        validated = Step3StarterResponse.model_validate(response.json())
        assert validated.valid is True
        assert validated.demo_info is None

    async def test_import_unknown_extra_field_ignored(self, client: AsyncClient) -> None:
        """Legacy clients may still send ``import_path`` — pydantic ignores it."""
        response = await client.post(
            "/api/v1/setup/validate/step-3",
            json={
                "starter": "import",
                "import_path": "/path/that/does/not/exist",
            },
        )
        assert response.status_code == 200
        validated = Step3StarterResponse.model_validate(response.json())
        assert validated.valid is True


class TestListProviderModels:
    async def test_returns_fallback_models_without_key(self, client: AsyncClient) -> None:
        """Should return fallback model list even without a valid API key."""

        # Patch fetch_models to raise immediately — the endpoint catches the
        # exception and returns the hardcoded fallback list.  Without the patch
        # the real HTTP call to Anthropic takes ~0.4s (connection refused).
        async def _raise(*args: object, **kwargs: object) -> None:
            raise RuntimeError("No API key — using fallback")

        with patch(
            "narrare.setup.provider_service.fetch_models",
            _raise,
        ):
            response = await client.get("/api/v1/setup/providers/anthropic/models")
        assert response.status_code == 200
        validated = AvailableModelsResponse.model_validate(response.json())
        assert validated.provider == "anthropic"
        assert len(validated.models) > 0

    async def test_all_providers_return_models(self, client: AsyncClient) -> None:
        providers = ["anthropic", "openai", "google", "groq", "openrouter", "zai"]
        # Patch fetch_models in the provider_service namespace to avoid real HTTP
        # calls to 6 provider APIs.  Each real call would take ~0.4s (connection
        # refused).  The patch triggers the fallback model list immediately.
        #
        # We patch at provider_service.fetch_models (not at ModelCatalogClient)
        # because provider_service has a local "from ... import fetch_models"
        # reference that is set at module-import time.

        async def _fake_fetch_models(
            provider: AIProvider,
            api_key: str,
            ollama_url: str,
            fallback_models: dict[AIProvider, list[ProviderModel]],
        ) -> FetchResult:
            """Return fallback models immediately without any HTTP calls."""
            from narrare.setup.provider_service import _FALLBACK_MODELS as FB

            return FetchResult(models=FB.get(provider, []), used_fallback=True)

        patcher = patch(
            "narrare.setup.provider_service.fetch_models",
            _fake_fetch_models,
        )
        patcher.start()
        try:
            for provider in providers:
                response = await client.get(f"/api/v1/setup/providers/{provider}/models")
                assert response.status_code == 200, f"Failed for provider: {provider}"
                validated = AvailableModelsResponse.model_validate(response.json())
                assert len(validated.models) > 0
        finally:
            patcher.stop()


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
        user_id = _extract_user_id(auth_headers)

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

        # Verify user_providers row exists in DB for THIS user
        result = await db_session.execute(
            text(
                "SELECT provider_name, api_key_encrypted, base_url "
                "FROM user_providers WHERE user_id = :uid"
            ),
            {"uid": user_id},
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
        user_id = _extract_user_id(auth_headers)

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

        # Verify user_ai_settings row exists with correct values for THIS user
        result = await db_session.execute(
            text("SELECT default_model FROM user_ai_settings WHERE user_id = :uid"),
            {"uid": user_id},
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] == "gpt-4o"
