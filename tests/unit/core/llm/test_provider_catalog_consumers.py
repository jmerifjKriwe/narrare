"""Consumer parity tests for the generated provider catalog (ADR-099).

The canonical provider set lives in the generated ``catalog_generated``
module. Any Core module that restates the provider set by hand drifts
silently when a provider is added to ``catalog.yaml``. These tests pin
the two consumers to the generated SSOT:

* ``model_listing.SUPPORTED_CATALOG_PROVIDERS`` — the derived set, and
* ``_model_listing_test_catalog._TEST_MODELS`` — the E2E stub source keys.

A third test guards the dispatch contract: every catalog provider must
have a ``_fetch_<id>`` method on ``ModelCatalogClient``, so adding a
provider without a fetcher fails here rather than at runtime.
"""

from __future__ import annotations

from narrare_core.llm._model_listing_test_catalog import _TEST_MODELS
from narrare_core.llm._providers.catalog_generated import PROVIDER_IDS
from narrare_core.llm.model_listing import SUPPORTED_CATALOG_PROVIDERS, ModelCatalogClient

EXPECTED = {"anthropic", "openai", "google", "groq", "ollama", "openrouter", "zai"}


def test_supported_catalog_providers_is_derived() -> None:
    assert SUPPORTED_CATALOG_PROVIDERS == EXPECTED
    assert set(PROVIDER_IDS) == EXPECTED


def test_test_models_exactly_matches_generated_provider_set() -> None:
    # ``_TEST_MODELS`` is the surface this guard must inspect, not the derived
    # ``_TEST_CATALOG``: the comprehension there silently drops a *stale* key (a
    # provider no longer in ``PROVIDER_IDS``), while a *missing* key raises
    # ``KeyError`` at import. So this assertion is the stale-entry guard;
    # ``set(_TEST_CATALOG) == EXPECTED`` would only restate that comprehension.
    assert set(_TEST_MODELS) == EXPECTED


def test_every_provider_has_a_model_fetcher() -> None:
    missing = [p for p in PROVIDER_IDS if not hasattr(ModelCatalogClient, f"_fetch_{p}")]
    assert missing == []
