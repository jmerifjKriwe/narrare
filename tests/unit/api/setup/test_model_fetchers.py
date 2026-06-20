"""Unit tests for setup/_model_fetchers.py — delegates to ModelCatalogClient.

Updated for CR-AUFG-08-06: ``fetch_models`` now returns ``FetchResult``
(models + ``used_fallback`` flag) so ``ProviderService.list_models`` can
label response provenance.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from narrare.setup._model_fetchers import FetchResult
from narrare.setup.base_schemas import AIProvider
from narrare.setup.provider_schemas import ProviderModel
from narrare_core.llm.model_listing import (
    ModelCatalogClient,
    ModelCatalogEntry,
    ModelCatalogError,
)


def _make_entries(*entries: dict[str, Any]) -> list[ModelCatalogEntry]:
    """Build a list of ModelCatalogEntry from dicts."""
    return [ModelCatalogEntry(**e) for e in entries]


def _mock_catalog(return_value: list[ModelCatalogEntry]) -> MagicMock:
    """Build a mock ModelCatalogClient whose list_models returns *return_value*."""
    mock = MagicMock(spec=ModelCatalogClient)
    mock.list_models = AsyncMock(return_value=return_value)
    return mock


# ---------------------------------------------------------------------------
# Per-provider dispatch
# ---------------------------------------------------------------------------


async def test_fetch_models_anthropic() -> None:
    """Anthropic provider dispatches correctly and maps entries."""
    from narrare.setup._model_fetchers import fetch_models

    entries = _make_entries(
        {"id": "claude-3-opus", "name": "Claude 3 Opus", "context_window": 200000},
        {"id": "claude-3-sonnet", "name": "Claude 3 Sonnet"},
    )
    mock = _mock_catalog(entries)

    with patch("narrare.setup._model_fetchers.ModelCatalogClient", return_value=mock):
        result = await fetch_models(AIProvider.ANTHROPIC, "sk-test", "", {})

    assert isinstance(result, FetchResult)
    assert result.used_fallback is False
    assert len(result.models) == 2
    assert result.models[0].id == "claude-3-opus"
    assert result.models[0].name == "Claude 3 Opus"
    assert result.models[0].context_window == 200000
    assert result.models[1].id == "claude-3-sonnet"
    mock.list_models.assert_awaited_once_with(
        "anthropic",
        api_key="sk-test",
        base_url=None,
    )


async def test_fetch_models_openai() -> None:
    """OpenAI provider dispatches correctly."""
    from narrare.setup._model_fetchers import fetch_models

    entries = _make_entries({"id": "gpt-4o", "name": "gpt-4o"})
    mock = _mock_catalog(entries)

    with patch("narrare.setup._model_fetchers.ModelCatalogClient", return_value=mock):
        result = await fetch_models(AIProvider.OPENAI, "sk-test", "", {})

    assert result.used_fallback is False
    assert len(result.models) == 1
    assert result.models[0].id == "gpt-4o"
    mock.list_models.assert_awaited_once_with(
        "openai",
        api_key="sk-test",
        base_url=None,
    )


async def test_fetch_models_ollama_passes_base_url() -> None:
    """Ollama provider passes base_url to catalog."""
    from narrare.setup._model_fetchers import fetch_models

    entries = _make_entries(
        {"id": "llama3.2", "name": "llama3.2", "context_window": 128000},
    )
    mock = _mock_catalog(entries)

    with patch("narrare.setup._model_fetchers.ModelCatalogClient", return_value=mock):
        result = await fetch_models(
            AIProvider.OLLAMA,
            "",
            "http://custom:11434",
            {},
        )

    assert result.used_fallback is False
    assert len(result.models) == 1
    assert result.models[0].context_window == 128000
    mock.list_models.assert_awaited_once_with(
        "ollama",
        api_key=None,
        base_url="http://custom:11434",
    )


async def test_fetch_models_openrouter() -> None:
    """OpenRouter provider dispatches correctly."""
    from narrare.setup._model_fetchers import fetch_models

    entries = _make_entries({"id": "model-1", "name": "Model 1"})
    mock = _mock_catalog(entries)

    with patch("narrare.setup._model_fetchers.ModelCatalogClient", return_value=mock):
        result = await fetch_models(AIProvider.OPENROUTER, "sk-test", "", {})

    assert result.used_fallback is False
    assert len(result.models) == 1
    mock.list_models.assert_awaited_once_with(
        "openrouter",
        api_key="sk-test",
        base_url=None,
    )


async def test_fetch_models_google() -> None:
    """Google provider dispatches correctly."""
    from narrare.setup._model_fetchers import fetch_models

    entries = _make_entries(
        {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash", "context_window": 1000000},
    )
    mock = _mock_catalog(entries)

    with patch("narrare.setup._model_fetchers.ModelCatalogClient", return_value=mock):
        result = await fetch_models(AIProvider.GOOGLE, "key", "", {})

    assert result.used_fallback is False
    assert len(result.models) == 1
    assert result.models[0].id == "gemini-2.0-flash"
    assert result.models[0].context_window == 1000000


async def test_fetch_models_groq() -> None:
    """Groq provider dispatches correctly."""
    from narrare.setup._model_fetchers import fetch_models

    entries = _make_entries(
        {"id": "llama-3.3-70b-versatile", "name": "llama-3.3-70b-versatile"},
    )
    mock = _mock_catalog(entries)

    with patch("narrare.setup._model_fetchers.ModelCatalogClient", return_value=mock):
        result = await fetch_models(AIProvider.GROQ, "gsk_test", "", {})

    assert result.used_fallback is False
    assert len(result.models) == 1
    assert result.models[0].id == "llama-3.3-70b-versatile"


async def test_fetch_models_zai() -> None:
    """ZAI provider dispatches correctly."""
    from narrare.setup._model_fetchers import fetch_models

    entries = _make_entries({"id": "glm-4", "name": "glm-4"})
    mock = _mock_catalog(entries)

    with patch("narrare.setup._model_fetchers.ModelCatalogClient", return_value=mock):
        result = await fetch_models(AIProvider.ZAI, "sk-test", "", {})

    assert result.used_fallback is False
    assert len(result.models) == 1
    assert result.models[0].id == "glm-4"


# ---------------------------------------------------------------------------
# Fallback behavior
# ---------------------------------------------------------------------------


async def test_fetch_models_fallback_on_api_error() -> None:
    """Falls back to hardcoded models on generic API error."""
    from narrare.setup._model_fetchers import fetch_models

    mock = MagicMock(spec=ModelCatalogClient)
    mock.list_models = AsyncMock(side_effect=Exception("API unreachable"))

    fallback_models = [ProviderModel(id="fallback-a", name="Fallback A")]
    fallback: dict[AIProvider, list[ProviderModel]] = {
        AIProvider.ANTHROPIC: fallback_models,
    }

    with patch("narrare.setup._model_fetchers.ModelCatalogClient", return_value=mock):
        result = await fetch_models(AIProvider.ANTHROPIC, "key", "", fallback)

    assert isinstance(result, FetchResult)
    assert result.used_fallback is True
    assert result.models == fallback_models
    assert result.models[0].id == "fallback-a"


async def test_fetch_models_fallback_on_catalog_error() -> None:
    """Falls back on ModelCatalogError (HTTP error, unsupported provider)."""
    from narrare.setup._model_fetchers import fetch_models

    mock = MagicMock(spec=ModelCatalogClient)
    mock.list_models = AsyncMock(
        side_effect=ModelCatalogError("anthropic", "HTTP 401"),
    )

    fallback_models = [ProviderModel(id="fallback", name="Fallback")]
    fallback: dict[AIProvider, list[ProviderModel]] = {
        AIProvider.ANTHROPIC: fallback_models,
    }

    with patch("narrare.setup._model_fetchers.ModelCatalogClient", return_value=mock):
        result = await fetch_models(AIProvider.ANTHROPIC, "key", "", fallback)

    assert result.used_fallback is True
    assert result.models == fallback_models


async def test_fetch_models_fallback_empty_when_no_entry() -> None:
    """Returns empty list when provider has no fallback entry and catalog fails."""
    from narrare.setup._model_fetchers import fetch_models

    mock = MagicMock(spec=ModelCatalogClient)
    mock.list_models = AsyncMock(side_effect=Exception("fail"))

    with patch("narrare.setup._model_fetchers.ModelCatalogClient", return_value=mock):
        result = await fetch_models(AIProvider.ANTHROPIC, "key", "", {})

    assert result.used_fallback is True
    assert result.models == []


async def test_fetch_models_empty_result() -> None:
    """Returns empty list (non-fallback) when provider returns no models."""
    from narrare.setup._model_fetchers import fetch_models

    mock = _mock_catalog([])

    with patch("narrare.setup._model_fetchers.ModelCatalogClient", return_value=mock):
        result = await fetch_models(AIProvider.GOOGLE, "key", "", {})

    assert result.used_fallback is False
    assert result.models == []
