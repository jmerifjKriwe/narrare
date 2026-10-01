"""Embedding search tail — hybrid ranking + opt-in rerank stage (ADR-090).

Extracted from ``service.py`` for RULE-04 (the file sat at its 300-line
hard limit; this mirrors the ``search_queries.py`` repository-side and
``embedding_hooks.py`` extractions). The module owns the search pipeline
after the pgvector fetch:

1. **First stage (unchanged shipped behavior):** build ``ScoredCandidate``s
   from the search rows and hybrid-rank them (``rank_candidates``).
2. **Second stage (ADR-090, opt-in):** when the service was wired with a
   ``Reranker`` AND an async ``TextFetcher`` AND
   ``CoreSettings.embedding_rerank_enabled`` is on, candidate texts are
   fetched, the local reranker reorders (its score is the new sort key),
   and the result is cut to top-N. Any other combination returns the
   untouched pre-rerank order.

Degradation lives here (ADR-090 Decision 6, RULE-11): a rerank-side
failure (text fetch, checkpoint load, scoring) emits exactly ONE
structured ``embedding_rerank_degraded`` warning and that request returns
the pre-rerank top-N — the base pgvector + hybrid path never gains a new
failure mode. Candidates whose text cannot be supplied keep their
first-stage position after the reranked subset.

RULE-06: one responsibility — the search tail pipeline only; embedding
generation and repository access stay in ``service.py`` / the repository.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

from narrare_core.embeddings.rerank import RerankCandidate
from narrare_core.embeddings.scoring import ScoredCandidate, compute_hybrid_score, rank_candidates
from narrare_core.embeddings.store import SearchResult
from narrare_core.settings import get_core_settings

if TYPE_CHECKING:
    from collections.abc import Sequence

    from narrare.embeddings.contracts import TextFetcher
    from narrare.embeddings.search_queries import SearchRow
    from narrare_core.embeddings.rerank import Reranker
    from narrare_core.embeddings.scoring import ScoringConfig

logger = structlog.get_logger(__name__)

__all__ = [
    "RerankStageLimits",
    "rank_and_maybe_rerank",
]


@dataclass(frozen=True, slots=True)
class RerankStageLimits:
    """First-stage fetch limits for the rerank stage (ADR-090 Option 0).

    The cap implements the ADR-090 CPU budget (K <= ~50 candidates on
    CPU); changing it is a Review-Trigger decision (ADR-090 "Latency
    budget"), not an operator knob — RULE-18 wants it named, not inline.
    """

    overfetch_factor: int = 4
    """First-stage overfetch multiple (plan F5: ``limit * 4``)."""

    max_overfetch: int = 100
    """Hard cap on the first-stage fetch size."""


_RERANK_STAGE_LIMITS = RerankStageLimits()


def prepare_rerank_stage(
    limit: int,
    reranker: Reranker | None,
    text_fetcher: TextFetcher | None,
) -> tuple[Reranker | None, TextFetcher | None, int]:
    """Resolve the rerank stage for one search call (ADR-090 D5).

    The stage is active only when components are wired AND the opt-in flag
    is on. When active, the returned fetch limit overfetches so the
    reranker can cut to ``limit``; otherwise the components are dropped
    (``None``) and the plain ``limit`` keeps the byte-identical first
    stage.

    Returns:
        ``(reranker, text_fetcher, search_limit)`` — the components are
        ``None`` when the stage must stay inert.
    """
    stage_active = (
        get_core_settings().embedding_rerank_enabled
        and reranker is not None
        and text_fetcher is not None
    )
    if not stage_active:
        return None, None, limit
    return (
        reranker,
        text_fetcher,
        min(
            limit * _RERANK_STAGE_LIMITS.overfetch_factor,
            _RERANK_STAGE_LIMITS.max_overfetch,
        ),
    )


async def rank_and_maybe_rerank(
    query: str,
    raw_results: Sequence[SearchRow],
    *,
    limit: int,
    reranker: Reranker | None,
    text_fetcher: TextFetcher | None,
    scoring_config: ScoringConfig | None = None,
) -> list[SearchResult]:
    """Hybrid-rank the search rows; rerank first when the stage is wired.

    Args:
        query: The search query (reranker input).
        raw_results: Rows from the repository search (similarity-desc).
        limit: Final result count.
        reranker: Wired reranker, or ``None`` for the plain hybrid path.
        text_fetcher: Wired candidate-text fetcher, or ``None``.
        scoring_config: Hybrid scoring weights (defaults when ``None``).

    Returns:
        ``SearchResult``s in final order: rerank order when the stage ran
        (textless candidates appended in hybrid order), else the hybrid
        order — always truncated to ``limit``.
    """
    if not raw_results:
        return []

    candidates = [
        ScoredCandidate(
            source_id=row.embedding.source_id,
            source_type=row.embedding.source_type,
            similarity=row.similarity,
            usage_count=row.usage_count,
            last_referenced_at=row.last_referenced_at,
            content_hash=row.embedding.content_hash,
        )
        for row in raw_results
    ]

    ranked = rank_candidates(candidates, config=scoring_config)

    if reranker is None or text_fetcher is None:
        return _to_search_results(ranked[:limit])
    return await _apply_rerank_stage(
        query,
        ranked,
        reranker=reranker,
        text_fetcher=text_fetcher,
        limit=limit,
        scoring_config=scoring_config,
    )


async def _apply_rerank_stage(
    query: str,
    ranked: list[ScoredCandidate],
    *,
    reranker: Reranker,
    text_fetcher: TextFetcher,
    limit: int,
    scoring_config: ScoringConfig | None = None,
) -> list[SearchResult]:
    """Fetch texts, rerank, cut to top-N — degrading loudly on failure."""
    if not ranked:
        return []

    try:
        texts = await text_fetcher([candidate.source_id for candidate in ranked])
    except Exception as exc:
        logger.warning(
            "embedding_rerank_degraded",
            reason="text_fetch_failed",
            error_type=type(exc).__name__,
            error=str(exc),
        )
        return _to_search_results(ranked[:limit])

    max_usage = max(candidate.usage_count for candidate in ranked)
    rerankable = [
        RerankCandidate(
            source_id=candidate.source_id,
            source_type=candidate.source_type,
            text=texts[candidate.source_id],
            base_score=compute_hybrid_score(candidate, max_usage=max_usage, config=scoring_config),
        )
        for candidate in ranked
        if candidate.source_id in texts
    ]
    # Textless candidates (e.g. deleted KB row, empty body) have no rerank
    # score — they keep their first-stage position, after the reranked subset.
    textless_ids = [candidate.source_id for candidate in ranked if candidate.source_id not in texts]
    if textless_ids:
        logger.debug("embedding_rerank_textless_candidates", count=len(textless_ids))

    try:
        reranked = await reranker.rerank(query, rerankable, top_n=limit)
    except Exception as exc:
        logger.warning(
            "embedding_rerank_degraded",
            reason="rerank_failed",
            error_type=type(exc).__name__,
            error=str(exc),
        )
        return _to_search_results(ranked[:limit])

    by_id = {candidate.source_id: candidate for candidate in ranked}
    ordered_ids = [candidate.source_id for candidate in reranked]
    final_ids = (ordered_ids + textless_ids)[:limit]
    return _to_search_results([by_id[source_id] for source_id in final_ids])


def _to_search_results(ranked: Sequence[ScoredCandidate]) -> list[SearchResult]:
    """Map ranked candidates to ``SearchResult`` (score = first-stage similarity)."""
    return [
        SearchResult(
            source_id=candidate.source_id,
            source_type=candidate.source_type,
            score=candidate.similarity,  # Use similarity score from ranking
            content_hash=candidate.content_hash,
        )
        for candidate in ranked
    ]
