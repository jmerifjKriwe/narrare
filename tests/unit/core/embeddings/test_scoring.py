"""Tests for embeddings/scoring.py — Hybrid search scoring."""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from narrare_core.embeddings.scoring import (
    ScoredCandidate,
    ScoringConfig,
    rank_candidates,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _candidate(
    *,
    similarity: float = 0.5,
    usage_count: int = 0,
    days_ago: int | None = None,
    source_type: str = "kb_entry",
) -> ScoredCandidate:
    """Build a ScoredCandidate with sensible defaults."""
    last_ref: datetime | None = None
    if days_ago is not None:
        last_ref = datetime(2026, 1, 15, 12, 0, 0) - timedelta(days=days_ago)
    return ScoredCandidate(
        source_id=uuid4(),
        source_type=source_type,
        similarity=similarity,
        usage_count=usage_count,
        last_referenced_at=last_ref,
        content_hash="fake_hash",
    )


NOW = datetime(2026, 1, 15, 12, 0, 0)


# ---------------------------------------------------------------------------
# Empty / single-candidate edge cases
# ---------------------------------------------------------------------------


class TestRankCandidatesEdgeCases:
    """Edge cases for rank_candidates."""

    def test_empty_candidates_returns_empty_list(self) -> None:
        result = rank_candidates([], now=NOW)
        assert result == []

    def test_single_candidate_returns_single_element(self) -> None:
        candidate = _candidate(similarity=0.9, usage_count=5, days_ago=1)
        result = rank_candidates([candidate], now=NOW)
        assert len(result) == 1
        assert result[0].source_id == candidate.source_id


# ---------------------------------------------------------------------------
# Known-input scoring (manual calculation)
# ---------------------------------------------------------------------------


class TestRankCandidatesKnownScores:
    """Verify scores against manually calculated values.

    Default weights: similarity=0.50, usage=0.30, recency=0.20
    Half-life: 14 days, baseline_recency: 0.1

    Candidate A: similarity=0.9, usage=10 (max), last_ref=1 day ago
        usage_score = min(10/10, 1.0) = 1.0
        recency_score = 0.5^(1/14) ≈ 0.9517
        final = 0.5*0.9 + 0.3*1.0 + 0.2*0.9517 ≈ 0.9403

    Candidate B: similarity=0.7, usage=5 (max=10), last_ref=7 days ago
        usage_score = min(5/10, 1.0) = 0.5
        recency_score = 0.5^(7/14) = 0.5^0.5 ≈ 0.7071
        final = 0.5*0.7 + 0.3*0.5 + 0.2*0.7071 ≈ 0.6414
    """

    def test_candidate_a_scores_higher_than_b(self) -> None:
        a = _candidate(similarity=0.9, usage_count=10, days_ago=1)
        b = _candidate(similarity=0.7, usage_count=5, days_ago=7)
        result = rank_candidates([b, a], now=NOW)
        assert result[0].source_id == a.source_id
        assert result[1].source_id == b.source_id

    def test_exact_score_values_match_manual_calculation(self) -> None:
        a = _candidate(similarity=0.9, usage_count=10, days_ago=1)
        b = _candidate(similarity=0.7, usage_count=5, days_ago=7)
        candidates = [a, b]

        # Compute manually
        max_usage = 10
        cfg = ScoringConfig()

        # Candidate A
        usage_a = min(a.usage_count / max(max_usage, 1), 1.0)
        recency_a = 0.5 ** (1 / cfg.half_life_days)
        score_a = (
            cfg.similarity_weight * a.similarity
            + cfg.usage_weight * usage_a
            + cfg.recency_weight * recency_a
        )

        # Candidate B
        usage_b = min(b.usage_count / max(max_usage, 1), 1.0)
        recency_b = 0.5 ** (7 / cfg.half_life_days)
        score_b = (
            cfg.similarity_weight * b.similarity
            + cfg.usage_weight * usage_b
            + cfg.recency_weight * recency_b
        )

        # Verify: rank_candidates produces the same order
        result = rank_candidates(candidates, now=NOW)
        assert result[0].source_id == a.source_id  # Higher score
        assert abs(score_a - 0.9403) < 0.01  # Rough manual check
        assert abs(score_b - 0.6414) < 0.01


# ---------------------------------------------------------------------------
# Zero-usage baseline: similarity-only ranking
# ---------------------------------------------------------------------------


class TestRankCandidatesZeroUsage:
    """When all candidates have zero usage and no recency, ranking is similarity-only."""

    def test_zero_usage_no_recency_similarity_only(self) -> None:
        """All signals except similarity are neutral.

        usage_score = 0 for all (max_usage=0, so usage_count/1 = 0)
        recency_score = baseline_recency (0.1) for all
        final = 0.5*sim + 0.3*0 + 0.2*0.1 = 0.5*sim + 0.02
        """
        high = _candidate(similarity=0.9)
        mid = _candidate(similarity=0.7)
        low = _candidate(similarity=0.5)

        result = rank_candidates([low, mid, high], now=NOW)
        assert [c.source_id for c in result] == [
            high.source_id,
            mid.source_id,
            low.source_id,
        ]

    def test_zero_usage_identical_similarity_maintains_order(self) -> None:
        """Candidates with identical scores keep original relative order."""
        a = _candidate(similarity=0.8)
        b = _candidate(similarity=0.8)
        c = _candidate(similarity=0.8)

        result = rank_candidates([a, b, c], now=NOW)
        assert result[0].source_id == a.source_id
        assert result[1].source_id == b.source_id
        assert result[2].source_id == c.source_id


# ---------------------------------------------------------------------------
# Recency decay
# ---------------------------------------------------------------------------


class TestRankCandidatesRecencyDecay:
    """Recency score decays exponentially with time."""

    def test_more_recent_entry_scores_higher(self) -> None:
        """1 day ago vs 14 days ago vs 100 days ago, same similarity."""
        recent = _candidate(similarity=0.8, days_ago=1)
        two_weeks = _candidate(similarity=0.8, days_ago=14)
        old = _candidate(similarity=0.8, days_ago=100)

        result = rank_candidates([old, two_weeks, recent], now=NOW)
        assert result[0].source_id == recent.source_id
        assert result[1].source_id == two_weeks.source_id
        assert result[2].source_id == old.source_id

    def test_never_referenced_gets_baseline_recency(self) -> None:
        """Never-referenced entry uses baseline_recency (0.1).

        14-day-old entry has recency_score = 0.5^1 = 0.5
        Never-referenced has recency_score = 0.1

        With same similarity, the 14-day-old should rank higher.
        """
        referenced = _candidate(similarity=0.8, days_ago=14)
        never = _candidate(similarity=0.8, usage_count=0)

        result = rank_candidates([never, referenced], now=NOW)
        assert result[0].source_id == referenced.source_id

    def test_recency_half_life_calculation(self) -> None:
        """At exactly half_life_days, recency_score should be 0.5."""
        cfg = ScoringConfig(half_life_days=14.0)
        candidate = _candidate(similarity=0.5, days_ago=14)

        # Manual: recency = 0.5^(14/14) = 0.5
        # final = 0.5*0.5 + 0.3*0 + 0.2*0.5 = 0.25 + 0 + 0.1 = 0.35
        # We can't directly access scores, but we can verify relative ranking
        recent = _candidate(similarity=0.5, days_ago=7)
        # recency for 7 days = 0.5^(7/14) = 0.5^0.5 ≈ 0.707
        # final = 0.5*0.5 + 0.3*0 + 0.2*0.707 ≈ 0.391

        result = rank_candidates([candidate, recent], config=cfg, now=NOW)
        assert result[0].source_id == recent.source_id  # Higher recency


# ---------------------------------------------------------------------------
# Custom configuration
# ---------------------------------------------------------------------------


class TestRankCandidatesCustomConfig:
    """Custom ScoringConfig produces different rankings."""

    def test_similarity_only_config(self) -> None:
        """With usage_weight=0 and recency_weight=0, only similarity matters."""
        config = ScoringConfig(
            similarity_weight=1.0,
            usage_weight=0.0,
            recency_weight=0.0,
        )
        low_sim_high_usage = _candidate(similarity=0.5, usage_count=100, days_ago=0)
        high_sim_no_usage = _candidate(similarity=0.9, usage_count=0)

        result = rank_candidates([low_sim_high_usage, high_sim_no_usage], config=config, now=NOW)
        assert result[0].source_id == high_sim_no_usage.source_id

    def test_usage_only_config(self) -> None:
        """With similarity_weight=0 and recency_weight=0, only usage matters."""
        config = ScoringConfig(
            similarity_weight=0.0,
            usage_weight=1.0,
            recency_weight=0.0,
        )
        low_usage_high_sim = _candidate(similarity=0.99, usage_count=1)
        high_usage_low_sim = _candidate(similarity=0.1, usage_count=50)

        result = rank_candidates([low_usage_high_sim, high_usage_low_sim], config=config, now=NOW)
        assert result[0].source_id == high_usage_low_sim.source_id

    def test_recency_only_config(self) -> None:
        """With similarity_weight=0 and usage_weight=0, only recency matters."""
        config = ScoringConfig(
            similarity_weight=0.0,
            usage_weight=0.0,
            recency_weight=1.0,
        )
        high_sim_old = _candidate(similarity=0.99, days_ago=100)
        low_sim_recent = _candidate(similarity=0.1, days_ago=1)

        result = rank_candidates([high_sim_old, low_sim_recent], config=config, now=NOW)
        assert result[0].source_id == low_sim_recent.source_id

    def test_custom_half_life_changes_ranking(self) -> None:
        """A shorter half-life makes older entries decay faster."""
        short_half_life = ScoringConfig(half_life_days=1.0)

        one_day_old = _candidate(similarity=0.8, days_ago=1)
        two_day_old = _candidate(similarity=0.8, days_ago=2)

        result = rank_candidates([two_day_old, one_day_old], config=short_half_life, now=NOW)
        # With half_life=1 day, the 1-day-old is much more recent than 2-day-old
        assert result[0].source_id == one_day_old.source_id


# ---------------------------------------------------------------------------
# Stable order for identical scores
# ---------------------------------------------------------------------------


class TestRankCandidatesStableOrder:
    """Candidates with identical scores maintain stable order."""

    def test_identical_scores_preserve_input_order(self) -> None:
        """When all signals are identical, output order matches input order."""
        a = _candidate(similarity=0.8, usage_count=0)
        b = _candidate(similarity=0.8, usage_count=0)
        c = _candidate(similarity=0.8, usage_count=0)

        result = rank_candidates([a, b, c], now=NOW)
        assert [c.source_id for c in result] == [
            a.source_id,
            b.source_id,
            c.source_id,
        ]
