"""Property-based tests for voice_check_scoring (WRITE-010/ADR-057 Decision 2).

Hypothesis-driven invariants over the scoring primitives (ADR-021 determinism +
bounded normalization). The example-based suite lives in
``test_voice_check_scoring.py``; this file is split out per RULE-04.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from narrare_core.analysis.voice_check_scoring import (
    VoiceCheckBand,
    band_for_score,
    blend_scores,
    metric_delta_subscore,
    voice_metric_distances,
)
from narrare_core.kb.schemas.character import VoiceMetrics


def _vm(**kwargs: object) -> VoiceMetrics:
    """Build a VoiceMetrics with only the given fields (others default to None)."""
    return VoiceMetrics(**kwargs)  # type: ignore[arg-type]


# Fixed blend weights (default VoiceCheckScorer weights) for reproducible props.
_METRIC_W = 0.6
_QUALITATIVE_W = 0.4


@given(
    a=st.floats(min_value=0.0, max_value=1e3, allow_nan=False, allow_infinity=False),
    b=st.floats(min_value=0.0, max_value=1e3, allow_nan=False, allow_infinity=False),
)
def test_scalar_distance_always_in_unit_interval(a: float, b: float) -> None:
    """Every scalar metric distance is bounded [0, 1] (triangle inequality)."""
    stored = _vm(type_token_ratio=a)
    current = _vm(type_token_ratio=b)
    dist = voice_metric_distances(stored, current)
    assert "type_token_ratio" in dist
    assert 0.0 <= dist["type_token_ratio"] <= 1.0


@given(
    a=st.floats(min_value=0.0, max_value=1e3, allow_nan=False, allow_infinity=False),
    b=st.floats(min_value=0.0, max_value=1e3, allow_nan=False, allow_infinity=False),
)
def test_scalar_distance_symmetric(a: float, b: float) -> None:
    """ADR-021: distance(stored, current) == distance(current, stored)."""
    stored = _vm(avg_sentence_length=a)
    current = _vm(avg_sentence_length=b)
    d_ab = voice_metric_distances(stored, current)["avg_sentence_length"]
    d_ba = voice_metric_distances(current, stored)["avg_sentence_length"]
    assert d_ab == d_ba


@given(
    metric=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    qual=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
)
def test_blend_in_range_and_reproducible(metric: float, qual: float) -> None:
    """Blend is in [0, 100] and deterministic (same inputs -> same output)."""
    r1 = blend_scores(metric, qual, metric_weight=_METRIC_W, qualitative_weight=_QUALITATIVE_W)
    r2 = blend_scores(metric, qual, metric_weight=_METRIC_W, qualitative_weight=_QUALITATIVE_W)
    assert r1 is not None
    assert r1 == r2
    assert 0.0 <= r1 <= 100.0


@given(score=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False))
def test_band_for_score_always_valid(score: float) -> None:
    """Every score in [0, 100] maps to a defined band."""
    assert band_for_score(score) in {
        VoiceCheckBand.GREEN,
        VoiceCheckBand.YELLOW,
        VoiceCheckBand.FAIR,
        VoiceCheckBand.RED,
    }


@given(
    a=st.floats(min_value=0.0, max_value=1e3, allow_nan=False, allow_infinity=False),
    b=st.floats(min_value=0.0, max_value=1e3, allow_nan=False, allow_infinity=False),
)
def test_metric_subscore_in_range_or_none(a: float, b: float) -> None:
    """Aggregate sub-score is in [0, 100] or None (nothing comparable)."""
    sub = metric_delta_subscore(_vm(avg_sentence_length=a), _vm(avg_sentence_length=b))
    assert sub is None or 0.0 <= sub <= 100.0


@given(
    a=st.floats(min_value=0.0, max_value=1e3, allow_nan=False, allow_infinity=False),
    b=st.floats(min_value=0.0, max_value=1e3, allow_nan=False, allow_infinity=False),
)
def test_metric_subscore_identical_is_hundred(a: float, b: float) -> None:
    """A metric compared with itself always yields sub-score 100 (identical)."""
    sub_a = metric_delta_subscore(_vm(avg_sentence_length=a), _vm(avg_sentence_length=a))
    sub_b = metric_delta_subscore(_vm(avg_sentence_length=b), _vm(avg_sentence_length=b))
    assert sub_a == 100.0
    assert sub_b == 100.0
