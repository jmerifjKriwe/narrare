"""Shared fixtures for embedding service unit tests.

Provides ``FakeEmbeddingRepository`` and common fixtures used across
generate, search, and lifecycle test files.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from narrare.embeddings.models import Embedding
from narrare.embeddings.service import EmbeddingService
from narrare_core.embeddings.store import EmbeddingStats


class FakeEmbeddingRepository:
    """In-memory fake implementation of EmbeddingRepositoryProtocol."""

    def __init__(self) -> None:
        self._store: dict[tuple[str, uuid.UUID, str], Embedding] = {}

    async def upsert(
        self,
        source_type: str,
        source_id: uuid.UUID,
        content_hash: str,
        embedding: list[float],
        model: str,
        dimension: int,
    ) -> Embedding:
        key = (source_type, source_id, model)
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
        self._store[key] = emb
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
    ) -> list[tuple[Embedding, float]]:
        results: list[tuple[Embedding, float]] = []
        for emb in self._store.values():
            if source_type and emb.source_type != source_type:
                continue
            if model and emb.model != model:
                continue
            if source_ids and emb.source_id not in source_ids:
                continue
            # Fake similarity — always return 0.95 for matching results
            results.append((emb, 0.95))
        return results[:limit]

    async def delete(self, source_type: str, source_id: uuid.UUID) -> None:
        keys_to_delete = [k for k in self._store if k[0] == source_type and k[1] == source_id]
        for key in keys_to_delete:
            del self._store[key]

    async def get_by_source(
        self,
        source_type: str,
        source_id: uuid.UUID,
        model: str | None = None,
    ) -> Embedding | None:
        for key, emb in self._store.items():
            if key[0] == source_type and key[1] == source_id and (model is None or key[2] == model):
                return emb
        return None

    async def get_status(
        self,
        source_type: str,
        source_ids: set[uuid.UUID],
    ) -> EmbeddingStats:
        total = len(source_ids)
        embedded = sum(
            1 for sid in source_ids if any(k[0] == source_type and k[1] == sid for k in self._store)
        )
        return EmbeddingStats(
            total=total,
            embedded=embedded,
            pending=total - embedded,
            failed=0,
            coverage_percentage=round((embedded / total) * 100.0, 1) if total > 0 else 0.0,
        )

    async def batch_upsert(
        self,
        items: list[tuple[str, uuid.UUID, str, list[float], str, int]],
    ) -> int:
        for s_type, s_id, c_hash, emb, mdl, dim in items:
            await self.upsert(s_type, s_id, c_hash, emb, mdl, dim)
        return len(items)


@pytest.fixture
def fake_repo() -> FakeEmbeddingRepository:
    return FakeEmbeddingRepository()


@pytest.fixture
def service(fake_repo: FakeEmbeddingRepository) -> EmbeddingService:
    return EmbeddingService(fake_repo)
