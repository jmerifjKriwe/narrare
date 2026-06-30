"""Tests for voice_check_scoring — pure hybrid voice-check scorer (WRITE-010/ADR-057).

Covers (ADR-057 Decision 2):
- band_for_score: threshold boundaries (green >=90, yellow 70-89, fair 50-69, red <50).
- voice_metric_distances: per-metric normalized [0,1] distance (scalar + dict);
  None on either side -> metric skipped (RULE-11).
- metric_delta_subscore: aggregate 0-100 (100 == identical); None when nothing
  comparable.
- blend_scores: deterministic weighted blend; graceful weight collapse.
- VoiceCheckScorer: RULE-18 weights (class defaults + constructor injection),
  weight-sum validation, no-profile signal, missing-current graceful.

Deterministic + pure (ADR-021). No LLM, no I/O (RULE-01b).
"""

from __future__ import annotations

import pytest

from narrare_core.analysis.voice_check_scoring import (
    VoiceCheckBand,
    VoiceCheckScorer,
    band_for_score,
    blend_scores,
    metric_delta_subscore,
    voice_metric_distances,
)
from narrare_core.kb.schemas.character import VoiceMetrics

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _vm(**kwargs: object) -> VoiceMetrics:
    """Build a VoiceMetrics with only the given fields (others default to None)."""
    return VoiceMetrics(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# A. band_for_score — threshold boundaries
# ---------------------------------------------------------------------------


class TestBandForScore:
    """green >=90; 70<=yellow<90; 50<=fair<70; red<50."""

    @pytest.mark.parametrize(
        ("score", "expected"),
        [
            (100.0, VoiceCheckBand.GREEN),
            (90.0, VoiceCheckBand.GREEN),
            (90.001, VoiceCheckBand.GREEN),
            (89.999, VoiceCheckBand.YELLOW),
            (70.0, VoiceCheckBand.YELLOW),
            (69.999, VoiceCheckBand.FAIR),
            (50.0, VoiceCheckBand.FAIR),
            (49.999, VoiceCheckBand.RED),
            (0.0, VoiceCheckBand.RED),
        ],
    )
    def test_boundary_mapping(self, score: float, expected: VoiceCheckBand) -> None:
        assert band_for_score(score) is expected

    def test_band_is_ordered_monotonically(self) -> None:
        """Higher score never yields a lower-severity band."""
        bands = [band_for_score(s) for s in (0.0, 49.9, 50.0, 69.9, 70.0, 89.9, 90.0, 100.0)]
        assert bands == [
            VoiceCheckBand.RED,
            VoiceCheckBand.RED,
            VoiceCheckBand.FAIR,
            VoiceCheckBand.FAIR,
            VoiceCheckBand.YELLOW,
            VoiceCheckBand.YELLOW,
            VoiceCheckBand.GREEN,
            VoiceCheckBand.GREEN,
        ]


# ---------------------------------------------------------------------------
# B. voice_metric_distances — per-metric normalization
# ---------------------------------------------------------------------------


class TestScalarDistances:
    """Scalar metrics: avg_sentence_length, sentence_length_std, type_token_ratio,
    avg_syllables_per_word, contraction_rate."""

    def test_identical_metrics_all_zero(self) -> None:
        stored = _vm(avg_sentence_length=12.0, type_token_ratio=0.7)
        current = _vm(avg_sentence_length=12.0, type_token_ratio=0.7)
        dist = voice_metric_distances(stored, current)
        assert set(dist.values()) == {0.0}

    def test_none_on_either_side_skipped(self) -> None:
        # stored has the metric, current does not -> absent from distances.
        stored = _vm(avg_sentence_length=12.0)
        current = _vm()  # avg_sentence_length is None
        assert voice_metric_distances(stored, current) == {}

    def test_none_on_stored_side_skipped(self) -> None:
        stored = _vm()  # None
        current = _vm(avg_sentence_length=12.0)
        assert voice_metric_distances(stored, current) == {}

    def test_relative_distance_value(self) -> None:
        # symmetric bounded relative difference: |a-b|/(|a|+|b|).
        # 10 vs 20 -> 10/30 = 0.333...
        stored = _vm(avg_sentence_length=10.0)
        current = _vm(avg_sentence_length=20.0)
        dist = voice_metric_distances(stored, current)
        assert dist["avg_sentence_length"] == pytest.approx(1.0 / 3.0)

    def test_distance_is_symmetric(self) -> None:
        stored = _vm(contraction_rate=0.1)
        current = _vm(contraction_rate=0.4)
        d1 = voice_metric_distances(stored, current)["contraction_rate"]
        d2 = voice_metric_distances(current, stored)["contraction_rate"]
        assert d1 == d2

    def test_distance_bounded_zero_to_one(self) -> None:
        # one side 0 -> distance 1.0 (max).
        stored = _vm(type_token_ratio=0.0)
        current = _vm(type_token_ratio=0.9)
        assert voice_metric_distances(stored, current)["type_token_ratio"] == pytest.approx(1.0)

    def test_both_zero_is_zero(self) -> None:
        # 0 vs 0 -> identical -> 0 (not 0/0).
        stored = _vm(contraction_rate=0.0)
        current = _vm(contraction_rate=0.0)
        assert voice_metric_distances(stored, current)["contraction_rate"] == 0.0

    def test_all_five_scalars_present(self) -> None:
        stored = _vm(
            avg_sentence_length=10.0,
            sentence_length_std=2.0,
            type_token_ratio=0.5,
            avg_syllables_per_word=1.4,
            contraction_rate=0.1,
        )
        current = _vm(
            avg_sentence_length=12.0,
            sentence_length_std=2.0,
            type_token_ratio=0.5,
            avg_syllables_per_word=1.4,
            contraction_rate=0.1,
        )
        dist = voice_metric_distances(stored, current)
        # All five keys present; only avg_sentence_length differs.
        assert set(dist) == {
            "avg_sentence_length",
            "sentence_length_std",
            "type_token_ratio",
            "avg_syllables_per_word",
            "contraction_rate",
        }
        assert dist["avg_sentence_length"] > 0.0
        assert dist["sentence_length_std"] == 0.0


class TestDictDistances:
    """Dict metrics: verbal_tic_frequency, punctuation_profile."""

    def test_both_none_skipped(self) -> None:
        stored = _vm()
        current = _vm()
        dist = voice_metric_distances(stored, current)
        assert "verbal_tic_frequency" not in dist
        assert "punctuation_profile" not in dist

    def test_one_none_skipped(self) -> None:
        stored = _vm(punctuation_profile={"exclamation": 0.1})
        current = _vm()  # None
        assert voice_metric_distances(stored, current) == {}

    def test_identical_dicts_zero(self) -> None:
        stored = _vm(punctuation_profile={"exclamation": 0.1, "question": 0.05})
        current = _vm(punctuation_profile={"exclamation": 0.1, "question": 0.05})
        assert voice_metric_distances(stored, current)["punctuation_profile"] == 0.0

    def test_key_only_in_one_side_max(self) -> None:
        # union = {exclamation, question}; question only in stored -> 1.0,
        # exclamation shared identical -> 0.0; mean = 0.5.
        stored = _vm(punctuation_profile={"exclamation": 0.1, "question": 0.05})
        current = _vm(punctuation_profile={"exclamation": 0.1})
        d = voice_metric_distances(stored, current)["punctuation_profile"]
        assert d == pytest.approx(0.5)

    def test_shared_key_value_diff(self) -> None:
        # exclamation 0.1 vs 0.3 -> 0.2/0.4 = 0.5; mean over 1 key = 0.5.
        stored = _vm(punctuation_profile={"exclamation": 0.1})
        current = _vm(punctuation_profile={"exclamation": 0.3})
        d = voice_metric_distances(stored, current)["punctuation_profile"]
        assert d == pytest.approx(0.5)

    def test_empty_dicts_identical(self) -> None:
        stored = _vm(punctuation_profile={})
        current = _vm(punctuation_profile={})
        assert voice_metric_distances(stored, current)["punctuation_profile"] == 0.0

    def test_disjoint_keys_max_distance(self) -> None:
        stored = _vm(punctuation_profile={"exclamation": 0.1})
        current = _vm(punctuation_profile={"question": 0.1})
        # union = 2 keys, each only in one side -> 1.0 each -> mean 1.0.
        d = voice_metric_distances(stored, current)["punctuation_profile"]
        assert d == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# C. metric_delta_subscore — aggregate 0-100
# ---------------------------------------------------------------------------


class TestMetricDeltaSubscore:
    def test_identical_is_hundred(self) -> None:
        stored = _vm(avg_sentence_length=12.0, type_token_ratio=0.7)
        current = _vm(avg_sentence_length=12.0, type_token_ratio=0.7)
        assert metric_delta_subscore(stored, current) == pytest.approx(100.0)

    def test_nothing_comparable_is_none(self) -> None:
        stored = _vm(avg_sentence_length=12.0)
        current = _vm()  # nothing on the current side
        assert metric_delta_subscore(stored, current) is None

    def test_subscore_in_range(self) -> None:
        stored = _vm(avg_sentence_length=10.0)
        current = _vm(avg_sentence_length=20.0)  # distance ~0.333 -> ~66.67
        sub = metric_delta_subscore(stored, current)
        assert sub is not None
        assert 0.0 <= sub <= 100.0
        assert sub == pytest.approx((1.0 - 1.0 / 3.0) * 100.0)

    def test_maximally_different_is_zero(self) -> None:
        stored = _vm(type_token_ratio=0.0)
        current = _vm(type_token_ratio=0.9)  # distance 1.0
        assert metric_delta_subscore(stored, current) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# D. blend_scores — deterministic weighted blend
# ---------------------------------------------------------------------------


class TestBlendScores:
    def test_weighted_average(self) -> None:
        result = blend_scores(80.0, 60.0, metric_weight=0.5, qualitative_weight=0.5)
        assert result == pytest.approx(70.0)

    def test_default_weights_six_four(self) -> None:
        result = blend_scores(100.0, 50.0, metric_weight=0.6, qualitative_weight=0.4)
        assert result == pytest.approx(80.0)

    def test_deterministic(self) -> None:
        kwargs = {
            "metric_subscore": 77.0,
            "qualitative_subscore": 63.0,
            "metric_weight": 0.6,
            "qualitative_weight": 0.4,
        }
        assert blend_scores(**kwargs) == blend_scores(**kwargs)

    def test_metric_none_collapses_to_qualitative(self) -> None:
        result = blend_scores(None, 70.0, metric_weight=0.6, qualitative_weight=0.4)
        assert result == pytest.approx(70.0)

    def test_qualitative_none_collapses_to_metric(self) -> None:
        result = blend_scores(70.0, None, metric_weight=0.6, qualitative_weight=0.4)
        assert result == pytest.approx(70.0)

    def test_both_none_is_none(self) -> None:
        assert blend_scores(None, None, metric_weight=0.6, qualitative_weight=0.4) is None


# ---------------------------------------------------------------------------
# E. VoiceCheckScorer — RULE-18 weights + orchestration + graceful
# ---------------------------------------------------------------------------


class TestScorerWeights:
    def test_defaults_sum_to_one(self) -> None:
        scorer = VoiceCheckScorer()
        total = scorer.DEFAULT_METRIC_WEIGHT + scorer.DEFAULT_QUALITATIVE_WEIGHT
        assert total == pytest.approx(1.0)

    def test_custom_weights_accepted(self) -> None:
        scorer = VoiceCheckScorer(metric_weight=0.7, qualitative_weight=0.3)
        # Identical metrics + qualitative 100 -> 100 regardless of weights.
        result = scorer.score(
            _vm(avg_sentence_length=10.0),
            _vm(avg_sentence_length=10.0),
            qualitative_subscore=100.0,
        )
        assert result.match_score == pytest.approx(100.0)

    def test_invalid_weight_sum_raises(self) -> None:
        with pytest.raises(ValueError):
            VoiceCheckScorer(metric_weight=0.6, qualitative_weight=0.5)


class TestScorerOrchestration:
    def test_no_stored_profile_signals_no_profile(self) -> None:
        scorer = VoiceCheckScorer()
        result = scorer.score(None, _vm(avg_sentence_length=10.0), qualitative_subscore=80.0)
        assert result.has_profile is False
        assert result.match_score is None
        assert result.band is None
        assert result.metric_delta_subscore is None

    def test_identical_metrics_and_qual_green(self) -> None:
        scorer = VoiceCheckScorer()
        stored = _vm(avg_sentence_length=10.0, type_token_ratio=0.6)
        current = _vm(avg_sentence_length=10.0, type_token_ratio=0.6)
        result = scorer.score(stored, current, qualitative_subscore=100.0)
        assert result.has_profile is True
        assert result.match_score == pytest.approx(100.0)
        assert result.band is VoiceCheckBand.GREEN

    def test_missing_current_graceful_uses_qualitative(self) -> None:
        # Stored profile exists, current has no comparable metrics (all None).
        # Metric sub-score collapses; overall == qualitative.
        scorer = VoiceCheckScorer()
        result = scorer.score(
            _vm(avg_sentence_length=10.0),
            _vm(),  # nothing comparable on current side
            qualitative_subscore=75.0,
        )
        assert result.has_profile is True
        assert result.metric_delta_subscore is None
        assert result.match_score == pytest.approx(75.0)
        assert result.band is VoiceCheckBand.YELLOW

    def test_both_subscores_absent_signals_unscorable(self) -> None:
        # Profile exists but neither metric nor qualitative signal -> no score.
        scorer = VoiceCheckScorer()
        result = scorer.score(
            _vm(avg_sentence_length=10.0),
            _vm(),
            qualitative_subscore=None,
        )
        assert result.has_profile is True
        assert result.match_score is None
        assert result.band is None

    def test_score_clamped_to_hundred(self) -> None:
        scorer = VoiceCheckScorer()
        result = scorer.score(
            _vm(avg_sentence_length=10.0),
            _vm(avg_sentence_length=10.0),
            qualitative_subscore=150.0,  # out of range -> clamped
        )
        assert result.match_score == pytest.approx(100.0)

    def test_metric_delta_subscore_surfaced_on_result(self) -> None:
        scorer = VoiceCheckScorer()
        result = scorer.score(
            _vm(avg_sentence_length=10.0),
            _vm(avg_sentence_length=10.0),
            qualitative_subscore=90.0,
        )
        assert result.metric_delta_subscore == pytest.approx(100.0)
        assert result.n_comparable_metrics == 1

    def test_current_none_treated_as_empty(self) -> None:
        # current=None (no dialogue analysed) -> graceful, metric collapses.
        scorer = VoiceCheckScorer()
        result = scorer.score(
            _vm(avg_sentence_length=10.0),
            None,
            qualitative_subscore=80.0,
        )
        assert result.has_profile is True
        assert result.metric_delta_subscore is None
        assert result.match_score == pytest.approx(80.0)

    def test_determinism_same_inputs_same_output(self) -> None:
        scorer = VoiceCheckScorer()
        stored = _vm(avg_sentence_length=10.0, type_token_ratio=0.5)
        current = _vm(avg_sentence_length=14.0, type_token_ratio=0.5)
        r1 = scorer.score(stored, current, qualitative_subscore=72.0)
        r2 = scorer.score(stored, current, qualitative_subscore=72.0)
        assert r1 == r2  # ADR-021 determinism


# Property-based (hypothesis) tests live in test_voice_check_scoring_props.py
# (RULE-04 split — kept separate from the example-based suite).
