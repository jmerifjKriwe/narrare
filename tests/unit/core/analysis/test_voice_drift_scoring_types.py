"""Value-type + reuse-contract tests for voice_drift_scoring (ANAL-009 / ADR-073 D2).

Split from ``test_voice_drift_scoring.py`` to keep both files under the RULE-04
400-line hard limit (mirrors the voice_check_scoring test layout:
``test_voice_check_scoring.py`` + ``test_voice_check_scoring_props.py``).

This file covers:
- The three value types (PerChapterMetrics / TrendPoint / JumpPoint) — Pydantic
  field shape.
- The ADR-057 Risk #3 reuse contract — voice_drift_scoring MUST import + reuse
  ``voice_metric_distances`` + ``band_for_score`` (zero duplication).
- The band↔label mapping (ADR-073 D4) covers all four VoiceCheckBand values.

Deterministic + pure (ADR-021). No LLM, no I/O.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from narrare_core.analysis.voice_check_scoring import VoiceCheckBand
from narrare_core.analysis.voice_drift_scoring import (
    _VOICE_CHECK_BAND_TO_DRIFT_LABEL,
    JumpPoint,
    PerChapterMetrics,
    TrendPoint,
)
from narrare_core.kb.schemas.character import VoiceMetrics


def _vm(**kwargs: object) -> VoiceMetrics:
    """Build a VoiceMetrics with only the given fields (others default to None)."""
    return VoiceMetrics(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Value types — Pydantic field shape
# ---------------------------------------------------------------------------


class TestPerChapterMetricsModel:
    """PerChapterMetrics is a Pydantic value type carrying the right fields."""

    def test_constructs_with_required_fields(self) -> None:
        pcm = PerChapterMetrics(
            chapter_id="ch-001",
            character_id="Elena",
            metrics=_vm(avg_sentence_length=10.0),
            utterance_count=4,
        )
        assert pcm.chapter_id == "ch-001"
        assert pcm.character_id == "Elena"
        assert pcm.metrics.avg_sentence_length == 10.0
        assert pcm.utterance_count == 4

    def test_is_frozen(self) -> None:
        """PerChapterMetrics is immutable (frozen=True) — value-object semantics."""
        pcm = PerChapterMetrics(
            chapter_id="ch-001",
            character_id="Elena",
            metrics=_vm(),
            utterance_count=1,
        )
        with pytest.raises(ValidationError):
            pcm.chapter_id = "ch-002"  # type: ignore[misc]

    def test_utterance_count_zero_is_valid(self) -> None:
        """utterance_count=0 is permitted by the Field (≥0).

        (In practice :func:`compute_per_chapter_metrics` OMITS chapters where the
        character speaks 0 utterances, so a 0 count only arises from direct
        construction — but the type itself permits it for forward-compat.)
        """
        pcm = PerChapterMetrics(
            chapter_id="ch-001",
            character_id="Elena",
            metrics=_vm(),
            utterance_count=0,
        )
        assert pcm.utterance_count == 0


class TestTrendPointModel:
    """TrendPoint is one row of signal (i) — the per-chapter trend."""

    def test_constructs_with_required_fields(self) -> None:
        tp = TrendPoint(
            chapter_id="ch-003",
            match_subscore=72.5,
            per_metric_deltas={"avg_sentence_length": 0.18},
            band="minor",
        )
        assert tp.chapter_id == "ch-003"
        assert tp.match_subscore == 72.5
        assert tp.per_metric_deltas["avg_sentence_length"] == 0.18
        assert tp.band == "minor"

    def test_match_subscore_bounds_enforced(self) -> None:
        """match_subscore is bounded to [0.0, 100.0] by the Pydantic Field."""
        with pytest.raises(ValidationError):
            TrendPoint(chapter_id="ch-001", match_subscore=-0.1, band="major")
        with pytest.raises(ValidationError):
            TrendPoint(chapter_id="ch-001", match_subscore=100.1, band="stable")

    def test_is_frozen(self) -> None:
        tp = TrendPoint(chapter_id="ch-001", match_subscore=50.0, band="moderate")
        with pytest.raises(ValidationError):
            tp.match_subscore = 60.0  # type: ignore[misc]


class TestJumpPointModel:
    """JumpPoint is one row of signal (iii) — an adjacent-chapter jump."""

    def test_constructs_with_required_fields(self) -> None:
        jp = JumpPoint(
            from_chapter_id="ch-003",
            to_chapter_id="ch-004",
            jumped_metrics=["avg_sentence_length", "type_token_ratio"],
            magnitude=0.42,
        )
        assert jp.from_chapter_id == "ch-003"
        assert jp.to_chapter_id == "ch-004"
        assert "avg_sentence_length" in jp.jumped_metrics
        assert jp.magnitude == pytest.approx(0.42)

    def test_jumped_metrics_min_length_one(self) -> None:
        """A JumpPoint always has ≥ 1 jumped metric (empty jumps are never emitted)."""
        with pytest.raises(ValidationError):
            JumpPoint(
                from_chapter_id="ch-001",
                to_chapter_id="ch-002",
                jumped_metrics=[],
                magnitude=0.0,
            )

    def test_magnitude_bounds_enforced(self) -> None:
        """magnitude is bounded to [0.0, 1.0] by the Pydantic Field."""
        with pytest.raises(ValidationError):
            JumpPoint(
                from_chapter_id="ch-001",
                to_chapter_id="ch-002",
                jumped_metrics=["x"],
                magnitude=-0.1,
            )
        with pytest.raises(ValidationError):
            JumpPoint(
                from_chapter_id="ch-001",
                to_chapter_id="ch-002",
                jumped_metrics=["x"],
                magnitude=1.1,
            )

    def test_is_frozen(self) -> None:
        jp = JumpPoint(
            from_chapter_id="ch-001",
            to_chapter_id="ch-002",
            jumped_metrics=["x"],
            magnitude=0.5,
        )
        with pytest.raises(ValidationError):
            jp.magnitude = 0.9  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Band↔label mapping (ADR-073 D4)
# ---------------------------------------------------------------------------


class TestBandLabelMapping:
    """ADR-073 D4 — the VoiceCheckBand→drift-label mapping is total + correct."""

    def test_mapping_covers_all_voice_check_bands(self) -> None:
        """Every VoiceCheckBand value maps to a drift label (no missing keys)."""
        assert set(_VOICE_CHECK_BAND_TO_DRIFT_LABEL.keys()) == set(VoiceCheckBand)

    def test_mapping_values_are_the_four_drift_labels(self) -> None:
        """The drift labels are exactly stable | minor | moderate | major."""
        assert set(_VOICE_CHECK_BAND_TO_DRIFT_LABEL.values()) == {
            "stable",
            "minor",
            "moderate",
            "major",
        }

    def test_green_maps_to_stable(self) -> None:
        assert _VOICE_CHECK_BAND_TO_DRIFT_LABEL[VoiceCheckBand.GREEN] == "stable"

    def test_yellow_maps_to_minor(self) -> None:
        assert _VOICE_CHECK_BAND_TO_DRIFT_LABEL[VoiceCheckBand.YELLOW] == "minor"

    def test_fair_maps_to_moderate(self) -> None:
        assert _VOICE_CHECK_BAND_TO_DRIFT_LABEL[VoiceCheckBand.FAIR] == "moderate"

    def test_red_maps_to_major(self) -> None:
        assert _VOICE_CHECK_BAND_TO_DRIFT_LABEL[VoiceCheckBand.RED] == "major"


# ---------------------------------------------------------------------------
# Reuse contract — ADR-057 Risk #3 no-duplication guarantee
# ---------------------------------------------------------------------------


class TestReuseContract:
    """ADR-057 Risk #3 / ADR-073 D2 — voice_drift_scoring MUST import and
    reuse voice_metric_distances + band_for_score from voice_check_scoring
    (zero duplication). A guard against future drift back to duplication."""

    def test_imports_voice_metric_distances_from_voice_check_scoring(
        self,
    ) -> None:
        """The module MUST reuse voice_metric_distances — not re-implement it."""
        import narrare_core.analysis.voice_drift_scoring as vds

        assert hasattr(vds, "voice_metric_distances")
        # The imported object is the same as the one in voice_check_scoring.
        from narrare_core.analysis.voice_check_scoring import (
            voice_metric_distances as canonical,
        )

        assert vds.voice_metric_distances is canonical

    def test_imports_band_for_score_from_voice_check_scoring(self) -> None:
        """The module MUST reuse band_for_score — not re-implement it."""
        import narrare_core.analysis.voice_drift_scoring as vds

        assert hasattr(vds, "band_for_score")
        from narrare_core.analysis.voice_check_scoring import (
            band_for_score as canonical,
        )

        assert vds.band_for_score is canonical

    def test_does_not_define_private_distance_helpers(self) -> None:
        """No private _scalar_distance / _dict_distance defined locally — those
        primitives live in voice_check_scoring only (the duplication guard)."""
        import narrare_core.analysis.voice_drift_scoring as vds

        assert not hasattr(vds, "_scalar_distance")
        assert not hasattr(vds, "_dict_distance")
