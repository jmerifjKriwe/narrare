"""Integration tests for generation API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from narrare_core.llm.intents import ResolvedModelConfig
from narrare_core.llm.result import LLMResult, TokenUsage

if TYPE_CHECKING:
    from httpx import AsyncClient


# Shared mock data for LLM name generation response
_MOCK_NAMES_JSON = (
    '{"names": ['
    '{"name": "Aelindra", "pronunciation": "ay-LIN-drah", "meaning": "starlight wanderer"},'
    '{"name": "Thormund", "pronunciation": "THOR-mund", "meaning": "thunder protector"},'
    '{"name": "Zephyra", "pronunciation": "zeh-FEER-ah", "meaning": "west wind"}'
    "]}"
)


@pytest.fixture
def _mock_gateway() -> MagicMock:
    """Create a mock LLMGateway that returns structured name data."""
    gateway = MagicMock()  # narrare: allow reason="Mocking LLMGateway for integration test"
    gateway.run = AsyncMock(
        return_value=LLMResult(
            text=_MOCK_NAMES_JSON,
            usage=TokenUsage(prompt_tokens=50, completion_tokens=100, total_tokens=150),
            model="claude-haiku",
            intent="name_generate",
        ),
    )
    return gateway


class TestGenerateNames:
    async def test_generate_names_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST /generation/names with valid request returns names."""
        from narrare._app.dependencies import _get_composer_instance
        from narrare.generation.name_service import NameGeneratorService
        from narrare.generation.router import _get_service as original_factory

        # Override the service factory to inject mock gateway
        mock_gw = _mock_gateway()

        mock_config = ResolvedModelConfig(
            provider_name="anthropic",
            model_id="claude-haiku-3-5-20241022",
            temperature=0.8,
            max_tokens=2000,
        )

        mock_service = NameGeneratorService(
            gateway=mock_gw,
            composer=_get_composer_instance(),
            config=mock_config,
        )

        app = client._transport.app  # type: ignore[reportUnknownMemberType]

        app.dependency_overrides[original_factory] = lambda: mock_service

        try:
            response = await client.post(
                "/api/v1/generation/names",
                json={
                    "project_id": str(uuid4()),
                    "name_type": "character",
                    "culture": "fantasy",
                    "count": 3,
                    "gender": "any",
                    "language": "en",
                },
                headers=auth_headers,
            )
            assert response.status_code == 200
            data = response.json()
            assert "names" in data
            assert "count" in data
            assert "culture" in data
            assert "name_type" in data
            assert data["culture"] == "fantasy"
            assert data["name_type"] == "character"
        finally:
            app.dependency_overrides.pop(original_factory, None)

    async def test_generate_names_count_over_50_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST /generation/names with count=100 returns 422 (validation)."""
        response = await client.post(
            "/api/v1/generation/names",
            json={
                "project_id": str(uuid4()),
                "name_type": "character",
                "culture": "fantasy",
                "count": 100,
                "gender": "any",
                "language": "en",
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_generate_names_invalid_name_type_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST /generation/names with invalid name_type returns 422."""
        response = await client.post(
            "/api/v1/generation/names",
            json={
                "project_id": str(uuid4()),
                "name_type": "invalid_type",
                "culture": "fantasy",
                "count": 5,
                "gender": "any",
                "language": "en",
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_generate_names_without_auth_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        """POST /generation/names without auth returns 401."""
        response = await client.post(
            "/api/v1/generation/names",
            json={
                "project_id": str(uuid4()),
                "name_type": "character",
                "culture": "fantasy",
                "count": 5,
            },
        )
        assert response.status_code == 401

    async def test_generate_names_missing_project_id_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST /generation/names without project_id returns 422."""
        response = await client.post(
            "/api/v1/generation/names",
            json={
                "name_type": "character",
                "culture": "fantasy",
                "count": 5,
            },
            headers=auth_headers,
        )
        assert response.status_code == 422
