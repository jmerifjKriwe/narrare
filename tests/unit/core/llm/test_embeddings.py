"""Tests for llm/embeddings.py — text embedding generation.

These tests cover both the :mod:`narrare_core.llm.embeddings` convenience
re-exports and the underlying :mod:`narrare_core.llm.embedding_providers`
implementation (OpenAIEmbeddingProvider).

The OpenAI client is patched at the provider layer:
``narrare_core.llm.embedding_providers.openai.AsyncOpenAI``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from narrare_core.shared.errors import EmbeddingError

# ── Fake classes for MagicMock spec (RULE-TEST-01 compliance) ──────────────


class _FakeEmbeddingItem:
    """Fake for OpenAI embedding response item (has .index + .embedding)."""

    index = 0
    embedding = None


class _FakeEmbeddingResponse:
    """Fake for OpenAI create embeddings response (has .data)."""

    data = None


class _FakeEmbeddingsResource:
    """Fake for OpenAI embeddings resource (has .create method)."""

    def create(self, **kwargs) -> None: ...


class _FakeProvider:
    """Fake for an EmbeddingProvider protocol implementation."""

    default_model = ""
    default_dimension = 0

    async def embed_texts(
        self, texts: list[str], model: str | None = None
    ) -> list[list[float]]: ...


class TestEmbedTexts:
    """Tests for the embed_texts convenience function (backward compatible)."""

    async def test_returns_empty_list_for_empty_input(self) -> None:
        from narrare_core.llm.embeddings import embed_texts

        result = await embed_texts([])
        assert result == []

    async def test_returns_zero_vectors_for_all_empty_strings(self) -> None:
        from narrare_core.llm.embeddings import embed_texts

        result = await embed_texts(["", "  ", ""])
        assert len(result) == 3
        assert all(len(v) == 1536 for v in result)
        assert all(all(x == 0.0 for x in v) for v in result)

    async def test_calls_api_and_returns_embeddings(self) -> None:
        from narrare_core.llm.embeddings import embed_texts

        mock_item = MagicMock(spec=_FakeEmbeddingItem)
        mock_item.index = 0
        mock_item.embedding = [0.1, 0.2, 0.3]

        mock_response = MagicMock(spec=_FakeEmbeddingResponse)
        mock_response.data = [mock_item]

        mock_client = AsyncMock()
        mock_client.embeddings = MagicMock(spec=_FakeEmbeddingsResource)
        mock_client.embeddings.create = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "narrare_core.llm.embedding_providers.openai.AsyncOpenAI",
            return_value=mock_client,
        ):
            result = await embed_texts(["hello world"])

        assert len(result) == 1
        assert result[0] == [0.1, 0.2, 0.3]

    async def test_handles_mixed_empty_and_nonempty_texts(self) -> None:
        from narrare_core.llm.embeddings import embed_texts

        mock_item = MagicMock(spec=_FakeEmbeddingItem)
        mock_item.index = 0
        mock_item.embedding = [0.5, 0.6]

        mock_response = MagicMock(spec=_FakeEmbeddingResponse)
        mock_response.data = [mock_item]

        mock_client = AsyncMock()
        mock_client.embeddings = MagicMock(spec=_FakeEmbeddingsResource)
        mock_client.embeddings.create = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "narrare_core.llm.embedding_providers.openai.AsyncOpenAI",
            return_value=mock_client,
        ):
            result = await embed_texts(["", "real text", ""])

        assert len(result) == 3
        # First and last should be zero vectors (dimension 2 from the mock)
        assert result[0] == [0.0, 0.0]
        assert result[1] == [0.5, 0.6]
        assert result[2] == [0.0, 0.0]

    async def test_raises_embedding_error_on_api_failure(self) -> None:
        import openai  # narrare: allow  reason="Testing OpenAI exception type"

        from narrare_core.llm.embeddings import embed_texts

        mock_client = AsyncMock()
        mock_client.embeddings = MagicMock(spec=_FakeEmbeddingsResource)
        mock_client.embeddings.create = AsyncMock(side_effect=openai.OpenAIError("API down"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with (
            patch(
                "narrare_core.llm.embedding_providers.openai.AsyncOpenAI",
                return_value=mock_client,
            ),
            pytest.raises(EmbeddingError, match="Embedding generation failed"),
        ):
            await embed_texts(["some text"])

    async def test_uses_custom_model_when_provided(self) -> None:
        from narrare_core.llm.embeddings import embed_texts

        mock_item = MagicMock(spec=_FakeEmbeddingItem)
        mock_item.index = 0
        mock_item.embedding = [0.1]

        mock_response = MagicMock(spec=_FakeEmbeddingResponse)
        mock_response.data = [mock_item]

        mock_client = AsyncMock()
        mock_client.embeddings = MagicMock(spec=_FakeEmbeddingsResource)
        mock_client.embeddings.create = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "narrare_core.llm.embedding_providers.openai.AsyncOpenAI",
            return_value=mock_client,
        ):
            await embed_texts(["text"], model="custom-model")

        mock_client.embeddings.create.assert_called_once_with(input=["text"], model="custom-model")

    async def test_uses_env_var_model_as_fallback(self) -> None:
        from narrare_core.llm.embeddings import embed_texts

        mock_item = MagicMock(spec=_FakeEmbeddingItem)
        mock_item.index = 0
        mock_item.embedding = [0.1]

        mock_response = MagicMock(spec=_FakeEmbeddingResponse)
        mock_response.data = [mock_item]

        mock_client = AsyncMock()
        mock_client.embeddings = MagicMock(spec=_FakeEmbeddingsResource)
        mock_client.embeddings.create = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with (
            patch(
                "narrare_core.llm.embedding_providers.openai.AsyncOpenAI",
                return_value=mock_client,
            ),
            patch.dict("os.environ", {"DEFAULT_EMBEDDING_MODEL": "env-model"}),
        ):
            await embed_texts(["text"])

        mock_client.embeddings.create.assert_called_once_with(input=["text"], model="env-model")

    async def test_processes_large_input_in_batches(self) -> None:
        from narrare_core.llm.embeddings import embed_texts

        batch_size = 100

        # Create more texts than the batch size
        texts = [f"text {i}" for i in range(batch_size + 10)]

        # Create mock items with proper index and embedding
        all_items: list[MagicMock] = []
        for i in range(len(texts)):
            mock_item = MagicMock(spec=_FakeEmbeddingItem)
            mock_item.index = i
            mock_item.embedding = [0.0] * 4
            all_items.append(mock_item)

        mock_response = MagicMock(spec=_FakeEmbeddingResponse)
        mock_response.data = all_items[:batch_size]

        mock_response2 = MagicMock(spec=_FakeEmbeddingResponse)
        mock_response2.data = all_items[batch_size:]

        mock_client = AsyncMock()
        mock_client.embeddings = MagicMock(spec=_FakeEmbeddingsResource)
        mock_client.embeddings.create = AsyncMock(side_effect=[mock_response, mock_response2])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "narrare_core.llm.embedding_providers.openai.AsyncOpenAI",
            return_value=mock_client,
        ):
            result = await embed_texts(texts)

        assert len(result) == len(texts)
        assert mock_client.embeddings.create.call_count == 2


class TestEmbeddingProviderRegistry:
    """Tests for the registry functions in embedding_providers."""

    async def test_register_and_get(self) -> None:
        from narrare_core.llm.embedding_providers import (
            available,
            get,
            register,
        )

        # Register a test provider
        mock_provider = MagicMock(spec=_FakeProvider)
        mock_provider.default_model = "test-model"
        mock_provider.default_dimension = 128
        mock_provider.embed_texts = AsyncMock(return_value=[[0.1, 0.2]])

        register("test_provider", mock_provider)
        retrieved = get("test_provider")
        assert retrieved is mock_provider
        assert "test_provider" in available()

        # Clean up to avoid affecting other tests
        # (we can't easily unregister, so we use a unique name)

    async def test_get_unknown_raises_key_error(self) -> None:
        from narrare_core.llm.embedding_providers import get

        with pytest.raises(KeyError, match="Unknown embedding provider"):
            get("nonexistent_provider_xyz")

    async def test_available_returns_openai_by_default(self) -> None:
        from narrare_core.llm.embedding_providers import available

        providers = available()
        assert "openai" in providers

    async def test_get_default_returns_openai(self) -> None:
        from narrare_core.llm.embedding_providers import get_default

        assert get_default() == "openai"

    async def test_get_default_raises_when_none_registered(self) -> None:
        from narrare_core.llm.embedding_providers import (
            _default_key,
            _embedding_providers,
        )

        # Temporarily clear and restore
        old_key = _default_key
        old_providers = dict(_embedding_providers)

        try:
            import narrare_core.llm.embedding_providers as ep

            ep._default_key = None
            ep._embedding_providers = {}  # type: ignore[misc]

            with pytest.raises(RuntimeError, match="No default embedding provider"):
                ep.get_default()
        finally:
            ep._default_key = old_key  # type: ignore[possibly-undefined]
            ep._embedding_providers.clear()  # type: ignore[possibly-undefined]
            ep._embedding_providers.update(old_providers)  # type: ignore[possibly-undefined]


class TestEmbedTextsProviderSelection:
    """Tests for the provider kwarg in the embed_texts convenience function."""

    async def test_uses_specified_provider(self) -> None:
        from narrare_core.llm.embedding_providers import (
            embed_texts,
            register,
        )

        # Register a test provider
        mock_provider = MagicMock(spec=_FakeProvider)
        mock_provider.default_model = "test-model"
        mock_provider.default_dimension = 128
        mock_provider.embed_texts = AsyncMock(return_value=[[0.42, 0.84]])

        provider_name = "test_provider_select"
        register(provider_name, mock_provider)

        result = await embed_texts(["hello"], provider=provider_name)
        assert result == [[0.42, 0.84]]
        mock_provider.embed_texts.assert_called_once_with(["hello"], model=None)

    async def test_uses_default_provider_when_none_specified(self) -> None:
        from narrare_core.llm.embedding_providers import get_default

        default = get_default()
        assert default == "openai"

    async def test_provider_kwarg_additive_backward_compat(self) -> None:
        """Verify the provider kwarg is additive — existing callers work without it."""
        from narrare_core.llm.embedding_providers import embed_texts as direct_embed_texts
        from narrare_core.llm.embeddings import embed_texts as compat_embed_texts

        # Both functions should be the same object
        assert compat_embed_texts is direct_embed_texts


class TestOpenAIEmbeddingProviderDirect:
    """Tests that instantiate OpenAIEmbeddingProvider directly with a mock client."""

    async def test_direct_injection_of_mock_client(self) -> None:
        """Verify the DI pattern: inject a mock client via the constructor."""
        from narrare_core.llm.embedding_providers import OpenAIEmbeddingProvider

        mock_item = MagicMock(spec=_FakeEmbeddingItem)
        mock_item.index = 0
        mock_item.embedding = [0.9, 0.8, 0.7]

        mock_response = MagicMock(spec=_FakeEmbeddingResponse)
        mock_response.data = [mock_item]

        mock_client = AsyncMock()
        mock_client.embeddings = MagicMock(spec=_FakeEmbeddingsResource)
        mock_client.embeddings.create = AsyncMock(return_value=mock_response)

        provider = OpenAIEmbeddingProvider(client=mock_client)
        result = await provider.embed_texts(["direct injection"])

        assert result == [[0.9, 0.8, 0.7]]
        mock_client.embeddings.create.assert_called_once_with(
            input=["direct injection"],
            model="text-embedding-3-small",
        )

    async def test_default_dimension(self) -> None:
        from narrare_core.llm.embedding_providers import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider()
        assert provider.default_model == "text-embedding-3-small"
        assert provider.default_dimension == 1536

    async def test_protocol_runtime_checkable(self) -> None:
        from narrare_core.llm.embedding_providers import (
            EmbeddingProvider,
            OpenAIEmbeddingProvider,
        )

        provider = OpenAIEmbeddingProvider()
        assert isinstance(provider, EmbeddingProvider)
