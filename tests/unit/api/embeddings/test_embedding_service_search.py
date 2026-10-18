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
from tests.fakes import FakeEmbeddingRepository  # noqa: TC001


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

    @patch("narrare.embeddings.service.embed_texts")
    async def test_search_raises_on_empty_vectors(
        self,
        mock_embed: AsyncMock,
        service: EmbeddingService,
    ) -> None:
        """Service.search raises when embed_texts returns empty list."""
        mock_embed.return_value = []

        with pytest.raises(EmbeddingError, match="Query embedding returned no vectors"):
            await service.search("test query")

    @patch("narrare.embeddings.service.embed_texts")
    async def test_search_forwards_novel_scope_to_repo(
        self,
        mock_embed: AsyncMock,
        service: EmbeddingService,
        fake_repo: FakeEmbeddingRepository,
    ) -> None:
        """The novel scope reaches the repository (ADR-088 suggestions).

        Regression: ``EmbeddingService.search`` accepted ``novel_id`` but
        never forwarded it — the KB suggestions search ran unscoped and
        could surface other novels' (and orphaned) embedding rows.
        """
        mock_embed.return_value = [[0.1] * 1536]
        novel_id = uuid.uuid4()

        await service.search("test query", source_type="kb_entry", novel_id=novel_id)

        search_calls = [c for c in fake_repo.calls if c.method == "search"]
        assert search_calls, "repository search was not called"
        assert search_calls[-1].kwargs["novel_id"] == novel_id
