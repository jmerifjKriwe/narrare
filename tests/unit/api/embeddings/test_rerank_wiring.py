"""Unit tests for the opt-in rerank stage in ``EmbeddingService.search``.

ADR-090 plan F5 service-level contract:

- Default-off invariance: flag off = byte-identical search path — the
  repository sees exactly ``limit``, the reranker/text fetcher are never
  called, and the hybrid order survives untouched.
- Flag on (RULE-18b): the first stage overfetches ``min(limit * 4, 100)``,
  candidate texts are fetched, the fake reranker's order wins, and the
  result is cut to top-N.
- Degradation (RULE-11): a rerank/text-fetch failure at search time emits
  exactly ONE ``embedding_rerank_degraded`` warning and that request
  returns the pre-rerank top-N — search never gains a new failure mode.

Fakes at the ``Reranker`` Protocol boundary (``tests/fakes``) — no
checkpoint download; DI wiring has its own file
(``test_rerank_wiring_di.py``).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from structlog.testing import capture_logs

from narrare.embeddings.service import EmbeddingService
from tests.fakes import FakeEmbeddingRepository, FakeReranker, FakeTextFetcher

_SEEDED_MODEL = "text-embedding-3-small"


# ---------------------------------------------------------------------------
# Helpers + fixtures
# ---------------------------------------------------------------------------


async def _seed_entries(repo: FakeEmbeddingRepository, count: int) -> list[UUID]:
    """Seed ``count`` kb_entry embeddings; returns ids in insertion order.

    The fake search returns equal similarity (0.95) for every row, so the
    hybrid ranking keeps insertion order (stable sort) — the pre-rerank
    order is exactly the seed order.
    """
    ids: list[UUID] = []
    for index in range(count):
        source_id = uuid4()
        await repo.upsert("kb_entry", source_id, f"hash-{index}", [0.2] * 1536, _SEEDED_MODEL, 1536)
        ids.append(source_id)
    return ids


def _texts_for(ids: list[UUID]) -> dict[UUID, str]:
    return {source_id: f"text-{index}" for index, source_id in enumerate(ids)}


def _search_calls(repo: FakeEmbeddingRepository) -> list[dict[str, object]]:
    return [call.kwargs for call in repo.calls if call.method == "search"]


@pytest.fixture
def fake_reranker() -> FakeReranker:
    return FakeReranker()


@pytest.fixture
def fake_fetcher() -> FakeTextFetcher:
    return FakeTextFetcher()


@pytest.fixture
def wired_service(
    fake_repo: FakeEmbeddingRepository,
    fake_reranker: FakeReranker,
    fake_fetcher: FakeTextFetcher,
) -> EmbeddingService:
    """Service wired for the rerank stage (the flag still gates it)."""
    return EmbeddingService(fake_repo, reranker=fake_reranker, text_fetcher=fake_fetcher)


# ---------------------------------------------------------------------------
# Default-off invariance
# ---------------------------------------------------------------------------


class TestRerankDisabled:
    @patch("narrare.embeddings.service.embed_texts")
    async def test_rerank_disabled_is_byte_identical(
        self,
        mock_embed: MagicMock,
        wired_service: EmbeddingService,
        fake_repo: FakeEmbeddingRepository,
        fake_reranker: FakeReranker,
        fake_fetcher: FakeTextFetcher,
    ) -> None:
        """Flag off (default): byte-identical path — repo sees ``limit``, no stage calls."""
        mock_embed.return_value = [[0.1] * 1536]
        ids = await _seed_entries(fake_repo, 3)

        results = await wired_service.search("query", limit=2)

        # Same values as the pre-rerank path: hybrid (insertion) order cut to limit.
        assert [(r.source_id, r.source_type, r.score, r.content_hash) for r in results] == [
            (ids[0], "kb_entry", 0.95, "hash-0"),
            (ids[1], "kb_entry", 0.95, "hash-1"),
        ]
        # The repository received exactly ``limit`` — no overfetch.
        search_calls = _search_calls(fake_repo)
        assert len(search_calls) == 1
        assert search_calls[0]["limit"] == 2
        # The stage components were never consulted.
        assert fake_reranker.calls == []
        assert fake_fetcher.requests == []

    @patch("narrare.embeddings.service.embed_texts")
    async def test_flag_on_without_components_is_inert(
        self,
        mock_embed: MagicMock,
        rerank_on: None,
        fake_repo: FakeEmbeddingRepository,
    ) -> None:
        """Flag on but service unwired (the untouched construction sites): flag-off path."""
        mock_embed.return_value = [[0.1] * 1536]
        ids = await _seed_entries(fake_repo, 3)
        service = EmbeddingService(fake_repo)

        results = await service.search("query", limit=2)

        assert [r.source_id for r in results] == ids[:2]
        assert _search_calls(fake_repo)[0]["limit"] == 2


# ---------------------------------------------------------------------------
# Flag on — overfetch, rerank, cut
# ---------------------------------------------------------------------------


class TestRerankStageActive:
    @patch("narrare.embeddings.service.embed_texts")
    async def test_rerank_enabled_overfetches_then_cuts(
        self,
        mock_embed: MagicMock,
        rerank_on: None,
        wired_service: EmbeddingService,
        fake_repo: FakeEmbeddingRepository,
        fake_reranker: FakeReranker,
        fake_fetcher: FakeTextFetcher,
    ) -> None:
        """Flag on: repo gets ``limit * 4``; the fake rerank order wins; cut to top-N."""
        mock_embed.return_value = [[0.1] * 1536]
        ids = await _seed_entries(fake_repo, 10)
        fake_fetcher.texts = _texts_for(ids)
        # Score by seed index → rerank order is the reverse of hybrid order.
        fake_reranker.scores = {source_id: float(index) for index, source_id in enumerate(ids)}

        results = await wired_service.search("query", limit=3)

        assert _search_calls(fake_repo)[0]["limit"] == 12  # min(3 * 4, 100)
        assert len(fake_reranker.calls) == 1
        query, candidates, top_n = fake_reranker.calls[0]
        assert query == "query"
        assert top_n == 3
        assert [candidate.text for candidate in candidates] == [f"text-{i}" for i in range(10)]
        assert [r.source_id for r in results] == [ids[9], ids[8], ids[7]]

    @patch("narrare.embeddings.service.embed_texts")
    async def test_overfetch_is_capped_at_100(
        self,
        mock_embed: MagicMock,
        rerank_on: None,
        wired_service: EmbeddingService,
        fake_repo: FakeEmbeddingRepository,
    ) -> None:
        """The first-stage fetch is capped at 100 rows regardless of ``limit * 4``."""
        mock_embed.return_value = [[0.1] * 1536]
        await _seed_entries(fake_repo, 2)

        await wired_service.search("query", limit=30)

        assert _search_calls(fake_repo)[0]["limit"] == 100

    @patch("narrare.embeddings.service.embed_texts")
    async def test_textless_candidates_keep_hybrid_position_after_reranked(
        self,
        mock_embed: MagicMock,
        rerank_on: None,
        wired_service: EmbeddingService,
        fake_repo: FakeEmbeddingRepository,
        fake_reranker: FakeReranker,
        fake_fetcher: FakeTextFetcher,
    ) -> None:
        """Candidates without text fall back to hybrid order, after the reranked subset."""
        mock_embed.return_value = [[0.1] * 1536]
        ids = await _seed_entries(fake_repo, 10)
        fake_fetcher.texts = _texts_for(ids[:5])  # only the first five have text
        fake_reranker.scores = {source_id: float(index) for index, source_id in enumerate(ids[:5])}

        results = await wired_service.search("query", limit=8)

        # Reranked subset (score order) first, then the textless five in
        # hybrid order, cut to 8.
        assert [r.source_id for r in results] == [
            ids[4],
            ids[3],
            ids[2],
            ids[1],
            ids[0],
            ids[5],
            ids[6],
            ids[7],
        ]


# ---------------------------------------------------------------------------
# Degradation (RULE-11) — loud, never a new search failure mode
# ---------------------------------------------------------------------------


class TestRerankDegradation:
    @patch("narrare.embeddings.service.embed_texts")
    async def test_rerank_failure_degrades_to_pre_rerank_order(
        self,
        mock_embed: MagicMock,
        rerank_on: None,
        wired_service: EmbeddingService,
        fake_repo: FakeEmbeddingRepository,
        fake_reranker: FakeReranker,
    ) -> None:
        """Checkpoint load / scoring failure → ONE warning, pre-rerank top-N."""
        mock_embed.return_value = [[0.1] * 1536]
        ids = await _seed_entries(fake_repo, 5)
        fake_reranker.error = RuntimeError("encoder load failed")

        with capture_logs() as logs:
            results = await wired_service.search("query", limit=3)

        assert [r.source_id for r in results] == ids[:3]
        degraded = [log for log in logs if log["event"] == "embedding_rerank_degraded"]
        assert len(degraded) == 1
        assert degraded[0]["log_level"] == "warning"
        assert degraded[0]["error_type"] == "RuntimeError"

    @patch("narrare.embeddings.service.embed_texts")
    async def test_text_fetch_failure_degrades_to_pre_rerank_order(
        self,
        mock_embed: MagicMock,
        rerank_on: None,
        wired_service: EmbeddingService,
        fake_repo: FakeEmbeddingRepository,
        fake_fetcher: FakeTextFetcher,
    ) -> None:
        """Text-fetch failure → ONE warning, pre-rerank top-N."""
        mock_embed.return_value = [[0.1] * 1536]
        ids = await _seed_entries(fake_repo, 5)
        fake_fetcher.error = RuntimeError("db unavailable")

        with capture_logs() as logs:
            results = await wired_service.search("query", limit=3)

        assert [r.source_id for r in results] == ids[:3]
        degraded = [log for log in logs if log["event"] == "embedding_rerank_degraded"]
        assert len(degraded) == 1
        assert degraded[0]["reason"] == "text_fetch_failed"
