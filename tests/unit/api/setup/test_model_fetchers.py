"""Unit tests for setup/_model_fetchers.py — provider-specific model fetching."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from narrare.setup.base_schemas import AIProvider
from narrare.setup.provider_schemas import ProviderModel


def _make_mock_client(mock_response: MagicMock) -> MagicMock:
    """Build a mock httpx.AsyncClient that returns *mock_response* on GET."""
    # narrare: allow  reason="Mocking httpx.AsyncClient infrastructure for provider API calls"
    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


def _make_mock_response(json_data: dict[str, object]) -> MagicMock:
    """Build a mock httpx.Response with .json() returning *json_data*."""
    # narrare: allow  reason="Mocking httpx.AsyncClient infrastructure for provider API calls"
    mock_response = MagicMock()
    # narrare: allow  reason="Mocking httpx.AsyncClient infrastructure for provider API calls"
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = json_data
    return mock_response


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------


async def test_fetch_anthropic_models() -> None:
    from narrare.setup._model_fetchers import _fetch_anthropic_models

    mock_response = _make_mock_response(
        {
            "data": [
                {"id": "claude-3-opus", "display_name": "Claude 3 Opus", "context_window": 200000},
                {"id": "some-other-model"},
            ]
        }
    )
    mock_client = _make_mock_client(mock_response)

    result = await _fetch_anthropic_models(mock_client, "sk-test")
    assert len(result) == 1
    assert result[0].id == "claude-3-opus"
    assert result[0].context_window == 200000


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------


async def test_fetch_openai_models() -> None:
    from narrare.setup._model_fetchers import _fetch_openai_models

    mock_response = _make_mock_response(
        {
            "data": [
                {"id": "gpt-4o"},
                {"id": "gpt-3.5-turbo"},
                {"id": "o3-mini"},
                {"id": "dall-e-3"},
            ]
        }
    )
    mock_client = _make_mock_client(mock_response)

    result = await _fetch_openai_models(mock_client, "sk-test")
    assert len(result) == 3


# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------


async def test_fetch_ollama_models() -> None:
    from narrare.setup._model_fetchers import _fetch_ollama_models

    mock_response = _make_mock_response(
        {
            "models": [
                {"name": "llama3.2", "details": {"context_length": 128000}},
                {"name": "mistral", "details": {}},
            ]
        }
    )
    mock_client = _make_mock_client(mock_response)

    result = await _fetch_ollama_models(mock_client, "http://localhost:11434")
    assert len(result) == 2
    assert result[0].id == "llama3.2"
    assert result[0].context_window == 128000


# ---------------------------------------------------------------------------
# OpenRouter
# ---------------------------------------------------------------------------


async def test_fetch_openrouter_models() -> None:
    from narrare.setup._model_fetchers import _fetch_openrouter_models

    models_data = [{"id": f"model-{i}", "name": f"Model {i}"} for i in range(50)]
    mock_response = _make_mock_response({"data": models_data})
    mock_client = _make_mock_client(mock_response)

    result = await _fetch_openrouter_models(mock_client, "sk-test")
    assert len(result) == 30  # Limited to 30


# ---------------------------------------------------------------------------
# Z.AI
# ---------------------------------------------------------------------------


async def test_fetch_zai_models() -> None:
    from narrare.setup._model_fetchers import _fetch_zai_models

    mock_response = _make_mock_response({"data": [{"id": "glm-4"}, {"id": "glm-z1"}]})
    mock_client = _make_mock_client(mock_response)

    result = await _fetch_zai_models(mock_client, "sk-test")
    assert len(result) == 2


# ---------------------------------------------------------------------------
# Google
# ---------------------------------------------------------------------------


async def test_fetch_google_models() -> None:
    """Google fetcher should strip 'models/' prefix and filter embeddings."""
    from narrare.setup._model_fetchers import _fetch_google_models

    mock_response = _make_mock_response(
        {
            "models": [
                {
                    "name": "models/gemini-2.0-flash",
                    "displayName": "Gemini 2.0 Flash",
                    "inputTokenLimit": 1000000,
                    "supportedGenerationMethods": ["generateContent"],
                },
                {
                    "name": "models/gemini-1.5-pro",
                    "displayName": "Gemini 1.5 Pro",
                    "inputTokenLimit": 2000000,
                    "supportedGenerationMethods": ["generateContent"],
                },
                {
                    "name": "models/text-embedding-004",
                    "displayName": "Text Embedding",
                    "supportedGenerationMethods": ["embedContent"],
                },
            ]
        }
    )
    mock_client = _make_mock_client(mock_response)

    result = await _fetch_google_models(mock_client, "fake-key")
    assert len(result) == 2  # Embedding model filtered out
    assert result[0].id == "gemini-2.0-flash"
    assert result[0].name == "Gemini 2.0 Flash"
    assert result[0].context_window == 1000000
    assert result[1].id == "gemini-1.5-pro"
    assert result[1].context_window == 2000000


async def test_fetch_google_models_empty_response() -> None:
    """Google fetcher should handle empty model list gracefully."""
    from narrare.setup._model_fetchers import _fetch_google_models

    mock_response = _make_mock_response({"models": []})
    mock_client = _make_mock_client(mock_response)

    result = await _fetch_google_models(mock_client, "fake-key")
    assert result == []


# ---------------------------------------------------------------------------
# Groq
# ---------------------------------------------------------------------------


async def test_fetch_groq_models() -> None:
    """Groq fetcher uses OpenAI-compatible endpoint."""
    from narrare.setup._model_fetchers import _fetch_groq_models

    mock_response = _make_mock_response(
        {
            "data": [
                {"id": "llama-3.3-70b-versatile"},
                {"id": "mixtral-8x7b-32768"},
            ]
        }
    )
    mock_client = _make_mock_client(mock_response)

    result = await _fetch_groq_models(mock_client, "gsk_test")
    assert len(result) == 2
    assert result[0].id == "llama-3.3-70b-versatile"
    assert result[1].id == "mixtral-8x7b-32768"


# ---------------------------------------------------------------------------
# Dispatcher (fetch_models)
# ---------------------------------------------------------------------------


async def test_fetch_models_dispatches_to_google() -> None:
    """Dispatcher routes GOOGLE provider to _fetch_google_models."""
    from narrare.setup._model_fetchers import fetch_models

    mock_response = _make_mock_response(
        {
            "models": [
                {
                    "name": "models/gemini-2.0-flash",
                    "displayName": "Gemini 2.0 Flash",
                    "inputTokenLimit": 1000000,
                    "supportedGenerationMethods": ["generateContent"],
                },
            ]
        }
    )
    mock_client = _make_mock_client(mock_response)

    with patch("narrare.setup._model_fetchers.httpx.AsyncClient", return_value=mock_client):
        result = await fetch_models(AIProvider.GOOGLE, "key", "", {})

    assert len(result) == 1
    assert result[0].id == "gemini-2.0-flash"


async def test_fetch_models_dispatches_to_groq() -> None:
    """Dispatcher routes GROQ provider to _fetch_groq_models."""
    from narrare.setup._model_fetchers import fetch_models

    mock_response = _make_mock_response({"data": [{"id": "llama-3.3-70b-versatile"}]})
    mock_client = _make_mock_client(mock_response)

    with patch("narrare.setup._model_fetchers.httpx.AsyncClient", return_value=mock_client):
        result = await fetch_models(AIProvider.GROQ, "key", "", {})

    assert len(result) == 1
    assert result[0].id == "llama-3.3-70b-versatile"


async def test_fetch_models_fallback_on_api_error() -> None:
    """Service-level fallback is used when the provider API call fails."""
    from narrare.setup._model_fetchers import fetch_models

    # narrare: allow  reason="Mocking httpx.AsyncClient infrastructure for provider API calls"
    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=Exception("API unreachable"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    fallback_models = [ProviderModel(id="fallback-a", name="Fallback A")]
    fallback: dict[AIProvider, list[ProviderModel]] = {
        AIProvider.ANTHROPIC: fallback_models,
    }

    with (
        patch("narrare.setup._model_fetchers.httpx.AsyncClient", return_value=mock_client),
        pytest.raises(Exception, match="API unreachable"),
    ):
        await fetch_models(AIProvider.ANTHROPIC, "key", "", fallback)

    # Note: fallback at the fetch_models level is only for providers without
    # a fetcher route. API errors propagate to the service, which applies
    # _FALLBACK_MODELS — tested in test_provider_service.py.
