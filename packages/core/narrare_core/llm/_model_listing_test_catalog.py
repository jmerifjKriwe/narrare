"""E2E test catalog stub for the provider model catalog.

Deterministic, network-free catalog used by
:meth:`narrare_core.llm.model_listing.ModelCatalogClient.list_models`
when ``get_core_settings().e2e_test`` is true. Analogous to
:class:`narrare_core.llm.embedding_providers.TestEmbeddingProvider` and
``pydantic_ai.models.test.TestModel``: it satisfies a catalog query
without calling a real provider API, keeping E2E hermetic (CR:
provider-catalog leak class, same as the embedding/model/memory stubs).

This module is internal (underscore prefix) — only ``model_listing.py``
imports it. It exists as a separate module to keep ``model_listing.py``
under the RULE-04 line limit.

The catalog is stored as raw tuples and materialised into
``ModelCatalogEntry`` instances inside :func:`_test_catalog` to avoid a
circular import (``ModelCatalogEntry`` lives in ``model_listing.py``,
which imports this module at load time).
"""

from __future__ import annotations

from typing import Any

__all__ = ["_test_catalog"]

# ---------------------------------------------------------------------------
# Test catalog (E2E stub — analog to TestModel / TestEmbeddingProvider)
# ---------------------------------------------------------------------------

# Raw catalog data: provider -> list of (id, name, context_window|None).
# Kept as plain tuples so this module does not need to import
# ``ModelCatalogEntry`` at load time (avoids a circular import with
# ``model_listing.py``).
_TEST_CATALOG: dict[str, list[tuple[str, str, int | None]]] = {
    "anthropic": [
        ("claude-test-model", "Claude (Test)", 200000),
    ],
    "openai": [
        ("gpt-test-model", "GPT (Test)", 128000),
    ],
    "ollama": [
        ("ollama-test-model", "Ollama (Test)", None),
    ],
    "google": [
        ("gemini-test-model", "Gemini (Test)", 1000000),
    ],
    "groq": [
        ("groq-test-model", "Groq (Test)", None),
    ],
    "openrouter": [
        ("openrouter-test-model", "OpenRouter (Test)", 128000),
    ],
    "zai": [
        ("glm-test-model", "GLM (Test)", None),
    ],
}


def _test_catalog(provider: str) -> list[Any]:
    """Return a deterministic model catalog for E2E/test mode — no network.

    Analogous to :class:`narrare_core.llm.embedding_providers.TestEmbeddingProvider`
    and ``pydantic_ai.models.test.TestModel``: it satisfies a catalog query
    without calling a real provider API. Returned by
    :meth:`narrare_core.llm.model_listing.ModelCatalogClient.list_models`
    when ``get_core_settings().e2e_test`` is true — the same switch the
    other two stubs use.

    Each supported provider gets one stable entry so the setup-wizard
    model-selection flow works end-to-end without real credentials or
    network access (keeps E2E hermetic — CR: provider-catalog leak class,
    same as the embedding/model/memory stubs).

    ``ModelCatalogEntry`` is imported lazily here to avoid a circular
    import at module load time (this module is imported by
    ``model_listing.py`` before ``ModelCatalogEntry`` would be available
    if imported at top level in the other direction).
    """
    from narrare_core.llm.model_listing import ModelCatalogEntry

    return [
        ModelCatalogEntry(id=mid, name=name, context_window=ctx)
        for mid, name, ctx in _TEST_CATALOG.get(provider, [])
    ]
