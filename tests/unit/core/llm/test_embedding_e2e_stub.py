"""Tests for the E2E embedding stub — ``TestEmbeddingProvider``.

When ``NARRARE_E2E_TEST`` is set, :func:`narrare_core.llm.embedding_providers.get`
returns a :class:`TestEmbeddingProvider` instead of constructing a real
OpenAI client. This is the embedding-gateway analogue of ``TestModel``
(the LLM stub exercised in ``test_providers_registry.py::TestE2ETestMode``)
and keeps end-to-end tests hermetic — no network, deterministic vectors.

These tests were split out of ``test_embeddings.py`` to keep that module
under the RULE-04 line limit. The non-E2E embedding tests (registry,
provider selection, direct injection) remain there.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest


class TestEmbeddingProviderE2ETestMode:
    """When NARRARE_E2E_TEST is set, embedding_providers.get() returns a
    TestEmbeddingProvider — no real OpenAI calls.

    Mirrors TestE2ETestMode in tests/unit/core/llm/test_providers_registry.py
    (the TestModel override). This is the E2E stub for the embedding gateway,
    analogous to how TestModel stubs the LLM agent.
    """

    @pytest.fixture(autouse=True)
    def _set_e2e_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NARRARE_E2E_TEST", "1")

    async def test_get_returns_test_embedding_provider(self) -> None:
        from narrare_core.llm.embedding_providers import TestEmbeddingProvider, get

        provider = get("openai")
        assert isinstance(provider, TestEmbeddingProvider)

    async def test_e2e_still_raises_for_unknown_provider(self) -> None:
        """The KeyError check runs before the E2E override (mirrors
        registry.py), so unknown names still raise even in E2E mode."""
        from narrare_core.llm.embedding_providers import get

        with pytest.raises(KeyError, match="Unknown embedding provider"):
            get("__nonexistent_e2e_provider__")

    async def test_embed_texts_returns_dummy_vectors_without_network(self) -> None:
        """In E2E mode, embed_texts returns deterministic vectors and never
        touches the OpenAI client."""
        from narrare_core.llm.embeddings import embed_texts

        # Patch AsyncOpenAI at the provider module to prove it is NOT used.
        with patch("narrare_core.llm.embedding_providers.openai.AsyncOpenAI") as mock_openai:
            result = await embed_texts(["hello world", "another text"])

        mock_openai.assert_not_called()
        assert len(result) == 2
        assert all(len(v) == 1536 for v in result)

    async def test_dummy_vectors_are_deterministic(self) -> None:
        """Same input text yields the same vector (keeps similarity
        computations reproducible in E2E)."""
        from narrare_core.llm.embeddings import embed_texts

        first = await embed_texts(["deterministic input"])
        second = await embed_texts(["deterministic input"])
        assert first == second

    async def test_empty_strings_return_zero_vectors_in_e2e(self) -> None:
        from narrare_core.llm.embeddings import embed_texts

        result = await embed_texts(["", "  "])
        assert len(result) == 2
        assert all(v == [0.0] * 1536 for v in result)

    async def test_test_embedding_provider_satisfies_protocol(self) -> None:
        from narrare_core.llm.embedding_providers import (
            EmbeddingProvider,
            TestEmbeddingProvider,
        )

        assert isinstance(TestEmbeddingProvider(), EmbeddingProvider)
