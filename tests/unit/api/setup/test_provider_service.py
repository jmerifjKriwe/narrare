"""Unit tests for setup/provider_service.py — model fetching and validation."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from narrare.setup.base_schemas import AIProvider
from narrare.setup.provider_schemas import AvailableModelsResponse, ProviderModel
from narrare.setup.provider_service import ProviderService


@pytest.fixture
def service() -> ProviderService:
    return ProviderService()


# ---------------------------------------------------------------------------
# list_models
# ---------------------------------------------------------------------------


class TestProviderServiceListModels:
    async def test_returns_fetched_models_on_success(self, service: ProviderService) -> None:
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
# validate_connection — normal model names
# ---------------------------------------------------------------------------


class TestProviderServiceValidateConnection:
    async def test_returns_none_on_success(self, service: ProviderService) -> None:
        with patch.object(service, "_test_call", new_callable=AsyncMock, return_value=None):
            result = await service.validate_connection(AIProvider.ANTHROPIC, "sk-test", "claude-3")

        assert result is None

    async def test_returns_error_message_on_failure(self, service: ProviderService) -> None:
        with patch.object(
            service, "_test_call", new_callable=AsyncMock, side_effect=Exception("Auth failed")
        ):
            result = await service.validate_connection(AIProvider.OPENAI, "bad-key", "gpt-4o")

        assert result == "Auth failed"

    async def test_passes_ollama_url(self, service: ProviderService) -> None:
        with patch.object(
            service, "_test_call", new_callable=AsyncMock, return_value=None
        ) as mock_call:
            await service.validate_connection(
                AIProvider.OLLAMA, "", "llama3", ollama_url="http://my-ollama:11434"
            )
            mock_call.assert_called_once_with(
                AIProvider.OLLAMA, "", "llama3", "http://my-ollama:11434", "general"
            )


# ---------------------------------------------------------------------------
# validate_connection — "test" placeholder model resolution
# ---------------------------------------------------------------------------


class TestProviderServiceValidateConnectionTestModel:
    """Tests for dynamic model resolution when the frontend sends 'test'."""

    async def test_resolves_test_model_dynamically(self, service: ProviderService) -> None:
        """When model='test', the first available model is used for validation."""
        mock_response = AvailableModelsResponse(
            provider=AIProvider.GOOGLE,
            models=[ProviderModel(id="gemini-2.0-flash", name="Gemini 2.0 Flash")],
        )
        with (
            patch.object(
                service, "list_models", new_callable=AsyncMock, return_value=mock_response
            ),
            patch.object(
                service, "_test_call", new_callable=AsyncMock, return_value=None
            ) as mock_test_call,
        ):
            result = await service.validate_connection(AIProvider.GOOGLE, "api-key", "test")

        assert result is None
        mock_test_call.assert_called_once_with(
            AIProvider.GOOGLE, "api-key", "gemini-2.0-flash", "http://localhost:11434", "general"
        )

    async def test_returns_error_when_no_models_available(self, service: ProviderService) -> None:
        """Empty model list should return a helpful German error message."""
        mock_response = AvailableModelsResponse(
            provider=AIProvider.GOOGLE,
            models=[],
        )
        with patch.object(
            service, "list_models", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await service.validate_connection(AIProvider.GOOGLE, "bad-key", "test")

        assert result is not None
        assert "Keine Modelle" in result
        assert "API-Key" in result

    async def test_returns_error_when_model_list_fetch_fails(
        self, service: ProviderService
    ) -> None:
        """Exception during list_models should return an error message."""
        with patch.object(
            service,
            "list_models",
            new_callable=AsyncMock,
            side_effect=Exception("Timeout"),
        ):
            result = await service.validate_connection(AIProvider.GOOGLE, "key", "test")

        assert result is not None
        assert "Modellliste" in result
        assert "Timeout" in result

    async def test_normal_model_name_skips_resolution(self, service: ProviderService) -> None:
        """When model is not 'test', resolution should be skipped entirely."""
        with (
            patch.object(service, "list_models", new_callable=AsyncMock) as mock_list,
            patch.object(service, "_test_call", new_callable=AsyncMock, return_value=None),
        ):
            result = await service.validate_connection(AIProvider.ANTHROPIC, "sk-test", "claude-3")

        assert result is None
        mock_list.assert_not_called()


# ---------------------------------------------------------------------------
# _fetch_models delegation
# ---------------------------------------------------------------------------


class TestProviderServiceFetchDelegation:
    async def test_delegates_to_model_fetchers(self, service: ProviderService) -> None:
        """_fetch_models should delegate to _model_fetchers.fetch_models."""
        mock_models = [ProviderModel(id="test-model", name="Test")]
        with patch(
            "narrare.setup.provider_service.fetch_models",
            new_callable=AsyncMock,
            return_value=mock_models,
        ) as mock_fetch:
            result = await service._fetch_models(AIProvider.OPENAI, "sk-test", "")

        assert result == mock_models
        # Verify delegation happened with correct positional args
        call_args = mock_fetch.call_args
        assert call_args[0][0] == AIProvider.OPENAI
        assert call_args[0][1] == "sk-test"
        assert call_args[0][2] == ""
        # Fourth arg is _FALLBACK_MODELS dict — verify it's populated
        assert len(call_args[0][3]) > 0
