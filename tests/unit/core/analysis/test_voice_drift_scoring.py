"""Tests for voice_drift_scoring — compute_per_chapter_metrics + signal (i) trend.

Covers ADR-073 Decision 2's longitudinal layer built on top of the WRITE-010
delta primitive (ADR-057 Risk #3 — zero duplication contract):

- ``compute_per_chapter_metrics``: per (character, chapter) deterministic
  VoiceMetrics extraction. Chapters where the character does NOT speak are
  OMITTED from the result (RULE-11 graceful — no artificial zeros).
- ``trend_against_profile``: per-chapter match sub-score + band against the
  stored profile's metrics (signal i). Reuses
  :func:`narrare_core.analysis.voice_check_scoring.voice_metric_distances` +
  :func:`narrare_core.analysis.voice_check_scoring.band_for_score` — the
  ADR-057 / ADR-073 Risk #3 no-duplication guarantee.

Signal (iii) — adjacent-chapter jump detection — lives in
``test_voice_drift_scoring_jumps.py``; value types + reuse contract + band
mapping live in ``test_voice_drift_scoring_types.py`` (RULE-04 split, mirrors
the voice_check_scoring layout: ``test_voice_check_scoring.py`` +
``test_voice_check_scoring_props.py``).

Deterministic + pure (ADR-021). No LLM, no I/O.
"""

from __future__ import annotations

import pytest

from narrare_core.analysis.dialogue_parser import DialogueParser
from narrare_core.analysis.voice_drift_scoring import (
    PerChapterMetrics,
    compute_per_chapter_metrics,
    trend_against_profile,
)
from narrare_core.analysis.voice_metrics import VoiceMetricsAnalyzer
from narrare_core.kb.schemas.character import VoiceMetrics

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# A. compute_per_chapter_metrics
# ---------------------------------------------------------------------------


class TestComputePerChapterMetrics:
    """Per (character, chapter) VoiceMetrics extraction.

    RULE-11 graceful: a chapter where the character speaks 0 attributed
    utterances is OMITTED from the result (no artificial zeros — ADR-073 D5).
    """

    def test_one_chapter_one_speaker(self) -> None:
        chapters = {
            "ch-001": '"Hello there," said Elena.',
        }
        parser = DialogueParser()
        analyzer = VoiceMetricsAnalyzer()
        result = compute_per_chapter_metrics(
            chapters, character_id="Elena", parser=parser, analyzer=analyzer
        )
        assert len(result) == 1
        assert result[0].chapter_id == "ch-001"
        assert result[0].character_id == "Elena"
        assert result[0].utterance_count >= 1
        assert isinstance(result[0].metrics, VoiceMetrics)

    def test_multiple_chapters_preserve_order(self) -> None:
        chapters = {
            "ch-001": '"Hi," said Elena.',
            "ch-002": '"Bye," said Elena.',
            "ch-003": '"Later," said Elena.',
        }
        parser = DialogueParser()
        analyzer = VoiceMetricsAnalyzer()
        result = compute_per_chapter_metrics(
            chapters, character_id="Elena", parser=parser, analyzer=analyzer
        )
        assert [pcm.chapter_id for pcm in result] == ["ch-001", "ch-002", "ch-003"]

    def test_chapter_where_character_does_not_speak_is_omitted(
        self,
    ) -> None:
        """RULE-11: silent-in-chapter → that chapter is OMITTED (no zeros)."""
        chapters = {
            "ch-001": '"Hello," said Elena.',
            # ch-002: Marc speaks, Elena doesn't.
            "ch-002": '"Hi," said Marc.',
            "ch-003": '"Back," said Elena.',
        }
        parser = DialogueParser()
        analyzer = VoiceMetricsAnalyzer()
        result = compute_per_chapter_metrics(
            chapters, character_id="Elena", parser=parser, analyzer=analyzer
        )
        chapter_ids = [pcm.chapter_id for pcm in result]
        assert chapter_ids == ["ch-001", "ch-003"]

    def test_empty_chapter_text_is_omitted(self) -> None:
        chapters = {"ch-001": "", "ch-002": '"Hi," said Elena.'}
        parser = DialogueParser()
        analyzer = VoiceMetricsAnalyzer()
        result = compute_per_chapter_metrics(
            chapters, character_id="Elena", parser=parser, analyzer=analyzer
        )
        assert len(result) == 1
        assert result[0].chapter_id == "ch-002"

    def test_chapter_with_unattributed_dialogue_only_is_omitted(self) -> None:
        """Quotes without a deterministic speaker attribution (speaker=None)
        are skipped by VoiceMetricsAnalyzer — so the chapter yields no
        metrics for the requested character_id."""
        chapters = {
            # No speech-verb tag, no action beat, no em-dash → speaker=None.
            "ch-001": '"Hello there."',
        }
        parser = DialogueParser()
        analyzer = VoiceMetricsAnalyzer()
        result = compute_per_chapter_metrics(
            chapters, character_id="Elena", parser=parser, analyzer=analyzer
        )
        assert result == []

    def test_empty_chapter_dict_yields_empty_list(self) -> None:
        parser = DialogueParser()
        analyzer = VoiceMetricsAnalyzer()
        result = compute_per_chapter_metrics(
            {}, character_id="Elena", parser=parser, analyzer=analyzer
        )
        assert result == []

    def test_metrics_block_is_populated_for_real_dialogue(self) -> None:
        """For real attributed dialogue the metrics block is non-default."""
        chapters = {
            "ch-001": (
                '"I dare say, this is most irregular," Elena said. '
                '"Indeed it is," she replied. '
                '"We shall see."'
            ),
        }
        parser = DialogueParser()
        analyzer = VoiceMetricsAnalyzer()
        result = compute_per_chapter_metrics(
            chapters, character_id="Elena", parser=parser, analyzer=analyzer
        )
        assert len(result) == 1
        m = result[0].metrics
        # avg_sentence_length is a populated scalar (not None) when there is
        # real attributed dialogue.
        assert m.avg_sentence_length is not None
        assert m.avg_sentence_length > 0


# ---------------------------------------------------------------------------
# B. trend_against_profile (signal i)
# ---------------------------------------------------------------------------


class TestTrendAgainstProfile:
    """Per-chapter match sub-score + band against the stored profile's metrics.

    Reuses voice_metric_distances + band_for_score (ADR-057 Risk #3 —
    no duplication). Identical metrics → match_subscore 100.0 / band stable.
    """

    def test_identical_metrics_to_profile_yield_stable_band(self) -> None:
        profile = _vm(avg_sentence_length=10.0, type_token_ratio=0.7)
        chapters = [
            _pcm("ch-001", metrics=_vm(avg_sentence_length=10.0, type_token_ratio=0.7)),
            _pcm("ch-002", metrics=_vm(avg_sentence_length=10.0, type_token_ratio=0.7)),
        ]
        trend = trend_against_profile(chapters, profile)
        assert len(trend) == 2
        for tp in trend:
            assert tp.match_subscore == pytest.approx(100.0)
            assert tp.band == "stable"

    def test_drift_declines_subscore_and_worsens_band(self) -> None:
        """A chapter that diverges from the profile scores lower + worse band."""
        profile = _vm(avg_sentence_length=10.0)
        # ch-001 matches; ch-002 is wildly off (much longer sentences).
        chapters = [
            _pcm("ch-001", metrics=_vm(avg_sentence_length=10.0)),
            _pcm("ch-002", metrics=_vm(avg_sentence_length=50.0)),
        ]
        trend = trend_against_profile(chapters, profile)
        assert trend[0].match_subscore > trend[1].match_subscore
        # 10 vs 50 -> distance 40/60 ≈ 0.667 -> subscore 33.3 -> band "major".
        assert trend[1].band == "major"

    def test_band_thresholds_match_band_for_score(self) -> None:
        """The band string MUST come from voice_check_scoring.band_for_score
        so the band thresholds are identical across WRITE-010 and ANAL-009
        (ADR-073 D2 / D4 band↔colour↔label mapping).

        Per :func:`voice_metric_distances` semantics: ``d = |a-b|/(|a|+|b|)``;
        match score = ``(1 - d) * 100``. With profile ``avg_sentence_length=10``:
        - b=10   → d=0     → score 100 → GREEN/stable
        - b=12   → d=2/22  ≈ 0.091 → score ≈ 90.9 → GREEN/stable
        - b=14   → d=4/24  ≈ 0.167 → score ≈ 83.3 → YELLOW/minor
        - b=20   → d=10/30 ≈ 0.333 → score ≈ 66.7 → FAIR/moderate
        - b=60   → d=50/70 ≈ 0.714 → score ≈ 28.6 → RED/major
        """
        profile = _vm(avg_sentence_length=10.0)
        cases = [
            (10.0, "stable"),
            (12.0, "stable"),
            (14.0, "minor"),
            (20.0, "moderate"),
            (60.0, "major"),
        ]
        chapters = [
            _pcm(f"ch-{i:03d}", metrics=_vm(avg_sentence_length=asl))
            for i, (asl, _) in enumerate(cases)
        ]
        trend = trend_against_profile(chapters, profile)
        for tp, (asl, expected_band) in zip(trend, cases, strict=True):
            assert tp.band == expected_band, (
                f"asl={asl}, subscore={tp.match_subscore}, "
                f"expected band={expected_band}, got {tp.band}"
            )

    def test_per_metric_deltas_populated(self) -> None:
        """per_metric_deltas carries the [0,1] distance for each comparable metric."""
        profile = _vm(avg_sentence_length=10.0, type_token_ratio=0.7)
        chapters = [
            _pcm("ch-001", metrics=_vm(avg_sentence_length=12.0, type_token_ratio=0.7)),
        ]
        trend = trend_against_profile(chapters, profile)
        deltas = trend[0].per_metric_deltas
        assert "avg_sentence_length" in deltas
        assert "type_token_ratio" in deltas
        assert deltas["avg_sentence_length"] > 0.0
        assert deltas["type_token_ratio"] == pytest.approx(0.0)

    def test_missing_profile_metric_skipped_in_delta(self) -> None:
        """RULE-11 graceful: a metric that is None on the profile is skipped
        in the delta (mirrors voice_metric_distances). Never crashes."""
        profile = _vm(avg_sentence_length=10.0)  # type_token_ratio is None
        chapters = [
            _pcm(
                "ch-001",
                metrics=_vm(avg_sentence_length=12.0, type_token_ratio=0.9),
            ),
        ]
        trend = trend_against_profile(chapters, profile)
        deltas = trend[0].per_metric_deltas
        # type_token_ratio absent on profile → absent from deltas.
        assert "type_token_ratio" not in deltas
        assert "avg_sentence_length" in deltas

    def test_missing_chapter_metric_skipped_in_delta(self) -> None:
        """RULE-11 graceful: a metric None on the chapter side is also skipped."""
        profile = _vm(avg_sentence_length=10.0, type_token_ratio=0.7)
        chapters = [
            _pcm("ch-001", metrics=_vm(avg_sentence_length=12.0)),  # ttr None
        ]
        trend = trend_against_profile(chapters, profile)
        deltas = trend[0].per_metric_deltas
        assert "type_token_ratio" not in deltas
        assert "avg_sentence_length" in deltas

    def test_no_comparable_metrics_yields_zero_subscore(self) -> None:
        """If no metric is comparable on both sides (all None mismatches),
        the trend point carries match_subscore=0.0 + band 'major' and an empty
        delta dict — RULE-11 graceful (no crash). The caller (drift agent)
        treats such a point as 'unscorable' but still includes it in the trend
        so the longitudinal shape is preserved."""
        profile = _vm()  # all None
        chapters = [_pcm("ch-001", metrics=_vm())]
        trend = trend_against_profile(chapters, profile)
        assert len(trend) == 1
        assert trend[0].match_subscore == 0.0
        assert trend[0].per_metric_deltas == {}
        assert trend[0].band == "major"

    def test_empty_chapter_list_yields_empty_trend(self) -> None:
        profile = _vm(avg_sentence_length=10.0)
        assert trend_against_profile([], profile) == []

    def test_preserves_chapter_order(self) -> None:
        profile = _vm(avg_sentence_length=10.0)
        chapters = [
            _pcm("ch-001"),
            _pcm("ch-002"),
            _pcm("ch-003"),
        ]
        trend = trend_against_profile(chapters, profile)
        assert [tp.chapter_id for tp in trend] == ["ch-001", "ch-002", "ch-003"]

    def test_band_string_matches_voice_check_band_enum_values(self) -> None:
        """The TrendPoint.band string values are the lowercase names that
        ADR-073 D4 specifies (stable | minor | moderate | major), derived from
        VoiceCheckBand (green→stable, yellow→minor, fair→moderate, red→major)."""
        profile = _vm(avg_sentence_length=10.0)
        chapters = [_pcm("ch-001", metrics=_vm(avg_sentence_length=10.0))]
        trend = trend_against_profile(chapters, profile)
        # The full enum of allowed band strings:
        assert trend[0].band in {"stable", "minor", "moderate", "major"}
