"""Tests for context/proactive_service.py — graph-neighbor boost.

Verifies that entities connected (via KB relationships) to name-matched
entities receive a score boost in ``_build_candidates``. The graph signal
is a *booster* for candidates already present from embedding search — it
never creates new candidates on its own (hybrid scoring approach).

See: graph-neighbor boosting spec in ProactiveContextService.suggest().
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID, uuid4

from narrare_core.context.proactive_service import (
    _GRAPH_NEIGHBOR_BOOST,
    _NAME_MATCH_BOOST,
    ProactiveContextService,
)
from narrare_core.context.suggestion import EntityMetadata
from narrare_core.embeddings.store import EmbeddingStats, SearchResult

# ---------------------------------------------------------------------------
# Helpers (duplicated from sibling test files for file independence)
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


NOVEL_ID = _uuid()


# ---------------------------------------------------------------------------
# _build_candidates — graph-neighbor boost
# ---------------------------------------------------------------------------


class TestBuildCandidatesGraphBoost:
    """Graph-connected entities (to name-matched ones) get a similarity boost."""

    def test_entity_connections_boosts_connected_candidate(self) -> None:
        """A candidate connected to a name-matched entity gets +_GRAPH_NEIGHBOR_BOOST."""
        service = ProactiveContextService(embedding_store=FakeEmbeddingStore())
        matched_id = _uuid()
        connected_id = _uuid()

        candidates = service._build_candidates(
            search_results=[_result(source_id=connected_id, score=0.5)],
            matched_entry_ids={matched_id},
            entity_metadata={
                matched_id: _meta(name="Aria"),
                connected_id: _meta(name="Bran"),
            },
            entity_connections={matched_id: {connected_id}},
        )

        assert candidates[connected_id].similarity == 0.5 + _GRAPH_NEIGHBOR_BOOST

    def test_graph_boost_does_not_create_new_candidates(self) -> None:
        """A connected entity absent from embedding results is NOT added.

        Graph boost only elevates EXISTING candidates — it must never inject
        entities that have no embedding similarity score.
        """
        service = ProactiveContextService(embedding_store=FakeEmbeddingStore())
        matched_id = _uuid()
        connected_id = _uuid()  # not in search_results, not name-matched

        candidates = service._build_candidates(
            search_results=[],
            matched_entry_ids={matched_id},
            entity_metadata={matched_id: _meta(name="Aria")},
            entity_connections={matched_id: {connected_id}},
        )

        # matched_id becomes a name-only candidate; connected_id must NOT appear
        assert connected_id not in candidates

    def test_no_graph_boost_when_entity_connections_none(self) -> None:
        """Backward compat: entity_connections=None → identical behaviour (no boost)."""
        service = ProactiveContextService(embedding_store=FakeEmbeddingStore())
        matched_id = _uuid()
        connected_id = _uuid()

        candidates = service._build_candidates(
            search_results=[_result(source_id=connected_id, score=0.5)],
            matched_entry_ids={matched_id},
            entity_metadata={
                matched_id: _meta(name="Aria"),
                connected_id: _meta(name="Bran"),
            },
            entity_connections=None,
        )

        # No graph data → no boost, similarity stays at the raw embedding score
        assert candidates[connected_id].similarity == 0.5

    def test_no_graph_boost_when_matched_entity_has_no_connections(self) -> None:
        """A matched entity with an empty (or absent) connection set boosts nothing."""
        service = ProactiveContextService(embedding_store=FakeEmbeddingStore())
        matched_id = _uuid()
        connected_id = _uuid()

        candidates = service._build_candidates(
            search_results=[_result(source_id=connected_id, score=0.5)],
            matched_entry_ids={matched_id},
            entity_metadata={
                matched_id: _meta(name="Aria"),
                connected_id: _meta(name="Bran"),
            },
            entity_connections={matched_id: set()},
        )

        assert candidates[connected_id].similarity == 0.5

    def test_graph_boost_additive_with_name_match_boost(self) -> None:
        """A candidate that is BOTH name-matched AND graph-connected gets both boosts.

        Order of operations in _build_candidates:
          1. name-match boost applied in the embedding-results loop
          2. graph-neighbor boost applied afterwards
        So an entity with raw score 0.5 that is name-matched (0.5 + 0.2 = 0.7)
        and connected to a matched entity (0.7 + 0.15 = 0.85) ends at 0.85.
        """
        service = ProactiveContextService(embedding_store=FakeEmbeddingStore())
        matched_a = _uuid()
        matched_b = _uuid()  # B is itself name-matched AND connected to A

        candidates = service._build_candidates(
            search_results=[_result(source_id=matched_b, score=0.5)],
            matched_entry_ids={matched_a, matched_b},
            entity_metadata={
                matched_a: _meta(name="Aria"),
                matched_b: _meta(name="Bran"),
            },
            entity_connections={matched_a: {matched_b}},
        )

        expected = 0.5 + _NAME_MATCH_BOOST + _GRAPH_NEIGHBOR_BOOST  # 0.85
        assert candidates[matched_b].similarity == expected

    def test_graph_boost_clamped_to_one(self) -> None:
        """Boosted similarity never exceeds 1.0."""
        service = ProactiveContextService(embedding_store=FakeEmbeddingStore())
        matched_id = _uuid()
        connected_id = _uuid()

        # raw 0.95 + 0.15 = 1.10 → must clamp to 1.0
        candidates = service._build_candidates(
            search_results=[_result(source_id=connected_id, score=0.95)],
            matched_entry_ids={matched_id},
            entity_metadata={
                matched_id: _meta(name="Aria"),
                connected_id: _meta(name="Bran"),
            },
            entity_connections={matched_id: {connected_id}},
        )

        assert candidates[connected_id].similarity == 1.0


# ---------------------------------------------------------------------------
# suggest() — end-to-end parameter threading
# ---------------------------------------------------------------------------


class TestSuggestGraphBoostIntegration:
    """The entity_connections parameter flows from suggest() into scoring."""

    async def test_suggest_with_entity_connections_higher_similarity(self) -> None:
        """Providing entity_connections raises the connected entity's similarity.

        Same inputs run twice — once with entity_connections, once without —
        and the connected entity's Suggestion.similarity must be strictly
        higher when graph data is supplied.
        """
        matched_id = _uuid()
        connected_id = _uuid()
        meta = {
            matched_id: _meta(name="Aria"),
            connected_id: _meta(name="Bran"),
        }
        store = FakeEmbeddingStore(results=[_result(source_id=connected_id, score=0.5)])
        service = ProactiveContextService(embedding_store=store)

        # Without graph data (backward compat)
        result_without = await service.suggest(
            "Aria walked through the forest.",
            novel_id=NOVEL_ID,
            entity_names=["Aria"],
            entity_metadata=meta,
            entity_connections=None,
        )
        sim_without = next(s.similarity for s in result_without if s.entry_id == connected_id)

        # With graph data: Bran is connected to the name-matched Aria
        result_with = await service.suggest(
            "Aria walked through the forest.",
            novel_id=NOVEL_ID,
            entity_names=["Aria"],
            entity_metadata=meta,
            entity_connections={matched_id: {connected_id}},
        )
        sim_with = next(s.similarity for s in result_with if s.entry_id == connected_id)

        assert sim_with == sim_without + _GRAPH_NEIGHBOR_BOOST
        assert sim_with > sim_without
