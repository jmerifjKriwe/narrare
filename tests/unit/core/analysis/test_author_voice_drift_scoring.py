"""Tests for author_voice_drift_scoring — narrator-voice longitudinal drift
(ANAL-009 Phase 2B / ADR-074).

The author-voice analogue of Phase 1's :mod:`voice_drift_scoring`. Where Phase
1 compares per-chapter :class:`VoiceMetrics` for ONE CHARACTER against the
stored :class:`CharacterVoiceProfile`, this module compares per-chapter
**narrator** metrics — BOTH :class:`VoiceMetrics` (via
:meth:`VoiceMetricsAnalyzer.analyze_text`) AND :class:`AuthorMetrics` (via
:class:`AuthorMetricsAnalyzer`) — against the stored
:class:`~narrare_core.profiles.author_voice.AuthorVoiceProfile`'s metric group.

ADR-057 Risk #3 / ADR-073 D2 no-duplication: reuses
:func:`voice_metric_distances` + :func:`author_metric_distances` (one delta
normalization) AND the shared trend/jump builders
(:func:`subscore_from_distances` / :func:`drift_band_for_subscore` /
:func:`jumped_metrics_from_distances`) extracted from Phase 1 — the author
module only supplies the distance *source*, never re-implements aggregation.

RULE-04: lives in its own module (``author_voice_drift_scoring`` + a
``_types`` sibling) mirroring the Phase 1 split —
``voice_drift_scoring.py`` was already 328 lines.

Deterministic + pure (ADR-021). No LLM, no I/O.
"""

from __future__ import annotations

import pytest

from narrare_core.analysis.author_metrics import AuthorMetrics, AuthorMetricsAnalyzer
from narrare_core.analysis.author_voice_drift_scoring import (
    PerAuthorChapterMetrics,
    compute_per_chapter_author_metrics,
    detect_adjacent_author_jumps,
    trend_against_author_profile,
)
from narrare_core.analysis.voice_metrics import VoiceMetricsAnalyzer
from narrare_core.kb.schemas.character import VoiceMetrics


def _vm(**kwargs: object) -> VoiceMetrics:
    return VoiceMetrics(**kwargs)  # type: ignore[arg-type]


def _am(**kwargs: object) -> AuthorMetrics:
    return AuthorMetrics(**kwargs)  # type: ignore[arg-type]


def _pacm(
    chapter_id: str,
    voice_metrics: VoiceMetrics | None = None,
    author_metrics: AuthorMetrics | None = None,
) -> PerAuthorChapterMetrics:
    return PerAuthorChapterMetrics(
        chapter_id=chapter_id,
        voice_metrics=voice_metrics if voice_metrics is not None else VoiceMetrics(),
        author_metrics=author_metrics if author_metrics is not None else AuthorMetrics(),
    )


# ---------------------------------------------------------------------------
# A. compute_per_chapter_author_metrics
# ---------------------------------------------------------------------------


class TestComputePerChapterAuthorMetrics:
    """Per-chapter narrator metrics (VoiceMetrics + AuthorMetrics).

    RULE-11 graceful: an empty/blank chapter is OMITTED (no artificial zeros),
    mirroring Phase 1 omitting chapters where the character is silent.
    """

    def test_one_chapter_yields_one_row(self) -> None:
        chapters = {
            "ch-001": (
                'The wind moved through the tall grass. "I will not go," Elena said quietly.'
            ),
        }
        result = compute_per_chapter_author_metrics(
            chapters,
            voice_analyzer=VoiceMetricsAnalyzer(),
            author_analyzer=AuthorMetricsAnalyzer(),
        )
        assert len(result) == 1
        assert result[0].chapter_id == "ch-001"
        assert isinstance(result[0].voice_metrics, VoiceMetrics)
        assert isinstance(result[0].author_metrics, AuthorMetrics)

    def test_order_preserved(self) -> None:
        chapters = {
            "ch-001": "The morning broke cold and clear.",
            "ch-002": "Rain came in the afternoon.",
            "ch-003": "By dusk the streets were empty.",
        }
        result = compute_per_chapter_author_metrics(
            chapters,
            voice_analyzer=VoiceMetricsAnalyzer(),
            author_analyzer=AuthorMetricsAnalyzer(),
        )
        assert [r.chapter_id for r in result] == ["ch-001", "ch-002", "ch-003"]

    def test_empty_chapter_omitted(self) -> None:
        """RULE-11: an empty/blank chapter yields no row (no artificial zeros)."""
        chapters = {"ch-001": "", "ch-002": "   ", "ch-003": "Real prose here."}
        result = compute_per_chapter_author_metrics(
            chapters,
            voice_analyzer=VoiceMetricsAnalyzer(),
            author_analyzer=AuthorMetricsAnalyzer(),
        )
        assert [r.chapter_id for r in result] == ["ch-003"]

    def test_empty_dict_yields_empty_list(self) -> None:
        result = compute_per_chapter_author_metrics(
            {},
            voice_analyzer=VoiceMetricsAnalyzer(),
            author_analyzer=AuthorMetricsAnalyzer(),
        )
        assert result == []

    def test_voice_metrics_populated_for_real_prose(self) -> None:
        chapters = {
            "ch-001": (
                "The old house stood at the edge of the cliff, its windows dark. "
                "She had not been there in years. The door groaned open."
            ),
        }
        result = compute_per_chapter_author_metrics(
            chapters,
            voice_analyzer=VoiceMetricsAnalyzer(),
            author_analyzer=AuthorMetricsAnalyzer(),
        )
        assert len(result) == 1
        # analyze_text populates avg_sentence_length for real prose.
        assert result[0].voice_metrics.avg_sentence_length is not None
        assert result[0].voice_metrics.avg_sentence_length > 0


# ---------------------------------------------------------------------------
# B. trend_against_author_profile (signal i — merged voice + author deltas)
# ---------------------------------------------------------------------------


class TestTrendAgainstAuthorProfile:
    """Per-chapter match sub-score + band over the MERGED voice + author deltas.

    Reuses subscore_from_distances + drift_band_for_subscore (ADR-073 D2 —
    one aggregation, two consumers). Identical metrics → 100.0 / stable.
    """

    def test_identical_metrics_to_profile_yield_stable(self) -> None:
        pv = _vm(avg_sentence_length=12.0, type_token_ratio=0.7)
        pa = _am(dialogue_ratio=0.4, metaphor_density=0.03)
        chapters = [
            _pacm(
                "ch-001",
                voice_metrics=_vm(avg_sentence_length=12.0, type_token_ratio=0.7),
                author_metrics=_am(dialogue_ratio=0.4, metaphor_density=0.03),
            ),
        ]
        trend = trend_against_author_profile(chapters, pv, pa)
        assert len(trend) == 1
        assert trend[0].match_subscore == pytest.approx(100.0)
        assert trend[0].band == "stable"

    def test_merged_deltas_carry_both_voice_and_author_metrics(self) -> None:
        """per_metric_deltas contains BOTH voice-metric AND author-metric keys."""
        pv = _vm(avg_sentence_length=12.0)
        pa = _am(dialogue_ratio=0.4)
        chapters = [
            _pacm(
                "ch-001",
                voice_metrics=_vm(avg_sentence_length=14.0),
                author_metrics=_am(dialogue_ratio=0.6),
            ),
        ]
        trend = trend_against_author_profile(chapters, pv, pa)
        deltas = trend[0].per_metric_deltas
        assert "avg_sentence_length" in deltas  # voice
        assert "dialogue_ratio" in deltas  # author
        assert deltas["avg_sentence_length"] > 0.0
        assert deltas["dialogue_ratio"] > 0.0

    def test_drift_worsens_band(self) -> None:
        """A chapter that diverges on author metrics scores lower + worse band.

        Profile has NO comparable voice metrics (all None) so the trend is
        driven purely by the author ``dialogue_ratio`` delta — isolating the
        author-drift signal. 0.1 vs 0.9 → d = 0.8/1.0 = 0.8 → subscore 20 →
        band 'major'.
        """
        pv = _vm()  # no comparable voice metrics
        pa = _am(dialogue_ratio=0.1)
        chapters = [
            _pacm(
                "ch-001",
                voice_metrics=_vm(avg_sentence_length=12.0),  # skipped (None profile)
                author_metrics=_am(dialogue_ratio=0.1),
            ),
            _pacm(
                "ch-002",
                voice_metrics=_vm(avg_sentence_length=12.0),
                author_metrics=_am(dialogue_ratio=0.9),  # big author drift
            ),
        ]
        trend = trend_against_author_profile(chapters, pv, pa)
        assert trend[0].match_subscore == pytest.approx(100.0)
        assert trend[0].band == "stable"
        assert trend[1].match_subscore < 50.0
        assert trend[1].band == "major"

    def test_missing_metric_on_either_side_skipped(self) -> None:
        """RULE-11: a metric None on either side is skipped (no crash)."""
        pv = _vm(avg_sentence_length=12.0)  # ttr None
        pa = _am(dialogue_ratio=0.4)  # others None
        chapters = [
            _pacm(
                "ch-001",
                voice_metrics=_vm(avg_sentence_length=14.0, type_token_ratio=0.9),
                author_metrics=_am(dialogue_ratio=0.4, metaphor_density=0.05),
            ),
        ]
        trend = trend_against_author_profile(chapters, pv, pa)
        deltas = trend[0].per_metric_deltas
        # type_token_ratio absent on profile → absent; metaphor_density absent
        # on profile → absent. Only the present-on-both metrics appear.
        assert "type_token_ratio" not in deltas
        assert "metaphor_density" not in deltas
        assert "avg_sentence_length" in deltas
        assert "dialogue_ratio" in deltas

    def test_no_comparable_metrics_yields_zero_subscore_major_band(self) -> None:
        """All-None profile + chapter → subscore 0.0, empty deltas, band 'major'."""
        chapters = [_pacm("ch-001")]
        trend = trend_against_author_profile(chapters, _vm(), _am())
        assert len(trend) == 1
        assert trend[0].match_subscore == 0.0
        assert trend[0].per_metric_deltas == {}
        assert trend[0].band == "major"

    def test_empty_chapter_list_yields_empty_trend(self) -> None:
        assert trend_against_author_profile([], _vm(), _am()) == []

    def test_preserves_chapter_order(self) -> None:
        chapters = [_pacm(f"ch-{i:03d}") for i in range(1, 4)]
        trend = trend_against_author_profile(chapters, _vm(), _am())
        assert [tp.chapter_id for tp in trend] == ["ch-001", "ch-002", "ch-003"]

    def test_band_values_are_drift_labels(self) -> None:
        chapters = [_pacm("ch-001", voice_metrics=_vm(avg_sentence_length=12.0))]
        trend = trend_against_author_profile(chapters, _vm(avg_sentence_length=12.0), _am())
        assert trend[0].band in {"stable", "minor", "moderate", "major"}


# ---------------------------------------------------------------------------
# C. detect_adjacent_author_jumps (signal iii)
# ---------------------------------------------------------------------------


class TestDetectAdjacentAuthorJumps:
    """Adjacent-chapter jumps over merged voice + author deltas.

    Reuses jumped_metrics_from_distances (one jump builder, two consumers).
    """

    def test_no_jumps_when_metrics_identical(self) -> None:
        chapters = [
            _pacm("ch-001", voice_metrics=_vm(avg_sentence_length=12.0)),
            _pacm("ch-002", voice_metrics=_vm(avg_sentence_length=12.0)),
        ]
        assert detect_adjacent_author_jumps(chapters) == []

    def test_jump_in_author_metric_detected(self) -> None:
        """dialogue_ratio jumps → jump point with the author metric listed."""
        chapters = [
            _pacm("ch-001", author_metrics=_am(dialogue_ratio=0.2)),
            _pacm("ch-002", author_metrics=_am(dialogue_ratio=0.9)),
        ]
        jumps = detect_adjacent_author_jumps(chapters, jump_threshold=0.3)
        assert len(jumps) == 1
        assert "dialogue_ratio" in jumps[0].jumped_metrics
        assert jumps[0].from_chapter_id == "ch-001"
        assert jumps[0].to_chapter_id == "ch-002"

    def test_jump_in_voice_metric_detected(self) -> None:
        """A voice-metric jump is detected too (merged deltas)."""
        chapters = [
            _pacm("ch-001", voice_metrics=_vm(avg_sentence_length=10.0)),
            _pacm("ch-002", voice_metrics=_vm(avg_sentence_length=40.0)),
        ]
        jumps = detect_adjacent_author_jumps(chapters, jump_threshold=0.3)
        assert len(jumps) == 1
        assert "avg_sentence_length" in jumps[0].jumped_metrics

    def test_jumped_metrics_can_mix_voice_and_author(self) -> None:
        """Both a voice and an author metric can jump in one pair."""
        chapters = [
            _pacm(
                "ch-001",
                voice_metrics=_vm(avg_sentence_length=10.0),
                author_metrics=_am(dialogue_ratio=0.2),
            ),
            _pacm(
                "ch-002",
                voice_metrics=_vm(avg_sentence_length=40.0),
                author_metrics=_am(dialogue_ratio=0.9),
            ),
        ]
        jumps = detect_adjacent_author_jumps(chapters, jump_threshold=0.3)
        assert len(jumps) == 1
        assert set(jumps[0].jumped_metrics) == {"avg_sentence_length", "dialogue_ratio"}

    def test_threshold_configurable(self) -> None:
        chapters = [
            _pacm("ch-001", author_metrics=_am(dialogue_ratio=0.40)),
            _pacm("ch-002", author_metrics=_am(dialogue_ratio=0.45)),
        ]
        # Small shift below default threshold.
        assert detect_adjacent_author_jumps(chapters) == []
        # Lowered threshold catches it.
        jumps = detect_adjacent_author_jumps(chapters, jump_threshold=0.05)
        assert len(jumps) == 1

    def test_magnitude_in_zero_to_one(self) -> None:
        chapters = [
            _pacm("ch-001", author_metrics=_am(dialogue_ratio=0.1)),
            _pacm("ch-002", author_metrics=_am(dialogue_ratio=0.9)),
        ]
        jumps = detect_adjacent_author_jumps(chapters, jump_threshold=0.3)
        assert len(jumps) == 1
        assert 0.0 <= jumps[0].magnitude <= 1.0

    def test_empty_and_single_chapter_yield_no_jumps(self) -> None:
        assert detect_adjacent_author_jumps([]) == []
        assert detect_adjacent_author_jumps([_pacm("ch-001")]) == []

    def test_missing_metric_on_one_side_not_jumped(self) -> None:
        """RULE-11: a metric None on one side is not comparable → not jumped."""
        chapters = [
            _pacm("ch-001", author_metrics=_am(dialogue_ratio=0.4)),
            # dialogue_ratio None on ch-002 → skipped, no jump.
            _pacm("ch-002", author_metrics=_am(description_density=0.5)),
        ]
        assert detect_adjacent_author_jumps(chapters, jump_threshold=0.3) == []


# ---------------------------------------------------------------------------
# D. PerAuthorChapterMetrics value type
# ---------------------------------------------------------------------------


class TestPerAuthorChapterMetrics:
    """The per-chapter narrator-metrics value object (frozen, both blocks)."""

    def test_construction(self) -> None:
        row = PerAuthorChapterMetrics(
            chapter_id="ch-1",
            voice_metrics=_vm(avg_sentence_length=10.0),
            author_metrics=_am(dialogue_ratio=0.4),
        )
        assert row.chapter_id == "ch-1"
        assert row.voice_metrics.avg_sentence_length == 10.0
        assert row.author_metrics.dialogue_ratio == 0.4

    def test_defaults(self) -> None:
        row = PerAuthorChapterMetrics(chapter_id="ch-2")
        assert isinstance(row.voice_metrics, VoiceMetrics)
        assert isinstance(row.author_metrics, AuthorMetrics)

    def test_frozen(self) -> None:
        from pydantic import ValidationError

        row = PerAuthorChapterMetrics(chapter_id="ch-1")
        with pytest.raises(ValidationError):
            row.chapter_id = "ch-9"  # type: ignore[misc]
