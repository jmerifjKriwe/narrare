"""Tests for llm/embeddings.py — text embedding generation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from narrare_core.shared.errors import EmbeddingError


class TestEmbedTexts:
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

        # narrare: allow  reason="Mocking openai client infrastructure for embedding API calls"
        mock_item = MagicMock()
        mock_item.index = 0
        mock_item.embedding = [0.1, 0.2, 0.3]

        # narrare: allow  reason="Mocking openai client infrastructure for embedding API calls"
        mock_response = MagicMock()
        mock_response.data = [mock_item]

        mock_client = AsyncMock()
        # narrare: allow  reason="Mocking openai client infrastructure for embedding API calls"
        mock_client.embeddings = MagicMock()
        mock_client.embeddings.create = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("narrare_core.llm.embeddings.openai.AsyncOpenAI", return_value=mock_client):
            result = await embed_texts(["hello world"])

        assert len(result) == 1
        assert result[0] == [0.1, 0.2, 0.3]

    async def test_handles_mixed_empty_and_nonempty_texts(self) -> None:
        from narrare_core.llm.embeddings import embed_texts

        # narrare: allow  reason="Mocking openai client infrastructure for embedding API calls"
        mock_item = MagicMock()
        mock_item.index = 0
        mock_item.embedding = [0.5, 0.6]

        # narrare: allow  reason="Mocking openai client infrastructure for embedding API calls"
        mock_response = MagicMock()
        mock_response.data = [mock_item]

        mock_client = AsyncMock()
        # narrare: allow  reason="Mocking openai client infrastructure for embedding API calls"
        mock_client.embeddings = MagicMock()
        mock_client.embeddings.create = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("narrare_core.llm.embeddings.openai.AsyncOpenAI", return_value=mock_client):
            result = await embed_texts(["", "real text", ""])

        assert len(result) == 3
        # First and last should be zero vectors (dimension 2 from the mock)
        assert result[0] == [0.0, 0.0]
        assert result[1] == [0.5, 0.6]
        assert result[2] == [0.0, 0.0]

    async def test_raises_embedding_error_on_api_failure(self) -> None:
        import openai  # narrare: allow  reason="Testing embeddings module"

        from narrare_core.llm.embeddings import embed_texts

        mock_client = AsyncMock()
        # narrare: allow  reason="Mocking openai client infrastructure for embedding API calls"
        mock_client.embeddings = MagicMock()
        mock_client.embeddings.create = AsyncMock(side_effect=openai.OpenAIError("API down"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("narrare_core.llm.embeddings.openai.AsyncOpenAI", return_value=mock_client),
            pytest.raises(EmbeddingError, match="Embedding generation failed"),
        ):
            await embed_texts(["some text"])

    async def test_uses_custom_model_when_provided(self) -> None:
        from narrare_core.llm.embeddings import embed_texts

        # narrare: allow  reason="Mocking openai client infrastructure for embedding API calls"
        mock_item = MagicMock()
        mock_item.index = 0
        mock_item.embedding = [0.1]

        # narrare: allow  reason="Mocking openai client infrastructure for embedding API calls"
        mock_response = MagicMock()
        mock_response.data = [mock_item]

        mock_client = AsyncMock()
        # narrare: allow  reason="Mocking openai client infrastructure for embedding API calls"
        mock_client.embeddings = MagicMock()
        mock_client.embeddings.create = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("narrare_core.llm.embeddings.openai.AsyncOpenAI", return_value=mock_client):
            await embed_texts(["text"], model="custom-model")

        mock_client.embeddings.create.assert_called_once_with(input=["text"], model="custom-model")

    async def test_uses_env_var_model_as_fallback(self) -> None:
        from narrare_core.llm.embeddings import embed_texts

        # narrare: allow  reason="Mocking openai client infrastructure for embedding API calls"
        mock_item = MagicMock()
        mock_item.index = 0
        mock_item.embedding = [0.1]

        # narrare: allow  reason="Mocking openai client infrastructure for embedding API calls"
        mock_response = MagicMock()
        mock_response.data = [mock_item]

        mock_client = AsyncMock()
        # narrare: allow  reason="Mocking openai client infrastructure for embedding API calls"
        mock_client.embeddings = MagicMock()
        mock_client.embeddings.create = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("narrare_core.llm.embeddings.openai.AsyncOpenAI", return_value=mock_client),
            patch.dict("os.environ", {"DEFAULT_EMBEDDING_MODEL": "env-model"}),
        ):
            await embed_texts(["text"])

        mock_client.embeddings.create.assert_called_once_with(input=["text"], model="env-model")

    async def test_processes_large_input_in_batches(self) -> None:
        from narrare_core.llm.embeddings import (
            _BATCH_SIZE,
            embed_texts,
        )

        # Create more texts than the batch size
        texts = [f"text {i}" for i in range(_BATCH_SIZE + 10)]

        # Create mock items with proper index and embedding
        all_items: list[MagicMock] = []
        for i in range(len(texts)):
            # narrare: allow  reason="Mocking openai client infrastructure for embedding API calls"
            mock_item = MagicMock()
            mock_item.index = i
            mock_item.embedding = [0.0] * 4
            all_items.append(mock_item)

        # narrare: allow  reason="Mocking openai client infrastructure for embedding API calls"
        mock_response = MagicMock()
        mock_response.data = all_items[:_BATCH_SIZE]

        # narrare: allow  reason="Mocking openai client infrastructure for embedding API calls"
        mock_response2 = MagicMock()
        mock_response2.data = all_items[_BATCH_SIZE:]

        mock_client = AsyncMock()
        # narrare: allow  reason="Mocking openai client infrastructure for embedding API calls"
        mock_client.embeddings = MagicMock()
        mock_client.embeddings.create = AsyncMock(side_effect=[mock_response, mock_response2])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("narrare_core.llm.embeddings.openai.AsyncOpenAI", return_value=mock_client):
            result = await embed_texts(texts)

        assert len(result) == len(texts)
        assert mock_client.embeddings.create.call_count == 2
