"""Jump-detection tests for voice_drift_scoring (signal iii, ADR-073 D2).

Split from ``test_voice_drift_scoring.py`` to keep both files under the RULE-04
400-line hard limit. This file covers signal (iii) — adjacent-chapter metric
jump detection via :func:`detect_adjacent_jumps`.

Signal (i) — profile-trend — lives in ``test_voice_drift_scoring.py``; value
types + reuse contract + band mapping live in
``test_voice_drift_scoring_types.py`` (mirrors the voice_check_scoring split
layout: ``test_voice_check_scoring.py`` + ``test_voice_check_scoring_props.py``).

Deterministic + pure (ADR-021). No LLM, no I/O.
"""

from __future__ import annotations

import pytest

from narrare_core.analysis.voice_drift_scoring import (
    DEFAULT_JUMP_THRESHOLD,
    PerChapterMetrics,
    detect_adjacent_jumps,
)
from narrare_core.kb.schemas.character import VoiceMetrics


def _vm(**kwargs: object) -> VoiceMetrics:
    """Build a VoiceMetrics with only the given fields (others default to None)."""
    return VoiceMetrics(**kwargs)  # type: ignore[arg-type]


def _pcm(
    chapter_id: str,
    character_id: str = "Elena",
    metrics: VoiceMetrics | None = None,
    utterance_count: int = 5,
) -> PerChapterMetrics:
    """Build a PerChapterMetrics with sensible defaults."""
    return PerChapterMetrics(
        chapter_id=chapter_id,
        character_id=character_id,
        metrics=metrics if metrics is not None else VoiceMetrics(),
        utterance_count=utterance_count,
    )


class TestDetectAdjacentJumps:
    """Adjacent-chapter delta + jump flagging.

    Reuses voice_metric_distances on consecutive chapters (ADR-073 D2 / D3 —
    one primitive, two consumers). A jump is recorded when a specific metric's
    [0,1] distance between two consecutive chapters exceeds the threshold.
    """

    def test_no_jumps_when_metrics_identical(self) -> None:
        chapters = [
            _pcm("ch-001", metrics=_vm(avg_sentence_length=10.0)),
            _pcm("ch-002", metrics=_vm(avg_sentence_length=10.0)),
            _pcm("ch-003", metrics=_vm(avg_sentence_length=10.0)),
        ]
        jumps = detect_adjacent_jumps(chapters)
        assert jumps == []

    def test_jump_detected_when_metric_shifts(self) -> None:
        """avg_sentence_length jumps from 10 to 30 between ch-001 and ch-002."""
        chapters = [
            _pcm("ch-001", metrics=_vm(avg_sentence_length=10.0)),
            _pcm("ch-002", metrics=_vm(avg_sentence_length=30.0)),
        ]
        jumps = detect_adjacent_jumps(chapters, jump_threshold=0.3)
        assert len(jumps) == 1
        jp = jumps[0]
        assert jp.from_chapter_id == "ch-001"
        assert jp.to_chapter_id == "ch-002"
        assert "avg_sentence_length" in jp.jumped_metrics

    def test_multiple_metrics_jumped(self) -> None:
        """When two metrics both shift beyond threshold, both are listed."""
        chapters = [
            _pcm(
                "ch-001",
                metrics=_vm(avg_sentence_length=10.0, type_token_ratio=0.7),
            ),
            _pcm(
                "ch-002",
                metrics=_vm(avg_sentence_length=40.0, type_token_ratio=0.3),
            ),
        ]
        jumps = detect_adjacent_jumps(chapters, jump_threshold=0.3)
        assert len(jumps) == 1
        jp = jumps[0]
        assert set(jp.jumped_metrics) == {"avg_sentence_length", "type_token_ratio"}

    def test_jump_threshold_filters_small_shifts(self) -> None:
        """A small shift below threshold does NOT produce a jump."""
        chapters = [
            _pcm("ch-001", metrics=_vm(avg_sentence_length=10.0)),
            # 10 vs 11 → d = 1/21 ≈ 0.048 < default threshold 0.3 → no jump.
            _pcm("ch-002", metrics=_vm(avg_sentence_length=11.0)),
        ]
        jumps = detect_adjacent_jumps(chapters, jump_threshold=0.3)
        assert jumps == []

    def test_jump_threshold_is_configurable(self) -> None:
        """Lowering the threshold catches smaller shifts.

        With profile metric 10.0 → 11.0 the distance is ``1/21 ≈ 0.0476``:
        - default threshold 0.3 → no jump (0.0476 < 0.3).
        - threshold 0.04 → jump detected (0.0476 > 0.04).
        """
        chapters = [
            _pcm("ch-001", metrics=_vm(avg_sentence_length=10.0)),
            _pcm("ch-002", metrics=_vm(avg_sentence_length=11.0)),
        ]
        # Default threshold does not flag this small shift.
        assert detect_adjacent_jumps(chapters) == []
        # Lowering the threshold to 0.04 catches it.
        jumps = detect_adjacent_jumps(chapters, jump_threshold=0.04)
        assert len(jumps) == 1
        assert "avg_sentence_length" in jumps[0].jumped_metrics

    def test_default_threshold_is_documented_constant(self) -> None:
        """The default jump_threshold is exposed on the module so callers +
        tests can reference it (RULE-18 — eval-tunable)."""
        assert DEFAULT_JUMP_THRESHOLD > 0.0
        assert DEFAULT_JUMP_THRESHOLD < 1.0

    def test_magnitude_is_normalized_in_zero_to_one(self) -> None:
        """JumpPoint.magnitude is the mean of the jumped metrics' [0,1] distances."""
        chapters = [
            _pcm(
                "ch-001",
                metrics=_vm(avg_sentence_length=10.0, type_token_ratio=0.7),
            ),
            _pcm(
                "ch-002",
                metrics=_vm(avg_sentence_length=30.0, type_token_ratio=0.3),
            ),
        ]
        jumps = detect_adjacent_jumps(chapters, jump_threshold=0.3)
        assert len(jumps) == 1
        m = jumps[0].magnitude
        assert 0.0 <= m <= 1.0
        # Two metrics jumped: avg_sentence_length (d=0.5), type_token_ratio
        # (d ≈ 0.4/1.0 = 0.4) → mean ≈ 0.45.
        assert m == pytest.approx(0.45, abs=0.01)

    def test_jumps_for_three_chapters_two_pairs(self) -> None:
        """Three consecutive chapters → up to two jump points."""
        chapters = [
            _pcm("ch-001", metrics=_vm(avg_sentence_length=10.0)),
            _pcm("ch-002", metrics=_vm(avg_sentence_length=40.0)),  # jump
            _pcm("ch-003", metrics=_vm(avg_sentence_length=12.0)),  # jump back
        ]
        jumps = detect_adjacent_jumps(chapters, jump_threshold=0.3)
        assert len(jumps) == 2
        assert jumps[0].from_chapter_id == "ch-001"
        assert jumps[0].to_chapter_id == "ch-002"
        assert jumps[1].from_chapter_id == "ch-002"
        assert jumps[1].to_chapter_id == "ch-003"

    def test_empty_chapter_list_yields_no_jumps(self) -> None:
        assert detect_adjacent_jumps([]) == []

    def test_single_chapter_yields_no_jumps(self) -> None:
        """A single chapter has no adjacent pair → no jumps."""
        chapters = [_pcm("ch-001", metrics=_vm(avg_sentence_length=10.0))]
        assert detect_adjacent_jumps(chapters) == []

    def test_missing_metric_on_one_side_not_jumped(self) -> None:
        """RULE-11: a metric present on one chapter but None on the other is
        not comparable → not flagged as a jump (no false positive)."""
        chapters = [
            _pcm("ch-001", metrics=_vm(avg_sentence_length=10.0)),
            # avg_sentence_length is None on ch-002 → skipped, no jump.
            _pcm("ch-002", metrics=_vm(type_token_ratio=0.9)),
        ]
        jumps = detect_adjacent_jumps(chapters, jump_threshold=0.3)
        assert jumps == []
