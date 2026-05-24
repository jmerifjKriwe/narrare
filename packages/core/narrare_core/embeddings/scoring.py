"""Hybrid search scoring for embedding result ranking.

Combines three signals into a single score:
- **Similarity** (cosine): How semantically close is the candidate to the query.
- **Usage**: How often the candidate has been referenced (behavioral signal).
- **Recency**: How recently the candidate was referenced (temporal signal).

The default weights (0.50 / 0.30 / 0.20) follow an established information-
retrieval pattern and are configurable via ``ScoringConfig``.

See: openspec/changes/infra-004-embedding-store/design.md (D3: hybrid formula)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ScoringConfig:
    """Weights and parameters for hybrid search scoring.

    Attributes:
        similarity_weight: Weight for cosine similarity (0-1).
        usage_weight: Weight for normalized usage count (0-1).
        recency_weight: Weight for time-decay recency (0-1).
        half_life_days: Days for recency score to decay to 0.5.
        baseline_recency: Recency score for entries never referenced.
    """

    similarity_weight: float = 0.50
    usage_weight: float = 0.30
    recency_weight: float = 0.20
    half_life_days: float = 14.0
    baseline_recency: float = 0.1


# ---------------------------------------------------------------------------
# Scored candidate
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ScoredCandidate:
    """A candidate for hybrid scoring.

    Attributes:
        source_id: UUID of the source entity.
        source_type: Content type label (e.g. "kb_entry").
        similarity: Cosine similarity score from pgvector (0-1).
        usage_count: Number of times this entry has been referenced.
        last_referenced_at: Timestamp of last reference, or None if never.
        content_hash: SHA-256 hash of the embedded content.
    """

    source_id: UUID
    source_type: str
    similarity: float
    usage_count: int
    last_referenced_at: datetime | None
    content_hash: str = ""


# ---------------------------------------------------------------------------
# Ranking function
# ---------------------------------------------------------------------------

_DEFAULT_CONFIG = ScoringConfig()


def rank_candidates(
    candidates: list[ScoredCandidate],
    config: ScoringConfig | None = None,
    now: datetime | None = None,
) -> list[ScoredCandidate]:
    """Rank candidates using hybrid scoring formula.

    The final score for each candidate is::

        score = similarity_weight * similarity
              + usage_weight * usage_score
              + recency_weight * recency_score

    Where:
        usage_score = min(usage_count / max(max_usage, 1), 1.0)
        recency_score = 0.5 ** (days_since / half_life_days)
            or baseline_recency if never referenced.

    Candidates are returned sorted by final score descending. Candidates
    with identical scores maintain their original relative order (stable sort).

    Args:
        candidates: List of candidates to rank.
        config: Scoring configuration. Uses defaults if None.
        now: Current datetime for recency calculation. Defaults to
            ``datetime.now()`` if None.

    Returns:
        New list of candidates sorted by hybrid score descending.
    """
    if not candidates:
        return []

    cfg = config or _DEFAULT_CONFIG
    reference_time = now or datetime.now()

    # Compute max usage count for normalization
    max_usage = max(c.usage_count for c in candidates)

    # Compute final score for each candidate
    scored: list[tuple[float, ScoredCandidate]] = []
    for candidate in candidates:
        usage_score = min(candidate.usage_count / max(max_usage, 1), 1.0)

        if candidate.last_referenced_at is not None:
            days_since = (reference_time - candidate.last_referenced_at).days
            recency_score = 0.5 ** (days_since / cfg.half_life_days)
        else:
            recency_score = cfg.baseline_recency

        final_score = (
            cfg.similarity_weight * candidate.similarity
            + cfg.usage_weight * usage_score
            + cfg.recency_weight * recency_score
        )
        scored.append((final_score, candidate))

    # Stable sort by score descending
    scored.sort(key=lambda pair: pair[0], reverse=True)

    return [candidate for _, candidate in scored]
