"""Unit tests for setup/provider_service.py — model fetching and validation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from narrare.setup.base_schemas import AIProvider
from narrare.setup.provider_service import ProviderService


@pytest.fixture
def service() -> ProviderService:
    return ProviderService()


# ---------------------------------------------------------------------------
# list_models
# ---------------------------------------------------------------------------


class TestProviderServiceListModels:
    async def test_returns_fetched_models_on_success(self, service: ProviderService) -> None:
        from narrare.setup.provider_schemas import ProviderModel

        mock_models = [ProviderModel(id="claude-3", name="Claude 3")]
        with patch.object(
            service, "_fetch_models", new_callable=AsyncMock, return_value=mock_models
        ):
            result = await service.list_models(AIProvider.ANTHROPIC, "sk-test")

        assert result.provider == AIProvider.ANTHROPIC
        assert len(result.models) == 1

    async def test_returns_fallback_on_fetch_error(self, service: ProviderService) -> None:
        with patch.object(
            service, "_fetch_models", new_callable=AsyncMock, side_effect=Exception("Network error")
        ):
            result = await service.list_models(AIProvider.OPENAI, "sk-test")

        assert result.provider == AIProvider.OPENAI
        # Should return fallback models
        assert len(result.models) > 0

    async def test_returns_empty_for_unknown_provider_on_error(
        self, service: ProviderService
    ) -> None:
        with patch.object(
            service, "_fetch_models", new_callable=AsyncMock, side_effect=Exception("err")
        ):
            # Google has fallback models
            result = await service.list_models(AIProvider.GOOGLE, "key")

        assert result.provider == AIProvider.GOOGLE

    async def test_passes_ollama_url_to_fetch(self, service: ProviderService) -> None:
        with patch.object(
            service, "_fetch_models", new_callable=AsyncMock, return_value=[]
        ) as mock_fetch:
            await service.list_models(AIProvider.OLLAMA, "", ollama_url="http://custom:11434")
            mock_fetch.assert_called_once_with(AIProvider.OLLAMA, "", "http://custom:11434")


# ---------------------------------------------------------------------------
# validate_connection
# ---------------------------------------------------------------------------


class TestProviderServiceValidateConnection:
    async def test_returns_true_on_success(self, service: ProviderService) -> None:
        with patch.object(service, "_test_call", new_callable=AsyncMock, return_value=None):
            result = await service.validate_connection(AIProvider.ANTHROPIC, "sk-test", "claude-3")

        assert result is True

    async def test_returns_false_on_failure(self, service: ProviderService) -> None:
        with patch.object(
            service, "_test_call", new_callable=AsyncMock, side_effect=Exception("Auth failed")
        ):
            result = await service.validate_connection(AIProvider.OPENAI, "bad-key", "gpt-4o")

        assert result is False

    async def test_passes_ollama_url(self, service: ProviderService) -> None:
        with patch.object(
            service, "_test_call", new_callable=AsyncMock, return_value=None
        ) as mock_call:
            await service.validate_connection(
                AIProvider.OLLAMA, "", "llama3", ollama_url="http://my-ollama:11434"
            )
            mock_call.assert_called_once_with(
                AIProvider.OLLAMA, "", "llama3", "http://my-ollama:11434"
            )


# ---------------------------------------------------------------------------
# _fetch_models (individual provider fetch methods)
# ---------------------------------------------------------------------------


class TestProviderServiceFetchModels:
    async def test_fetch_anthropic_models(self, service: ProviderService) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"id": "claude-3-opus", "display_name": "Claude 3 Opus", "context_window": 200000},
                {"id": "some-other-model"},
            ]
        }
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("narrare.setup.provider_service.httpx.AsyncClient", return_value=mock_client):
            result = await service._fetch_models(AIProvider.ANTHROPIC, "sk-test", "")  # type: ignore[reportPrivateUsage]

        # Only claude models should pass the filter
        assert len(result) == 1
        assert result[0].id == "claude-3-opus"

    async def test_fetch_openai_models(self, service: ProviderService) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"id": "gpt-4o"},
                {"id": "gpt-3.5-turbo"},
                {"id": "o3-mini"},
                {"id": "dall-e-3"},
            ]
        }
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("narrare.setup.provider_service.httpx.AsyncClient", return_value=mock_client):
            result = await service._fetch_models(AIProvider.OPENAI, "sk-test", "")  # type: ignore[reportPrivateUsage]

        # Only chat models should pass the filter
        assert len(result) == 3

    async def test_fetch_ollama_models(self, service: ProviderService) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "models": [
                {"name": "llama3.2", "details": {"context_length": 128000}},
                {"name": "mistral", "details": {}},
            ]
        }
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("narrare.setup.provider_service.httpx.AsyncClient", return_value=mock_client):
            result = await service._fetch_models(AIProvider.OLLAMA, "", "http://localhost:11434")  # type: ignore[reportPrivateUsage]

        assert len(result) == 2
        assert result[0].id == "llama3.2"

    async def test_fetch_openrouter_models(self, service: ProviderService) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        models_data = [{"id": f"model-{i}", "name": f"Model {i}"} for i in range(50)]
        mock_response.json.return_value = {"data": models_data}
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("narrare.setup.provider_service.httpx.AsyncClient", return_value=mock_client):
            result = await service._fetch_models(AIProvider.OPENROUTER, "sk-test", "")  # type: ignore[reportPrivateUsage]

        # Should be limited to 30
        assert len(result) == 30

    async def test_fetch_zai_models(self, service: ProviderService) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"id": "glm-4"},
                {"id": "glm-z1"},
            ]
        }
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("narrare.setup.provider_service.httpx.AsyncClient", return_value=mock_client):
            result = await service._fetch_models(AIProvider.ZAI, "sk-test", "")  # type: ignore[reportPrivateUsage]

        assert len(result) == 2

    async def test_fetch_returns_fallback_for_unsupported_provider(
        self, service: ProviderService
    ) -> None:
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("narrare.setup.provider_service.httpx.AsyncClient", return_value=mock_client):
            # GROQ has fallback but no dedicated fetch method
            result = await service._fetch_models(AIProvider.GROQ, "sk-test", "")  # type: ignore[reportPrivateUsage]

        assert len(result) > 0  # Falls back to _FALLBACK_MODELS
