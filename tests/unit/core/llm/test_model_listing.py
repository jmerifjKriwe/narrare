"""Tests for core/llm/model_listing.py — schemas, protocol, and providers.

Split per RULE-04 (file size limits).  See also:
- ``test_model_listing_errors.py`` — error handling tests
"""

from __future__ import annotations

import pytest

from narrare_core.llm.contracts import ModelCatalogProtocol
from narrare_core.llm.model_listing import (
    SUPPORTED_CATALOG_PROVIDERS,
    ModelCatalogClient,
    ModelCatalogEntry,
    ModelCatalogError,
)

from ._model_listing_helpers import make_mock_response, patch_httpx_client

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def catalog() -> ModelCatalogClient:
    return ModelCatalogClient()


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestModelCatalogEntry:
    """Tests for the ModelCatalogEntry Pydantic model."""

    def test_minimal_fields(self) -> None:
        entry = ModelCatalogEntry(id="gpt-4", name="GPT-4")
        assert entry.id == "gpt-4"
        assert entry.name == "GPT-4"
        assert entry.context_window is None

    def test_all_fields(self) -> None:
        entry = ModelCatalogEntry(
            id="claude-3",
            name="Claude 3",
            context_window=200000,
        )
        assert entry.context_window == 200000

    def test_serialization_round_trip(self) -> None:
        entry = ModelCatalogEntry(id="test", name="Test", context_window=4096)
        restored = ModelCatalogEntry.model_validate(entry.model_dump())
        assert restored == entry


class TestModelCatalogError:
    """Tests for ModelCatalogError."""

    def test_message_format(self) -> None:
        err = ModelCatalogError("openai", "HTTP 401")
        assert "openai" in str(err)
        assert "HTTP 401" in str(err)

    def test_attributes(self) -> None:
        err = ModelCatalogError("anthropic", "timeout")
        assert err.provider == "anthropic"
        assert err.detail == "timeout"

    def test_is_exception(self) -> None:
        assert isinstance(ModelCatalogError("test", "detail"), Exception)


# ---------------------------------------------------------------------------
# Protocol & supported providers
# ---------------------------------------------------------------------------


class TestProtocolCompliance:
    def test_runtime_checkable(self) -> None:
        assert isinstance(ModelCatalogClient(), ModelCatalogProtocol)


class TestSupportedProviders:
    def test_all_providers_present(self) -> None:
        expected = {
            "anthropic",
            "openai",
            "ollama",
            "google",
            "groq",
            "openrouter",
            "zai",
        }
        assert expected == SUPPORTED_CATALOG_PROVIDERS

    def test_is_frozenset(self) -> None:
        assert isinstance(SUPPORTED_CATALOG_PROVIDERS, frozenset)


# ---------------------------------------------------------------------------
# Unsupported provider
# ---------------------------------------------------------------------------


class TestUnsupportedProvider:
    @pytest.mark.asyncio
    async def test_unknown_raises(self, catalog: ModelCatalogClient) -> None:
        with pytest.raises(ModelCatalogError, match="Unsupported provider"):
            await catalog.list_models("unknown_provider")

    @pytest.mark.asyncio
    async def test_empty_raises(self, catalog: ModelCatalogClient) -> None:
        with pytest.raises(ModelCatalogError):
            await catalog.list_models("")


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------


_ANTHROPIC_DATA = {
    "data": [
        {
            "id": "claude-sonnet-4-20250514",
            "display_name": "Claude Sonnet 4",
            "context_window": 200000,
        },
        {"id": "some-other-model", "display_name": "Other"},
    ]
}


class TestAnthropic:
    @pytest.mark.asyncio
    async def test_filters_claude_only(self, catalog: ModelCatalogClient) -> None:
        resp = make_mock_response(_ANTHROPIC_DATA)
        async with patch_httpx_client(resp):
            models = await catalog.list_models("anthropic", api_key="sk-test")
        ids = [m.id for m in models]
        assert "claude-sonnet-4-20250514" in ids
        assert "some-other-model" not in ids

    @pytest.mark.asyncio
    async def test_display_name_and_context_window(
        self,
        catalog: ModelCatalogClient,
    ) -> None:
        resp = make_mock_response(_ANTHROPIC_DATA)
        async with patch_httpx_client(resp):
            models = await catalog.list_models("anthropic", api_key="sk-test")
        m = models[0]
        assert m.name == "Claude Sonnet 4"
        assert m.context_window == 200000

    @pytest.mark.asyncio
    async def test_fallback_to_id_when_no_display_name(
        self,
        catalog: ModelCatalogClient,
    ) -> None:
        data = {"data": [{"id": "claude-foo"}]}
        resp = make_mock_response(data)
        async with patch_httpx_client(resp):
            models = await catalog.list_models("anthropic", api_key="sk-test")
        assert models[0].name == "claude-foo"

    @pytest.mark.asyncio
    async def test_case_insensitive(self, catalog: ModelCatalogClient) -> None:
        resp = make_mock_response(_ANTHROPIC_DATA)
        async with patch_httpx_client(resp):
            models = await catalog.list_models("Anthropic", api_key="sk-test")
        assert len(models) == 1


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------


_OPENAI_DATA = {
    "data": [
        {"id": "gpt-4o"},
        {"id": "gpt-3.5-turbo"},
        {"id": "o3-mini"},
        {"id": "dall-e-3"},
        {"id": "text-embedding-3-small"},
    ]
}


class TestOpenAI:
    @pytest.mark.asyncio
    async def test_filters_chat_models(self, catalog: ModelCatalogClient) -> None:
        resp = make_mock_response(_OPENAI_DATA)
        async with patch_httpx_client(resp):
            models = await catalog.list_models("openai", api_key="sk-test")
        ids = [m.id for m in models]
        assert "gpt-4o" in ids
        assert "gpt-3.5-turbo" in ids
        assert "o3-mini" in ids
        assert "dall-e-3" not in ids
        assert "text-embedding-3-small" not in ids

    @pytest.mark.asyncio
    async def test_name_equals_id(self, catalog: ModelCatalogClient) -> None:
        resp = make_mock_response(_OPENAI_DATA)
        async with patch_httpx_client(resp):
            models = await catalog.list_models("openai", api_key="sk-test")
        assert all(m.name == m.id for m in models)


# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------


_OLLAMA_DATA = {
    "models": [
        {"name": "llama3:latest", "details": {"context_length": 8192}},
        {"name": "codellama:latest"},
    ]
}


class TestOllama:
    @pytest.mark.asyncio
    async def test_lists_models_with_context(
        self,
        catalog: ModelCatalogClient,
    ) -> None:
        resp = make_mock_response(_OLLAMA_DATA)
        async with patch_httpx_client(resp):
            models = await catalog.list_models("ollama")
        by_id = {m.id: m for m in models}
        assert by_id["llama3:latest"].context_window == 8192
        assert by_id["codellama:latest"].context_window is None

    @pytest.mark.asyncio
    async def test_default_base_url(self, catalog: ModelCatalogClient) -> None:
        from unittest.mock import patch

        from ._model_listing_helpers import FakeAsyncClient

        captured_url: str = ""

        def _capture_get(url: object, **kw: object) -> object:
            nonlocal captured_url
            captured_url = str(url)
            return make_mock_response({"models": []})

        fake = FakeAsyncClient(_capture_get)
        with patch(
            "narrare_core.llm.model_listing.httpx.AsyncClient",
            return_value=fake,
        ):
            await catalog.list_models("ollama")

        assert captured_url == "http://localhost:11434/api/tags"

    @pytest.mark.asyncio
    async def test_custom_base_url(self, catalog: ModelCatalogClient) -> None:
        from unittest.mock import patch

        from ._model_listing_helpers import FakeAsyncClient

        captured_url: str = ""

        def _capture_get(url: object, **kw: object) -> object:
            nonlocal captured_url
            captured_url = str(url)
            return make_mock_response({"models": []})

        fake = FakeAsyncClient(_capture_get)
        with patch(
            "narrare_core.llm.model_listing.httpx.AsyncClient",
            return_value=fake,
        ):
            await catalog.list_models("ollama", base_url="http://myserver:1234/")

        assert captured_url == "http://myserver:1234/api/tags"

    @pytest.mark.asyncio
    async def test_no_api_key_needed(self, catalog: ModelCatalogClient) -> None:
        resp = make_mock_response({"models": []})
        async with patch_httpx_client(resp):
            models = await catalog.list_models("ollama")
        assert models == []
