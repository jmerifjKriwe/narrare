"""Unit tests for EmbeddingService — generate operations.

Tests ``generate()`` using FakeEmbeddingRepository and mocked ``embed_texts``.
Shared fixtures are in ``conftest.py``.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from narrare.embeddings.service import EmbeddingService  # noqa: TC001
from narrare_core.shared.errors import EmbeddingError

from .conftest import FakeEmbeddingRepository  # noqa: TC001


class TestGenerate:
    @patch("narrare.embeddings.service.embed_texts")
    async def test_generate_delegates_to_embed_texts_and_repo(
        self,
        mock_embed: AsyncMock,
        service: EmbeddingService,
        fake_repo: FakeEmbeddingRepository,
    ) -> None:
        mock_embed.return_value = [[0.1] * 1536]
        source_id = uuid.uuid4()

        await service.generate("kb_entry", source_id, "test content")

        mock_embed.assert_called_once_with(["test content"], model="text-embedding-3-small")
        result = await fake_repo.get_by_source("kb_entry", source_id)
        assert result is not None
        assert result.source_type == "kb_entry"
        assert result.source_id == source_id

    @patch("narrare.embeddings.service.embed_texts")
    async def test_generate_computes_content_hash(
        self,
        mock_embed: AsyncMock,
        service: EmbeddingService,
        fake_repo: FakeEmbeddingRepository,
    ) -> None:
        mock_embed.return_value = [[0.1] * 1536]
        source_id = uuid.uuid4()

        await service.generate("kb_entry", source_id, "hello world")

        result = await fake_repo.get_by_source("kb_entry", source_id)
        assert result is not None
        # Hash should match SHA-256 of "hello world"
        from narrare_core.embeddings.hash import compute_content_hash

        assert result.content_hash == compute_content_hash("hello world")

    @patch("narrare.embeddings.service.embed_texts")
    async def test_generate_raises_on_embed_failure(
        self,
        mock_embed: AsyncMock,
        service: EmbeddingService,
    ) -> None:
        mock_embed.side_effect = Exception("API error")

        with pytest.raises(EmbeddingError, match="Embedding generation failed"):
            await service.generate("kb_entry", uuid.uuid4(), "content")

    @patch("narrare.embeddings.service.embed_texts")
    async def test_generate_raises_on_empty_vectors(
        self,
        mock_embed: AsyncMock,
        service: EmbeddingService,
    ) -> None:
        mock_embed.return_value = []

        with pytest.raises(EmbeddingError, match="no vectors"):
            await service.generate("kb_entry", uuid.uuid4(), "content")
