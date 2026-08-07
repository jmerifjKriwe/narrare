"""Tests for the E2E model-catalog stub — ``ModelCatalogClient`` in E2E mode.

When ``NARRARE_E2E_TEST`` is set, ``ModelCatalogClient.list_models`` returns a
deterministic canned catalog instead of issuing a real HTTP call to a provider
catalog endpoint (e.g. ``GET https://api.anthropic.com/v1/models``). This is the
model-catalog analogue of ``TestModel`` (the LLM stub exercised in
``test_providers_registry.py::TestE2ETestMode``) and ``TestEmbeddingProvider``
(``test_embedding_e2e_stub.py``) and keeps end-to-end tests hermetic — no
network, deterministic model lists.

These tests were split out of ``test_model_listing.py`` to keep the E2E-stub
behaviour assertions co-located with the sibling embedding-stub tests. The
non-E2E catalog tests (schema, providers, errors) remain in the sibling files.

Context: the setup wizard's step-4 provider validation used to leak a real
``GET https://api.anthropic.com/v1/models`` (401 on a dummy key) during E2E.
Playwright route mocks only intercept browser→backend requests; the backend's
own outbound HTTP needed a production-side guard at the single catalog choke
point — the same ``e2e_test`` switch the other three core stubs use
(TestModel, TestEmbeddingProvider, NullMemoryClient).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from narrare_core.llm.model_listing import (
    SUPPORTED_CATALOG_PROVIDERS,
    ModelCatalogClient,
    ModelCatalogEntry,
    ModelCatalogError,
)


class TestModelCatalogE2ETestMode:
    """When NARRARE_E2E_TEST is set, list_models() returns a deterministic
    catalog and never touches ``httpx`` — no real provider catalog calls.

    Mirrors ``TestEmbeddingProviderE2ETestMode`` in
    ``test_embedding_e2e_stub.py`` and ``TestE2ETestMode`` in
    ``test_providers_registry.py`` (the TestModel override). This is the E2E
    stub for the model-catalog gateway, completing the fourth core leak guard
    alongside TestModel / TestEmbeddingProvider / NullMemoryClient.
    """

    @pytest.fixture(autouse=True)
    def _set_e2e_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NARRARE_E2E_TEST", "1")

    async def test_returns_test_catalog_for_known_provider(self) -> None:
        catalog = ModelCatalogClient()
        models = await catalog.list_models("anthropic", api_key="dummy")

        assert len(models) >= 1
        assert all(isinstance(m, ModelCatalogEntry) for m in models)
        # Clearly-marked test id so it can never be confused with a real model.
        assert "test" in models[0].id.lower()

    async def test_e2e_does_not_touch_httpx(self) -> None:
        """In E2E mode, list_models returns entries and never constructs an
        ``httpx.AsyncClient`` — proves the Anthropic/OpenAI catalog leak is
        sealed at the production choke point, not just at the test boundary."""
        catalog = ModelCatalogClient()
        with patch("narrare_core.llm.model_listing.httpx.AsyncClient") as mock_client:
            models = await catalog.list_models("anthropic", api_key="sk-test-dummy")

        mock_client.assert_not_called()
        assert len(models) >= 1

    async def test_catalog_is_deterministic(self) -> None:
        """Same provider yields the same catalog across calls (keeps the
        wizard model-selection flow reproducible in E2E)."""
        catalog = ModelCatalogClient()
        first = await catalog.list_models("openai", api_key="k1")
        second = await catalog.list_models("openai", api_key="k2")

        assert first == second
        assert first  # non-empty

    async def test_e2e_ignores_credentials_and_base_url(self) -> None:
        """The E2E override must not depend on api_key/base_url — mirroring
        TestE2ETestMode.test_e2e_factory_ignores_credentials for the LLM
        registry. Dummy/empty credentials still yield a catalog."""
        catalog = ModelCatalogClient()
        with patch("narrare_core.llm.model_listing.httpx.AsyncClient") as mock_client:
            # Ollama path normally uses base_url; all cloud paths use api_key.
            # In E2E mode neither matters.
            models_no_key = await catalog.list_models("openai")
            models_ollama = await catalog.list_models("ollama", base_url="http://x:1")

        mock_client.assert_not_called()
        assert len(models_no_key) >= 1
        assert len(models_ollama) >= 1

    async def test_e2e_still_raises_for_unsupported_provider(self) -> None:
        """The unsupported-provider check runs before the E2E override
        (mirrors embedding_providers.get KeyError ordering), so unknown names
        still raise even in E2E mode."""
        catalog = ModelCatalogClient()
        with pytest.raises(ModelCatalogError, match="Unsupported provider"):
            await catalog.list_models("__nonexistent_e2e_provider__")

    async def test_all_supported_providers_return_nonempty_catalog(self) -> None:
        """Every supported catalog provider gets at least one entry in E2E
        mode — the wizard auto-selects the first model, so an empty list would
        block the step-4 flow."""
        catalog = ModelCatalogClient()
        for provider in SUPPORTED_CATALOG_PROVIDERS:
            models = await catalog.list_models(provider, api_key="dummy")
            assert models, f"E2E catalog for {provider!r} must not be empty"

    async def test_returns_fresh_list_copy(self) -> None:
        """Mutating the returned list must not corrupt the module-level test
        catalog (``_test_catalog`` returns ``list(...)`` for isolation)."""
        catalog = ModelCatalogClient()
        first = await catalog.list_models("anthropic", api_key="dummy")
        snapshot = list(first)
        first.clear()
        second = await catalog.list_models("anthropic", api_key="dummy")

        assert second == snapshot
        assert second  # unaffected by the caller mutating the prior result
