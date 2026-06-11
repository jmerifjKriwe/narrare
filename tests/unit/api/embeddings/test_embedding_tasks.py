"""Unit tests for embedding background tasks.

Tests mock embed_texts and verify retry behavior and idempotent skip.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from narrare.embeddings.models import Embedding
from narrare.embeddings.search_queries import SearchRow  # noqa: TC001
from narrare.embeddings.tasks import run_embed_source
from narrare_core.embeddings.hash import compute_content_hash
from narrare_core.embeddings.store import EmbeddingStats  # noqa: TC001
from narrare_core.shared.errors import EmbeddingError

# ---------------------------------------------------------------------------
# Fake repository for task tests
# ---------------------------------------------------------------------------


class FakeEmbeddingRepo:
    """Fake implementing EmbeddingRepositoryProtocol for task testing.

    Only get_by_source and upsert are functional; the rest raise
    NotImplementedError to catch unexpected usage.
    """

    def __init__(self) -> None:
        self._embeddings: dict[tuple[str, uuid.UUID, str], Embedding] = {}
        self.upsert_calls: list[tuple[str, uuid.UUID, str, list[float], str, int]] = []

    async def get_by_source(
        self,
        source_type: str,
        source_id: uuid.UUID,
        model: str | None = None,
    ) -> Embedding | None:
        key = (source_type, source_id, model or "")
        return self._embeddings.get(key)

    async def upsert(
        self,
        source_type: str,
        source_id: uuid.UUID,
        content_hash: str,
        embedding: list[float],
        model: str,
        dimension: int,
    ) -> Embedding:
        self.upsert_calls.append(
            (source_type, source_id, content_hash, embedding, model, dimension)
        )
        emb = Embedding(
            id=uuid.uuid4(),
            source_type=source_type,
            source_id=source_id,
            content_hash=content_hash,
            embedding=embedding,
            model=model,
            dimension=dimension,
            generated_at=datetime.now(UTC),
        )
        self._embeddings[(source_type, source_id, model)] = emb
        return emb

    async def search(
        self,
        query_embedding: list[float],
        *,
        source_type: str | None = None,
        source_ids: set[uuid.UUID] | None = None,
        threshold: float = 0.7,
        limit: int = 20,
        model: str | None = None,
    ) -> list[SearchRow]:
        raise NotImplementedError

    async def delete(self, source_type: str, source_id: uuid.UUID) -> None:
        raise NotImplementedError

    async def get_status(
        self,
        source_type: str,
        source_ids: set[uuid.UUID],
    ) -> EmbeddingStats:
        raise NotImplementedError

    async def batch_upsert(
        self,
        items: list[tuple[str, uuid.UUID, str, list[float], str, int]],
    ) -> int:
        raise NotImplementedError

    def seed(self, source_type: str, source_id: uuid.UUID, content_hash: str, model: str) -> None:
        """Pre-populate an existing embedding."""
        emb = Embedding(
            id=uuid.uuid4(),
            source_type=source_type,
            source_id=source_id,
            content_hash=content_hash,
            embedding=[0.0] * 1536,
            model=model,
            dimension=1536,
            generated_at=datetime.now(UTC),
        )
        self._embeddings[(source_type, source_id, model)] = emb


# ---------------------------------------------------------------------------
# Idempotency tests
# ---------------------------------------------------------------------------


class TestIdempotentSkip:
    @patch("narrare.embeddings.tasks.embed_texts")
    async def test_skips_when_content_unchanged(self, mock_embed: AsyncMock) -> None:
        repo = FakeEmbeddingRepo()
        source_id = uuid.uuid4()
        content = "unchanged content"
        content_hash = compute_content_hash(content)

        repo.seed("kb_entry", source_id, content_hash, "text-embedding-3-small")

        result = await run_embed_source(
            "kb_entry",
            source_id,
            content,
            repo=repo,
        )

        assert result is False
        mock_embed.assert_not_called()
        assert len(repo.upsert_calls) == 0

    @patch("narrare.embeddings.tasks.embed_texts")
    async def test_generates_when_content_changed(self, mock_embed: AsyncMock) -> None:
        mock_embed.return_value = [[0.1] * 1536]
        repo = FakeEmbeddingRepo()
        source_id = uuid.uuid4()

        repo.seed("kb_entry", source_id, "old_hash", "text-embedding-3-small")

        result = await run_embed_source(
            "kb_entry",
            source_id,
            "new content",
            repo=repo,
        )

        assert result is True
        mock_embed.assert_called_once()
        assert len(repo.upsert_calls) == 1

    @patch("narrare.embeddings.tasks.embed_texts")
    async def test_generates_when_no_existing_embedding(self, mock_embed: AsyncMock) -> None:
        mock_embed.return_value = [[0.1] * 1536]
        repo = FakeEmbeddingRepo()

        result = await run_embed_source(
            "kb_entry",
            uuid.uuid4(),
            "new content",
            repo=repo,
        )

        assert result is True
        mock_embed.assert_called_once()


# ---------------------------------------------------------------------------
# Retry tests
# ---------------------------------------------------------------------------


class TestRetryBehavior:
    @patch("narrare.embeddings.tasks.asyncio.sleep", new_callable=AsyncMock)
    @patch("narrare.embeddings.tasks.embed_texts")
    async def test_retries_on_failure_then_succeeds(
        self,
        mock_embed: AsyncMock,
        mock_sleep: AsyncMock,
    ) -> None:
        # Fail twice, succeed on third attempt
        mock_embed.side_effect = [Exception("fail 1"), Exception("fail 2"), [[0.1] * 1536]]
        repo = FakeEmbeddingRepo()

        result = await run_embed_source(
            "kb_entry",
            uuid.uuid4(),
            "content",
            repo=repo,
        )

        assert result is True
        assert mock_embed.call_count == 3
        assert mock_sleep.call_count == 2

    @patch("narrare.embeddings.tasks.asyncio.sleep", new_callable=AsyncMock)
    @patch("narrare.embeddings.tasks.embed_texts")
    async def test_raises_after_max_retries(
        self,
        mock_embed: AsyncMock,
        mock_sleep: AsyncMock,
    ) -> None:
        mock_embed.side_effect = Exception("permanent failure")
        repo = FakeEmbeddingRepo()

        with pytest.raises(EmbeddingError, match="3 retries"):
            await run_embed_source(
                "kb_entry",
                uuid.uuid4(),
                "content",
                repo=repo,
            )

        # Should have tried initial + 3 retries = 4 attempts
        assert mock_embed.call_count == 4

    @patch("narrare.embeddings.tasks.asyncio.sleep", new_callable=AsyncMock)
    @patch("narrare.embeddings.tasks.embed_texts")
    async def test_retry_uses_exponential_backoff(
        self,
        mock_embed: AsyncMock,
        mock_sleep: AsyncMock,
    ) -> None:
        mock_embed.side_effect = [
            Exception("fail 1"),
            Exception("fail 2"),
            Exception("fail 3"),
            Exception("fail 4"),
        ]
        repo = FakeEmbeddingRepo()

        with pytest.raises(EmbeddingError):
            await run_embed_source(
                "kb_entry",
                uuid.uuid4(),
                "content",
                repo=repo,
            )

        # Check backoff delays: 30s, 120s, 300s
        sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
        assert sleep_calls == [30.0, 120.0, 300.0]


# ---------------------------------------------------------------------------
# Success path tests
# ---------------------------------------------------------------------------


class TestSuccessPath:
    @patch("narrare.embeddings.tasks.embed_texts")
    async def test_succeeds_on_first_attempt(
        self,
        mock_embed: AsyncMock,
    ) -> None:
        mock_embed.return_value = [[0.1] * 1536]
        repo = FakeEmbeddingRepo()

        result = await run_embed_source(
            "kb_entry",
            uuid.uuid4(),
            "content",
            repo=repo,
        )

        assert result is True
        assert mock_embed.call_count == 1
        assert len(repo.upsert_calls) == 1

    @patch("narrare.embeddings.tasks.embed_texts")
    async def test_uses_custom_model(
        self,
        mock_embed: AsyncMock,
    ) -> None:
        mock_embed.return_value = [[0.1] * 3072]
        repo = FakeEmbeddingRepo()

        result = await run_embed_source(
            "kb_entry",
            uuid.uuid4(),
            "content",
            repo=repo,
            model="text-embedding-3-large",
            dimension=3072,
        )

        assert result is True
        mock_embed.assert_called_with(["content"], model="text-embedding-3-large")
        assert repo.upsert_calls[0][4] == "text-embedding-3-large"
        assert repo.upsert_calls[0][5] == 3072
