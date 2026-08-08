"""Leak-regression tests for OpenAIEmbeddingProvider client lifecycle.

Extracted from ``test_embeddings.py`` per RULE-04 (file size limits).

These guard against resource leaks in the lazy-init / dependency-injection
paths of :class:`narrare_core.llm.embedding_providers.OpenAIEmbeddingProvider`:

* ``test_lazy_client_reused_across_calls_no_leak`` — a provider without an
  injected client must construct exactly ONE ``AsyncOpenAI`` and reuse it,
  not leak a new httpx client + socket per call.
* ``test_injected_client_bypasses_lazy_init`` — an injected client must be
  used as-is; the lazy-init path must not fire.

The spec fakes are shared via :mod:`tests.unit.core.llm._embedding_fakes`.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from ._embedding_fakes import (
    _FakeEmbeddingItem,
    _FakeEmbeddingResponse,
    _FakeEmbeddingsResource,
)


class TestOpenAIEmbeddingProviderClientLifecycle:
    """Regression tests for the lazy-init / DI client handling.

    These intentionally instantiate fresh ``OpenAIEmbeddingProvider`` instances
    (no module singleton involved), so they do not require the
    ``_reset_openai_singleton_client`` fixture used by the ``embed_texts``
    convenience-function tests in ``test_embeddings.py``.
    """

    async def test_lazy_client_reused_across_calls_no_leak(self) -> None:
        """Regression: embed_texts must NOT construct a new AsyncOpenAI on
        every call (each call leaked an un-closed httpx client + socket).

        Without an injected client, the provider lazily creates ONE client
        on first use and reuses it for all subsequent calls.
        """
        from narrare_core.llm.embedding_providers import OpenAIEmbeddingProvider

        mock_item = MagicMock(spec=_FakeEmbeddingItem)
        mock_item.index = 0
        mock_item.embedding = [0.1, 0.2]

        mock_response = MagicMock(spec=_FakeEmbeddingResponse)
        mock_response.data = [mock_item]

        mock_client = AsyncMock()
        mock_client.embeddings = MagicMock(spec=_FakeEmbeddingsResource)
        mock_client.embeddings.create = AsyncMock(return_value=mock_response)

        # No client injected → exercises the lazy-init path.
        provider = OpenAIEmbeddingProvider()

        with patch(
            "narrare_core.llm.embedding_providers.openai.AsyncOpenAI",
            return_value=mock_client,
        ) as mock_ctor:
            await provider.embed_texts(["first call"])
            await provider.embed_texts(["second call"])

        # Exactly ONE client constructed across two calls — no per-call leak.
        assert mock_ctor.call_count == 1
        # The reused client handled both embed calls.
        assert mock_client.embeddings.create.call_count == 2

    async def test_injected_client_bypasses_lazy_init(self) -> None:
        """An injected client must be used as-is; no AsyncOpenAI constructed.

        This guards behavioral compatibility for callers/tests that inject a
        (possibly fake) client — the lazy-init path must not fire.
        """
        from narrare_core.llm.embedding_providers import OpenAIEmbeddingProvider

        mock_item = MagicMock(spec=_FakeEmbeddingItem)
        mock_item.index = 0
        mock_item.embedding = [0.3]

        mock_response = MagicMock(spec=_FakeEmbeddingResponse)
        mock_response.data = [mock_item]

        mock_client = AsyncMock()
        mock_client.embeddings = MagicMock(spec=_FakeEmbeddingsResource)
        mock_client.embeddings.create = AsyncMock(return_value=mock_response)

        provider = OpenAIEmbeddingProvider(client=mock_client)

        with patch(
            "narrare_core.llm.embedding_providers.openai.AsyncOpenAI",
        ) as mock_ctor:
            await provider.embed_texts(["injected"])

        assert mock_ctor.call_count == 0
        mock_client.embeddings.create.assert_called_once()
