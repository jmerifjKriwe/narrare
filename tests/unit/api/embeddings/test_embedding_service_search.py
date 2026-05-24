"""Unit tests for EmbeddingService — search operations.

Tests ``search()`` using FakeEmbeddingRepository and mocked ``embed_texts``.
Shared fixtures are in ``conftest.py``.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from narrare.embeddings.service import EmbeddingService  # noqa: TC001
from narrare_core.shared.errors import EmbeddingError

from .conftest import FakeEmbeddingRepository  # noqa: TC001


class TestSearch:
    @patch("narrare.embeddings.service.embed_texts")
    async def test_search_calls_embed_and_returns_results(
        self,
        mock_embed: AsyncMock,
        service: EmbeddingService,
        fake_repo: FakeEmbeddingRepository,
    ) -> None:
        mock_embed.return_value = [[0.1] * 1536]
        source_id = uuid.uuid4()

        # Seed an embedding
        await fake_repo.upsert(
            "kb_entry",
            source_id,
            "hash123",
            [0.2] * 1536,
            "text-embedding-3-small",
            1536,
        )

        results = await service.search("test query", source_type="kb_entry")

        assert len(results) == 1
        assert results[0].source_id == source_id

    @patch("narrare.embeddings.service.embed_texts")
    async def test_search_returns_empty_for_no_matches(
        self,
        mock_embed: AsyncMock,
        service: EmbeddingService,
    ) -> None:
        mock_embed.return_value = [[0.1] * 1536]

        results = await service.search("nonexistent query", source_ids=set())

        assert results == []

    @patch("narrare.embeddings.service.embed_texts")
    async def test_search_raises_on_embed_failure(
        self,
        mock_embed: AsyncMock,
        service: EmbeddingService,
    ) -> None:
        mock_embed.side_effect = Exception("API error")

        with pytest.raises(EmbeddingError, match="Query embedding failed"):
            await service.search("test query")
