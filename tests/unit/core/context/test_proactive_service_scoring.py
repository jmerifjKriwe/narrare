"""Tests for context/proactive_service.py — scoring, dedup, and edge cases."""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID, uuid4

from narrare_core.context.proactive_service import ProactiveContextService
from narrare_core.context.suggestion import EntityMetadata
from narrare_core.embeddings.store import EmbeddingStats, SearchResult

# ---------------------------------------------------------------------------
# Helpers (duplicated from test_proactive_service.py for file independence)
# ---------------------------------------------------------------------------


def _uuid() -> UUID:
    return uuid4()


def _result(
    source_id: UUID | None = None,
    score: float = 0.8,
    source_type: str = "kb_entry",
) -> SearchResult:
    return SearchResult(
        source_id=source_id or _uuid(),
        source_type=source_type,
        score=score,
        content_hash="fake_hash",
    )


def _meta(
    name: str = "Aria",
    entity_type: str = "character",
    usage_count: int = 0,
    days_ago: int | None = None,
) -> EntityMetadata:
    last_ref: datetime | None = None
    if days_ago is not None:
        last_ref = datetime(2026, 5, 20, 12, 0, 0) - timedelta(days=days_ago)
    return EntityMetadata(
        name=name,
        entity_type=entity_type,
        usage_count=usage_count,
        last_referenced_at=last_ref,
    )


NOVEL_ID = _uuid()


class FakeEmbeddingStore:
    """Minimal fake implementing EmbeddingStoreProtocol for tests."""

    def __init__(self, results: list[SearchResult] | None = None) -> None:
        self._results = results or []
        self.last_query: str | None = None

    async def search(
        self,
        query: str,
        *,
        source_type: str | None = None,
        novel_id: UUID | None = None,
        threshold: float = 0.7,
        limit: int = 20,
        model: str | None = None,
    ) -> list[SearchResult]:
        self.last_query = query
        return self._results[:limit]

    async def generate(self, source_type: str, source_id: UUID, content: str) -> None:
        pass

    async def delete(self, source_type: str, source_id: UUID) -> None:
        pass

    async def get_status(self, novel_id: UUID) -> EmbeddingStats:
        return EmbeddingStats(total=0, embedded=0, pending=0, failed=0, coverage_percentage=0.0)

    async def reprocess(self, novel_id: UUID, model: str | None = None) -> None:
        pass


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


class TestSuggestDeduplication:
    """Same entry from name match and embedding is not duplicated."""

    async def test_suggest_deduplicates_entries(self) -> None:
        """Entry found by both name and embedding appears once."""
        sid = _uuid()
        store = FakeEmbeddingStore(results=[_result(source_id=sid, score=0.8)])
        meta = {sid: _meta(name="Aria")}
        service = ProactiveContextService(embedding_store=store)

        result = await service.suggest(
            "Aria walked through the forest.",
            novel_id=NOVEL_ID,
            entity_names=["Aria"],
            entity_metadata=meta,
        )

        entry_ids = [s.entry_id for s in result]
        assert entry_ids.count(sid) == 1


# ---------------------------------------------------------------------------
# Metadata derivation
# ---------------------------------------------------------------------------


class TestSuggestMetadataDerivation:
    """entity_names derived from entity_metadata when not provided."""

    async def test_derives_names_from_metadata(self) -> None:
        """When entity_names is None, names are extracted from metadata."""
        sid = _uuid()
        store = FakeEmbeddingStore(results=[_result(source_id=sid, score=0.7)])
        meta = {sid: _meta(name="Aria")}
        service = ProactiveContextService(embedding_store=store)

        result = await service.suggest(
            "Aria walked through the forest.",
            novel_id=NOVEL_ID,
            entity_metadata=meta,
        )

        assert any(s.entry_id == sid and s.reason == "mentioned_in_text" for s in result)


# ---------------------------------------------------------------------------
# Embedding store interaction
# ---------------------------------------------------------------------------


class TestSuggestEmbeddingSearch:
    """Verify the embedding store is called correctly."""

    async def test_passes_chapter_content_as_query(self) -> None:
        """The store.search receives chapter_content as the query."""
        store = FakeEmbeddingStore(results=[])
        service = ProactiveContextService(embedding_store=store)

        await service.suggest(
            "The hero's journey begins.",
            novel_id=NOVEL_ID,
        )

        assert store.last_query == "The hero's journey begins."


# ---------------------------------------------------------------------------
# Relevance score
# ---------------------------------------------------------------------------


class TestSuggestRelevanceScore:
    """relevance_score is the computed hybrid score."""

    async def test_relevance_scores_are_non_negative(self) -> None:
        """All relevance scores are >= 0."""
        results = [_result(score=0.9), _result(score=0.5), _result(score=0.3)]
        store = FakeEmbeddingStore(results=results)
        service = ProactiveContextService(embedding_store=store)

        suggestions = await service.suggest(
            "Some text.",
            novel_id=NOVEL_ID,
        )

        for s in suggestions:
            assert s.relevance_score >= 0.0

    async def test_relevance_scores_descending(self) -> None:
        """Suggestions are sorted by relevance_score descending."""
        results = [_result(score=0.9), _result(score=0.5), _result(score=0.3)]
        store = FakeEmbeddingStore(results=results)
        service = ProactiveContextService(embedding_store=store)

        suggestions = await service.suggest(
            "Some text.",
            novel_id=NOVEL_ID,
        )

        scores = [s.relevance_score for s in suggestions]
        assert scores == sorted(scores, reverse=True)
