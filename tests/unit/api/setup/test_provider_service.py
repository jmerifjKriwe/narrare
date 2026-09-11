"""Unit tests for setup/provider_service.py — model fetching and validation.

Updated for CR-AUFG-08-06: ``_fetch_models`` returns ``FetchResult``
(models + ``used_fallback`` flag). Provenance tests live in
``test_setup_catalog_provenance.py``.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic_ai.models.test import TestModel

from narrare.setup._model_fetchers import FetchResult
from narrare.setup.base_schemas import AIProvider
from narrare.setup.provider_schemas import AvailableModelsResponse, ProviderModel
from narrare.setup.provider_service import ProviderService


@pytest.fixture
def service() -> ProviderService:
    return ProviderService()


def _ok_model() -> TestModel:
    """Deterministic pydantic-ai model — no network, always replies "OK"."""
    return TestModel(custom_output_text="OK")


# ---------------------------------------------------------------------------
# list_models
# ---------------------------------------------------------------------------


class TestProviderServiceListModels:
    async def test_returns_fetched_models_on_success(self, service: ProviderService) -> None:
        mock_result = FetchResult(
            models=[ProviderModel(id="claude-3", name="Claude 3")],
            used_fallback=False,
        )
        with patch.object(
            service, "_fetch_models", new_callable=AsyncMock, return_value=mock_result
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
        mock_result = FetchResult(models=[], used_fallback=False)
        with patch.object(
            service, "_fetch_models", new_callable=AsyncMock, return_value=mock_result
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
        mock_result = FetchResult(
            models=[ProviderModel(id="test-model", name="Test")],
            used_fallback=False,
        )
        with patch(
            "narrare.setup.provider_service.fetch_models",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_fetch:
            result = await service._fetch_models(AIProvider.OPENAI, "sk-test", "")

        assert isinstance(result, FetchResult)
        assert result.models[0].id == "test-model"
        assert result.used_fallback is False
        # Verify delegation happened with correct positional args
        call_args = mock_fetch.call_args
        assert call_args[0][0] == AIProvider.OPENAI
        assert call_args[0][1] == "sk-test"
        assert call_args[0][2] == ""
        # Fourth arg is _FALLBACK_MODELS dict — verify it's populated
        assert len(call_args[0][3]) > 0


# ---------------------------------------------------------------------------
# _test_call — per-request credential pass-through
#
# Regression (benchmark finding #5, KB rehearsal spec §6): the previous
# implementation mutated ``os.environ`` and called provider factories bare.
# ``get_core_settings()`` is lru-cached (ADR-071) and instantiated at startup,
# so env writes after startup are invisible — zai step-4 validation failed
# with "Missing credentials ... OPENAI_API_KEY" despite a valid key.
# The registry contract (ProviderFactory) documents per-request pass-through
# via ``factory(model_id, api_key=..., base_url=...)``.
# ---------------------------------------------------------------------------


class TestProviderServiceTestCallCredentialPassthrough:
    """_test_call must pass credentials per-request to the provider factories."""

    async def test_passes_api_key_to_zai_coding_factory(self, service: ProviderService) -> None:
        with patch(
            "narrare_core.llm._providers.zai.make_zai_coding",
            return_value=_ok_model(),
        ) as mock_zai_coding:
            await service._test_call(
                AIProvider.ZAI, "zai-key-123", "glm-4-flash", "", zai_endpoint="coding"
            )

        mock_zai_coding.assert_called_once_with("glm-4-flash", api_key="zai-key-123")

    async def test_passes_api_key_to_registry_factory(self, service: ProviderService) -> None:
        mock_factory = Mock(return_value=_ok_model())
        with patch("narrare_core.llm._providers.registry.get", return_value=mock_factory):
            await service._test_call(AIProvider.OPENAI, "sk-key-123", "gpt-4o", "")

        mock_factory.assert_called_once_with("gpt-4o", api_key="sk-key-123")

    async def test_passes_ollama_url_as_base_url(self, service: ProviderService) -> None:
        """Ollama has no key — the URL must reach the factory via base_url."""
        mock_factory = Mock(return_value=_ok_model())
        with patch("narrare_core.llm._providers.registry.get", return_value=mock_factory):
            await service._test_call(AIProvider.OLLAMA, "", "llama3.2", "http://my-ollama:11434")

        mock_factory.assert_called_once_with("llama3.2", base_url="http://my-ollama:11434")

    @pytest.mark.parametrize(
        ("provider", "env_var"),
        [
            (AIProvider.ANTHROPIC, "ANTHROPIC_API_KEY"),
            (AIProvider.OPENAI, "OPENAI_API_KEY"),
            (AIProvider.ZAI, "ZAI_API_KEY"),
            (AIProvider.OLLAMA, "OLLAMA_BASE_URL"),
        ],
    )
    async def test_does_not_mutate_environ(
        self,
        service: ProviderService,
        monkeypatch: pytest.MonkeyPatch,
        provider: AIProvider,
        env_var: str,
    ) -> None:
        """_test_call is forbidden from writing credentials into os.environ."""
        monkeypatch.delenv(env_var, raising=False)
        mock_factory = Mock(return_value=_ok_model())
        with patch("narrare_core.llm._providers.registry.get", return_value=mock_factory):
            await service._test_call(provider, "cred-value", "some-model", "http://ollama:11434")

        assert env_var not in os.environ
