"""Unit tests for EmbeddingService — lifecycle operations.

Tests ``delete()``, ``get_status()``, ``reprocess()``, and property
accessors. Shared fixtures are in ``conftest.py``.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

from narrare.embeddings.service import EmbeddingService  # noqa: TC001

from .conftest import FakeEmbeddingRepository  # noqa: TC001


class TestDelete:
    async def test_delete_removes_embedding(
        self,
        service: EmbeddingService,
        fake_repo: FakeEmbeddingRepository,
    ) -> None:
        source_id = uuid.uuid4()
        await fake_repo.upsert(
            "kb_entry",
            source_id,
            "hash",
            [0.1] * 1536,
            "text-embedding-3-small",
            1536,
        )

        await service.delete("kb_entry", source_id)

        result = await fake_repo.get_by_source("kb_entry", source_id)
        assert result is None

    async def test_delete_nonexistent_succeeds_silently(
        self,
        service: EmbeddingService,
    ) -> None:
        # Should not raise
        await service.delete("kb_entry", uuid.uuid4())


class TestGetStatus:
    async def test_get_status_returns_stats(
        self,
        service: EmbeddingService,
        fake_repo: FakeEmbeddingRepository,
    ) -> None:
        sid1 = uuid.uuid4()
        sid2 = uuid.uuid4()
        sid3 = uuid.uuid4()
        await fake_repo.upsert(
            "kb_entry",
            sid1,
            "hash1",
            [0.1] * 1536,
            "text-embedding-3-small",
            1536,
        )

        stats = await service.get_status(
            novel_id=uuid.uuid4(),
            source_ids={sid1, sid2, sid3},
        )

        assert stats.total == 3
        assert stats.embedded == 1
        assert stats.pending == 2
        assert stats.coverage_percentage == 33.3

    async def test_get_status_with_empty_ids(
        self,
        service: EmbeddingService,
    ) -> None:
        stats = await service.get_status(novel_id=uuid.uuid4())

        assert stats.total == 0
        assert stats.embedded == 0


class TestReprocess:
    @patch("narrare.embeddings.service.embed_texts")
    async def test_reprocess_generates_embeddings(
        self,
        mock_embed: AsyncMock,
        service: EmbeddingService,
        fake_repo: FakeEmbeddingRepository,
    ) -> None:
        mock_embed.return_value = [[0.1] * 1536]
        sid1 = uuid.uuid4()
        sid2 = uuid.uuid4()

        queued = await service.reprocess(
            novel_id=uuid.uuid4(),
            source_ids=[(sid1, "content1"), (sid2, "content2")],
        )

        assert queued == 2

    async def test_reprocess_with_empty_list_returns_zero(
        self,
        service: EmbeddingService,
    ) -> None:
        queued = await service.reprocess(novel_id=uuid.uuid4())

        assert queued == 0


class TestProperties:
    def test_model_property(self, service: EmbeddingService) -> None:
        assert service.model == "text-embedding-3-small"

    def test_dimension_property(self, service: EmbeddingService) -> None:
        assert service.dimension == 1536

    def test_provider_property(self, service: EmbeddingService) -> None:
        assert service.provider == "openai"
