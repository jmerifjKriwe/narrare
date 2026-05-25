"""Tests for context/proactive_service.py — ProactiveContextService."""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID, uuid4

from narrare_core.context.proactive_service import ProactiveContextService
from narrare_core.context.suggestion import EntityMetadata, Suggestion
from narrare_core.embeddings.store import EmbeddingStats, SearchResult

# ---------------------------------------------------------------------------
# Helpers
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
# Happy path
# ---------------------------------------------------------------------------


class TestSuggestBasic:
    """Basic suggestion scenarios."""

    async def test_suggest_returns_suggestions(self) -> None:
        """Basic happy path: embedding results become suggestions."""
        sid = _uuid()
        store = FakeEmbeddingStore(results=[_result(source_id=sid, score=0.85)])
        meta = {sid: _meta(name="Aria", entity_type="character")}
        service = ProactiveContextService(embedding_store=store)

        result = await service.suggest(
            "Aria walked through the forest.",
            novel_id=NOVEL_ID,
            entity_names=["Aria"],
            entity_metadata=meta,
        )

        assert len(result) >= 1
        assert isinstance(result[0], Suggestion)
        assert result[0].entry_id == sid

    async def test_suggest_empty_content_and_names(self) -> None:
        """Empty content and no names returns empty list."""
        store = FakeEmbeddingStore(results=[])
        service = ProactiveContextService(embedding_store=store)

        result = await service.suggest(
            "",
            novel_id=NOVEL_ID,
        )

        assert result == []

    async def test_suggest_empty_content_with_names(self) -> None:
        """Empty content with names but no embedding results returns empty."""
        store = FakeEmbeddingStore(results=[])
        service = ProactiveContextService(embedding_store=store)

        result = await service.suggest(
            "",
            novel_id=NOVEL_ID,
            entity_names=["Aria"],
        )

        assert result == []

    async def test_suggest_no_embeddings_with_metadata(self) -> None:
        """No embeddings but name match + metadata produces suggestions."""
        sid = _uuid()
        store = FakeEmbeddingStore(results=[])
        meta = {sid: _meta(name="Aria", entity_type="character")}
        service = ProactiveContextService(embedding_store=store)

        result = await service.suggest(
            "Aria walked through the forest.",
            novel_id=NOVEL_ID,
            entity_names=["Aria"],
            entity_metadata=meta,
        )

        assert len(result) == 1
        assert result[0].entry_id == sid
        assert result[0].reason == "mentioned_in_text"


# ---------------------------------------------------------------------------
# Name match boost
# ---------------------------------------------------------------------------


class TestSuggestNameMatchBoost:
    """Name-matched entries get boosted ranking."""

    async def test_name_match_boosts_ranking(self) -> None:
        """Name-matched entry ranks higher than higher-similarity entry."""
        matched_id = _uuid()
        other_id = _uuid()

        store = FakeEmbeddingStore(
            results=[
                _result(source_id=other_id, score=0.85),
                _result(source_id=matched_id, score=0.75),
            ]
        )
        meta = {
            matched_id: _meta(name="Aria"),
            other_id: _meta(name="Bran"),
        }
        service = ProactiveContextService(embedding_store=store)

        result = await service.suggest(
            "Aria walked through the forest.",
            novel_id=NOVEL_ID,
            entity_names=["Aria"],
            entity_metadata=meta,
        )

        # With name match boost (0.2), matched similarity becomes 0.95
        # vs other at 0.85, so matched should rank higher
        assert result[0].entry_id == matched_id

    async def test_suggest_reason_mentioned_in_text(self) -> None:
        """Name-matched entry gets 'mentioned_in_text' reason."""
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

        assert result[0].reason == "mentioned_in_text"

    async def test_suggest_reason_semantically_similar(self) -> None:
        """Embedding-only entry gets 'semantically_similar' reason."""
        sid = _uuid()
        store = FakeEmbeddingStore(results=[_result(source_id=sid, score=0.9)])
        meta = {sid: _meta(name="Aria")}
        service = ProactiveContextService(embedding_store=store)

        result = await service.suggest(
            "Someone walked through the forest.",
            novel_id=NOVEL_ID,
            entity_names=["Bran"],
            entity_metadata=meta,
        )

        assert result[0].reason == "semantically_similar"


# ---------------------------------------------------------------------------
# Max results
# ---------------------------------------------------------------------------


class TestSuggestMaxResults:
    """max_results truncates the output."""

    async def test_suggest_respects_max_results(self) -> None:
        """Returns at most max_results suggestions."""
        results = [_result(score=0.8 - i * 0.05) for i in range(10)]
        store = FakeEmbeddingStore(results=results)
        service = ProactiveContextService(embedding_store=store)

        result = await service.suggest(
            "Some chapter text.",
            novel_id=NOVEL_ID,
            max_results=3,
        )

        assert len(result) == 3

    async def test_suggest_clamps_max_results_to_100(self) -> None:
        """max_results above 100 is clamped without error."""
        service = ProactiveContextService(embedding_store=FakeEmbeddingStore())

        result = await service.suggest(
            "text",
            novel_id=NOVEL_ID,
            max_results=500,
        )

        assert isinstance(result, list)

    async def test_suggest_clamps_max_results_to_1_minimum(self) -> None:
        """max_results below 1 is clamped to 1."""
        results = [_result(score=0.9)]
        store = FakeEmbeddingStore(results=results)
        service = ProactiveContextService(embedding_store=store)

        result = await service.suggest(
            "Some text",
            novel_id=NOVEL_ID,
            max_results=0,
        )

        assert len(result) == 1
