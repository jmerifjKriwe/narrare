"""Integration tests for generation API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from narrare._app.dependencies import _get_composer_instance
from narrare.generation.name_service import NameGeneratorService
from narrare_core.llm import ResolvedModelConfig
from tests.fakes.fake_llm_gateway import FakeModelRegistry

if TYPE_CHECKING:
    from httpx import AsyncClient

    from narrare.novels.contracts import NovelRepositoryProtocol

# Shared mock data for LLM name generation response
_MOCK_NAMES_JSON = (
    '{"names": ['
    '{"name": "Aelindra", "pronunciation": "ay-LIN-drah", "meaning": "starlight wanderer"},'
    '{"name": "Thormund", "pronunciation": "THOR-mund", "meaning": "thunder protector"},'
    '{"name": "Zephyra", "pronunciation": "zeh-FEER-ah", "meaning": "west wind"}'
    "]}"
)


class _PermissiveNovelRepo:
    """Owns everything — random test project ids pass the S12b gate."""

    async def get_by_id(self, novel_id: object, user_id: object) -> object:
        return object()


@pytest.fixture
def mock_registry() -> FakeModelRegistry:
    """Fake ModelRegistry that returns structured name data."""
    registry = FakeModelRegistry()
    registry.returns(_MOCK_NAMES_JSON)
    return registry


class TestGenerateNames:
    async def test_generate_names_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        mock_registry: FakeModelRegistry,
    ) -> None:
        """POST /generation/names with valid request returns names."""
        mock_config = ResolvedModelConfig(
            provider_name="anthropic",
            model_id="claude-haiku-3-5-20241022",
            temperature=0.8,
            max_tokens=2000,
        )

        # Use FakeModelRegistry — its run() signature matches the
        # positional-arg call in NameGeneratorService.generate_names().
        # _get_service is patched away, so the factory-level S12b gate is
        # bypassed here — the permissive novel repo keeps the service-level
        # gate satisfied for the random test project id.
        mock_service = NameGeneratorService(
            registry=mock_registry,
            composer=_get_composer_instance(),
            config=mock_config,
            # Minimal fake — cast at the construction seam (house pattern).
            novel_repo=cast("NovelRepositoryProtocol", _PermissiveNovelRepo()),
        )

        # _get_service is called directly in the route handler (not via
        # Depends), so dependency_overrides cannot intercept it.
        # Patch the module-level function instead.
        with patch(
            "narrare.generation.router._get_service",
            new_callable=AsyncMock,
            return_value=mock_service,
        ):
            response = await client.post(
                "/api/v1/generation/names",
                json={
                    "project_id": str(uuid4()),
                    "name_type": "character",
                    "name_style": "fantasy",
                    "count": 3,
                    "gender": "any",
                    "explanation_language": "en",
                },
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert "names" in data
        assert "count" in data
        assert "name_style" in data
        assert "name_type" in data
        assert data["name_style"] == "fantasy"
        assert data["name_type"] == "character"

    async def test_generate_names_count_over_50_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        response = await client.post(
            "/api/v1/generation/names",
            json={
                "project_id": str(uuid4()),
                "name_type": "character",
                "name_style": "fantasy",
                "count": 100,
                "gender": "any",
                "explanation_language": "en",
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_generate_names_invalid_name_type_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        response = await client.post(
            "/api/v1/generation/names",
            json={
                "project_id": str(uuid4()),
                "name_type": "invalid_type",
                "name_style": "fantasy",
                "count": 5,
                "gender": "any",
                "explanation_language": "en",
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_generate_names_without_auth_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        response = await client.post(
            "/api/v1/generation/names",
            json={
                "project_id": str(uuid4()),
                "name_type": "character",
                "name_style": "fantasy",
                "count": 5,
            },
        )
        assert response.status_code == 401

    async def test_generate_names_missing_project_id_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        response = await client.post(
            "/api/v1/generation/names",
            json={
                "name_type": "character",
                "name_style": "fantasy",
                "count": 5,
            },
            headers=auth_headers,
        )
        assert response.status_code == 422
