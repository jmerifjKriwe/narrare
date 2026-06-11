"""Fake embedding repository for unit tests.

Implements EmbeddingRepositoryProtocol from narrare.embeddings.contracts.
Used in unit tests instead of MagicMock — see RULE-TEST-01 in testing-standards.md.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from narrare.embeddings.models import Embedding
from narrare.embeddings.search_queries import SearchRow
from narrare_core.embeddings.store import EmbeddingStats
from tests.fakes._shared import CallRecord


class FakeEmbeddingRepository:
    """In-memory fake for EmbeddingRepositoryProtocol.

    Keyed by (source_type, source_id, model) to match the unique constraint
    on the embeddings table.
    """

    def __init__(self) -> None:
        self._store: dict[tuple[str, uuid.UUID, str], Embedding] = {}
        self.calls: list[CallRecord] = []

    # ------------------------------------------------------------------
    # Protocol methods
    # ------------------------------------------------------------------

    async def upsert(
        self,
        source_type: str,
        source_id: uuid.UUID,
        content_hash: str,
        embedding: list[float],
        model: str,
        dimension: int,
    ) -> Embedding:
        """Insert or update an embedding row."""
        self.calls.append(
            CallRecord(
                "upsert",
                kwargs={
                    "source_type": source_type,
                    "source_id": source_id,
                    "content_hash": content_hash,
                    "model": model,
                    "dimension": dimension,
                },
            )
        )
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
    ) -> list[SearchRow]:
        """Search for similar embeddings using fake similarity scoring."""
        self.calls.append(
            CallRecord(
                "search",
                kwargs={
                    "source_type": source_type,
                    "source_ids": source_ids,
                    "threshold": threshold,
                    "limit": limit,
                    "model": model,
                },
            )
        )
        results: list[SearchRow] = []
        for emb in self._store.values():
            if source_type and emb.source_type != source_type:
                continue
            if model and emb.model != model:
                continue
            if source_ids and emb.source_id not in source_ids:
                continue
            # Fake similarity — always return 0.95 for matching results
            results.append(
                SearchRow(
                    embedding=emb,
                    similarity=0.95,
                    usage_count=0,
                    last_referenced_at=None,
                )
            )
        return results[:limit]

    async def delete(self, source_type: str, source_id: uuid.UUID) -> None:
        """Delete all embeddings for a source entity."""
        self.calls.append(
            CallRecord("delete", kwargs={"source_type": source_type, "source_id": source_id})
        )
        keys_to_delete = [k for k in self._store if k[0] == source_type and k[1] == source_id]
        for key in keys_to_delete:
            del self._store[key]

    async def get_by_source(
        self,
        source_type: str,
        source_id: uuid.UUID,
        model: str | None = None,
    ) -> Embedding | None:
        """Fetch an embedding by source identity."""
        self.calls.append(
            CallRecord(
                "get_by_source",
                kwargs={"source_type": source_type, "source_id": source_id, "model": model},
            )
        )
        for key, emb in self._store.items():
            if key[0] == source_type and key[1] == source_id and (model is None or key[2] == model):
                return emb
        return None

    async def get_status(
        self,
        source_type: str,
        source_ids: set[uuid.UUID],
    ) -> EmbeddingStats:
        """Compute embedding statistics for a set of source entities."""
        self.calls.append(
            CallRecord("get_status", kwargs={"source_type": source_type, "source_ids": source_ids})
        )
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
        """Insert or update multiple embedding rows in a single call."""
        self.calls.append(CallRecord("batch_upsert", kwargs={"items_count": len(items)}))
        for s_type, s_id, c_hash, emb, mdl, dim in items:
            await self.upsert(s_type, s_id, c_hash, emb, mdl, dim)
        return len(items)

    # ------------------------------------------------------------------
    # Assertion helpers
    # ------------------------------------------------------------------

    def call_count(self, method: str) -> int:
        """Count how many times a method was called."""
        return sum(1 for c in self.calls if c.method == method)

    def assert_called(self, method: str, **kwargs: object) -> None:
        """Assert that a method was called with matching kwargs."""
        for call in self.calls:
            if call.method == method and call.matches(kwargs):
                return
        raise AssertionError(f"No call to {method} with {kwargs}")

    def assert_called_once(self, method: str) -> None:
        """Assert that a method was called exactly once."""
        count = self.call_count(method)
        if count != 1:
            raise AssertionError(f"Expected 1 call to {method}, got {count}")

    def assert_not_called(self, method: str) -> None:
        """Assert that a method was never called."""
        count = self.call_count(method)
        if count > 0:
            raise AssertionError(f"Expected 0 calls to {method}, got {count}")
