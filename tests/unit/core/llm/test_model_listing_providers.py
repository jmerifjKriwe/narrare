"""Tests for core/llm/model_listing.py — Google, Groq, OpenRouter, Z.AI providers.

Split per RULE-04 (file size limits).  See also:
- ``test_model_listing.py`` — core schema, protocol, Anthropic, OpenAI, Ollama tests
- ``test_model_listing_errors.py`` — error handling tests
"""

from __future__ import annotations

import pytest

from narrare_core.llm.model_listing import (
    _OPENROUTER_MAX_MODELS,
    ModelCatalogClient,
)

from ._model_listing_helpers import make_mock_response, patch_httpx_client


@pytest.fixture
def catalog() -> ModelCatalogClient:
    return ModelCatalogClient()


# ---------------------------------------------------------------------------
# Google
# ---------------------------------------------------------------------------


_GOOGLE_DATA = {
    "models": [
        {
            "name": "models/gemini-2.0-flash",
            "displayName": "Gemini 2.0 Flash",
            "supportedGenerationMethods": ["generateContent", "countTokens"],
            "inputTokenLimit": 1048576,
        },
        {
            "name": "models/text-embedding-004",
            "supportedGenerationMethods": ["embedContent"],
        },
    ]
}


class TestGoogle:
    @pytest.mark.asyncio
    async def test_filters_generate_content(
        self,
        catalog: ModelCatalogClient,
    ) -> None:
        resp = make_mock_response(_GOOGLE_DATA)
        async with patch_httpx_client(resp):
            models = await catalog.list_models("google", api_key="AIzaTest")
        ids = [m.id for m in models]
        assert "gemini-2.0-flash" in ids
        assert "text-embedding-004" not in ids

    @pytest.mark.asyncio
    async def test_strips_models_prefix(
        self,
        catalog: ModelCatalogClient,
    ) -> None:
        resp = make_mock_response(_GOOGLE_DATA)
        async with patch_httpx_client(resp):
            models = await catalog.list_models("google", api_key="AIzaTest")
        assert all(not m.id.startswith("models/") for m in models)

    @pytest.mark.asyncio
    async def test_context_window_and_display_name(
        self,
        catalog: ModelCatalogClient,
    ) -> None:
        resp = make_mock_response(_GOOGLE_DATA)
        async with patch_httpx_client(resp):
            models = await catalog.list_models("google", api_key="AIzaTest")
        m = models[0]
        assert m.context_window == 1048576
        assert m.name == "Gemini 2.0 Flash"

    @pytest.mark.asyncio
    async def test_fallback_to_id_no_display_name(
        self,
        catalog: ModelCatalogClient,
    ) -> None:
        data = {
            "models": [
                {
                    "name": "models/test-model",
                    "supportedGenerationMethods": ["generateContent"],
                }
            ]
        }
        resp = make_mock_response(data)
        async with patch_httpx_client(resp):
            models = await catalog.list_models("google", api_key="AIzaTest")
        assert models[0].name == "test-model"


# ---------------------------------------------------------------------------
# Groq
# ---------------------------------------------------------------------------


_GROQ_DATA = {
    "data": [
        {"id": "mixtral-8x7b-32768"},
        {"id": "llama-3.3-70b-versatile"},
    ]
}


class TestGroq:
    @pytest.mark.asyncio
    async def test_lists_models(self, catalog: ModelCatalogClient) -> None:
        resp = make_mock_response(_GROQ_DATA)
        async with patch_httpx_client(resp):
            models = await catalog.list_models("groq", api_key="gsk_test")
        assert len(models) == 2
        assert models[0].id == "mixtral-8x7b-32768"

    @pytest.mark.asyncio
    async def test_name_equals_id(self, catalog: ModelCatalogClient) -> None:
        resp = make_mock_response(_GROQ_DATA)
        async with patch_httpx_client(resp):
            models = await catalog.list_models("groq", api_key="gsk_test")
        assert all(m.name == m.id for m in models)


# ---------------------------------------------------------------------------
# OpenRouter
# ---------------------------------------------------------------------------


_OPENROUTER_DATA = {
    "data": [
        {
            "id": "anthropic/claude-3.5-sonnet",
            "name": "Claude 3.5 Sonnet",
            "context_length": 200000,
        },
        {"id": "openai/gpt-4o", "name": "GPT-4o", "context_length": 128000},
    ]
}


class TestOpenRouter:
    @pytest.mark.asyncio
    async def test_lists_models(self, catalog: ModelCatalogClient) -> None:
        resp = make_mock_response(_OPENROUTER_DATA)
        async with patch_httpx_client(resp):
            models = await catalog.list_models("openrouter", api_key="sk-or-test")
        assert len(models) == 2
        assert models[0].context_window == 200000

    @pytest.mark.asyncio
    async def test_caps_at_max_models(self, catalog: ModelCatalogClient) -> None:
        many = {"data": [{"id": f"model-{i}", "name": f"M{i}"} for i in range(50)]}
        resp = make_mock_response(many)
        async with patch_httpx_client(resp):
            models = await catalog.list_models("openrouter", api_key="sk-or-test")
        assert len(models) == _OPENROUTER_MAX_MODELS

    @pytest.mark.asyncio
    async def test_fallback_to_id_when_no_name(
        self,
        catalog: ModelCatalogClient,
    ) -> None:
        data = {"data": [{"id": "test/model"}]}
        resp = make_mock_response(data)
        async with patch_httpx_client(resp):
            models = await catalog.list_models("openrouter", api_key="sk-or-test")
        assert models[0].name == "test/model"


# ---------------------------------------------------------------------------
# Z.AI
# ---------------------------------------------------------------------------


_ZAI_DATA = {"data": [{"id": "glm-4"}, {"id": "glm-4-flash"}]}


class TestZAI:
    @pytest.mark.asyncio
    async def test_lists_models(self, catalog: ModelCatalogClient) -> None:
        resp = make_mock_response(_ZAI_DATA)
        async with patch_httpx_client(resp):
            models = await catalog.list_models("zai", api_key="zai-test")
        assert len(models) == 2
        assert models[0].id == "glm-4"

    @pytest.mark.asyncio
    async def test_name_defaults_to_id(self, catalog: ModelCatalogClient) -> None:
        resp = make_mock_response(_ZAI_DATA)
        async with patch_httpx_client(resp):
            models = await catalog.list_models("zai", api_key="zai-test")
        assert all(m.name == m.id for m in models)
