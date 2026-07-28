"""voice_drift_scoring — pure longitudinal drift primitives (ANAL-009 / ADR-073 D2).

The longitudinal layer of character-voice drift detection. Built **on top of**
the WRITE-010 delta primitive — it imports and reuses
:func:`narrare_core.analysis.voice_check_scoring.voice_metric_distances` and
:func:`narrare_core.analysis.voice_check_scoring.band_for_score` verbatim
(ADR-057 Risk #3 / ADR-073 Decision 2 — **zero duplication**).

Two complementary signals are computed here:

- **Signal (i) — profile-trend** (:func:`trend_against_profile`): for each
  chapter where the character speaks, the per-chapter metrics are compared
  against the stored profile's metrics via the reused delta primitive,
  producing a per-chapter match sub-score (0-100) + a severity band. The
  per-chapter trend is the always-visible sparkline / heatmap row.
- **Signal (iii) — adjacent-chapter jumps** (:func:`detect_adjacent_jumps`):
  the same delta primitive applied to chapter N vs chapter N+1. A jump point
  is recorded when a specific metric's normalized distance exceeds a
  threshold; the point is labelled with which metric(s) jumped + a normalized
  magnitude. Jump points localise *where* drift began.

:func:`compute_per_chapter_metrics` is the per-chapter measurement entry
point — it runs the deterministic
:class:`~narrare_core.analysis.dialogue_parser.DialogueParser` +
:class:`~narrare_core.analysis.voice_metrics.VoiceMetricsAnalyzer` once per
chapter, scoped to a single character.

The module is **pure** — no I/O, no LLM, no state — and **deterministic**
(ADR-021): identical inputs always yield identical output. Fully unit-testable
without an LLM.

RULE-11 graceful behaviour (ADR-073 Decision 5):
- A chapter where the character speaks 0 attributed utterances is OMITTED
  from :func:`compute_per_chapter_metrics`'s result (no artificial zeros in
  the trend — the trend is defined over the chapters where the character
  speaks).
- A metric that is ``None`` on either side is skipped in the delta (mirrors
  ``voice_metric_distances``) — never a crash.

Band↔label mapping (ADR-073 Decision 4): the
:class:`~narrare_core.analysis.voice_check_scoring.VoiceCheckBand` enum
(green / yellow / fair / red) maps to the drift-facing labels
(stable / minor / moderate / major). The band thresholds themselves are
identical to WRITE-010's because they come from the same
:func:`band_for_score` — the ADR-057 Risk #3 no-duplication guarantee.

See Also
--------
ADR-073 — Character Voice Drift (Decision 2 comparison model, Decision 4
visualization band mapping, Decision 5 graceful behaviour).
ADR-057 — Voice-check checking-path contract (the delta primitive reused here).
ADR-021 — Deterministic analysis strategy.
"""

from __future__ import annotations

from itertools import pairwise
from typing import TYPE_CHECKING

from narrare_core.analysis.voice_check_scoring import (
    VoiceCheckBand,
    band_for_score,
    voice_metric_distances,
)

# Value types live in their own module so this scoring module stays under the
# RULE-04 400-line hard limit (modularise, not minify). Re-exported below via
# ``__all__`` so existing ``from voice_drift_scoring import PerChapterMetrics``
# imports (analysis/__init__.py, the drift agent, tests) keep working.
from narrare_core.analysis.voice_drift_scoring_types import (
    JumpPoint,
    PerChapterMetrics,
    TrendPoint,
)

# Runtime import (not TYPE_CHECKING): VoiceMetrics is used at runtime by
# trend_against_profile's signature + the band mapping docstring cross-ref.
# noqa: TC001.
from narrare_core.kb.schemas.character import VoiceMetrics  # noqa: TC001

if TYPE_CHECKING:
    from collections.abc import Mapping

    from narrare_core.analysis.dialogue_parser import DialogueParser
    from narrare_core.analysis.voice_metrics import VoiceMetricsAnalyzer

# ---------------------------------------------------------------------------
# Band↔label mapping (ADR-073 Decision 4)
# ---------------------------------------------------------------------------
#
# ADR-073 D4's band↔colour↔label table maps the WRITE-010 VoiceCheckBand
# (green / yellow / fair / red) to the drift-facing labels
# (stable / minor / moderate / major). Keeping the mapping in one place here
# means the labels the agent + the UI see are derived from the canonical
# band_for_score thresholds — change the threshold in voice_check_scoring and
# both WRITE-010 and ANAL-009 see the new boundary identically (no second
# tuning surface — ADR-057 Risk #2 / ADR-073 D2).

_VOICE_CHECK_BAND_TO_DRIFT_LABEL: dict[VoiceCheckBand, str] = {
    VoiceCheckBand.GREEN: "stable",
    VoiceCheckBand.YELLOW: "minor",
    VoiceCheckBand.FAIR: "moderate",
    VoiceCheckBand.RED: "major",
}

# ---------------------------------------------------------------------------
# Jump detection default (RULE-18)
# ---------------------------------------------------------------------------
#
# Default jump_threshold for :func:`detect_adjacent_jumps`. A metric is flagged
# as "jumped" between two adjacent chapters when its [0,1] normalized distance
# exceeds this value. 0.3 corresponds to the lower edge of the "fair"/
# "moderate" band (a chapter whose overall match score would land in 50-69):
# shifts that large between adjacent chapters are unlikely to be noise and
# worth flagging as candidate drift anchors. Class-level annotated constant +
# constructor-style parameter — the canonical RULE-18 pattern (cf.
# ``DialogueParser.DEFAULT_CONTEXT_WINDOW``, ``VoiceCheckScorer`` weights).
# Eval-tunable via ADR-032.
DEFAULT_JUMP_THRESHOLD: float = 0.3


# Value types (PerChapterMetrics / TrendPoint / JumpPoint) live in
# ``voice_drift_scoring_types.py`` (RULE-04 modularisation). They are imported
# above and re-exported via ``__all__`` so existing callers are unaffected.


# ---------------------------------------------------------------------------
# Signal (i) — per-chapter measurement + profile-trend
# ---------------------------------------------------------------------------


def compute_per_chapter_metrics(
    chapter_texts: Mapping[str, str],
    character_id: str,
    *,
    parser: DialogueParser,
    analyzer: VoiceMetricsAnalyzer,
) -> list[PerChapterMetrics]:
    """Compute per-chapter VoiceMetrics for one character across chapters.

    For each chapter: parses attributed dialogue, filters to utterances whose
    speaker matches *character_id*, runs the deterministic
    :class:`VoiceMetricsAnalyzer` over them, and emits a
    :class:`PerChapterMetrics` row. Chapters where the character speaks 0
    attributed utterances are **omitted** from the result (RULE-11 graceful
    behaviour — ADR-073 Decision 5: no artificial zeros in the trend).

    Deterministic (ADR-021): identical inputs always yield identical output.

    Args:
        chapter_texts: Mapping from chapter_id to raw chapter text. Iteration
            order is preserved in the result (Python 3.7+ dicts are
            insertion-ordered).
        character_id: The character whose metrics to compute (matched against
            ``AttributedUtterance.speaker`` — case-sensitive, exact match
            mirroring :meth:`VoiceMetricsAnalyzer.analyze` grouping).
        parser: A :class:`DialogueParser` instance (caller-owned; configurable
            per RULE-18).
        analyzer: A :class:`VoiceMetricsAnalyzer` instance (caller-owned;
            configurable per RULE-18).

    Returns:
        Ordered list of :class:`PerChapterMetrics`. One row per chapter where
        the character has ≥ 1 attributed utterance. Empty when no chapter has
        attributable dialogue for this character.
    """
    results: list[PerChapterMetrics] = []
    for chapter_id, text in chapter_texts.items():
        utterances = parser.parse(text)
        # Keep only utterances whose speaker matches the requested character
        # (VoiceMetricsAnalyzer.analyze groups by speaker; we pre-filter so a
        # chapter where the character does NOT speak yields no row, mirroring
        # the analyzer's own None-speaker skip).
        character_utterances = [u for u in utterances if u.speaker == character_id]
        if not character_utterances:
            # RULE-11 graceful — omit the chapter (no artificial zeros).
            continue
        # Run the analyzer on just this character's utterances. We pass a
        # single-speaker list so the returned dict has exactly one entry.
        metrics_by_speaker = analyzer.analyze(character_utterances)
        metrics = metrics_by_speaker.get(character_id)
        if metrics is None:
            # Defensive: analyzer returned no entry (e.g. all empty text).
            continue
        results.append(
            PerChapterMetrics(
                chapter_id=chapter_id,
                character_id=character_id,
                metrics=metrics,
                utterance_count=len(character_utterances),
            )
        )
    return results


def trend_against_profile(
    per_chapter: list[PerChapterMetrics],
    profile_metrics: VoiceMetrics,
) -> list[TrendPoint]:
    """Compute the per-chapter match trend against the stored profile.

    For each supplied :class:`PerChapterMetrics`, computes the [0,1] distance
    per comparable metric via :func:`voice_metric_distances` (reused from
    WRITE-010 — ADR-057 Risk #3 / ADR-073 D2), aggregates to a match sub-score
    in [0, 100] (100 = identical to profile that chapter), and bands it via
    :func:`band_for_score` (same thresholds as WRITE-010).

    RULE-11 graceful: a metric that is ``None`` on either side is skipped in
    the delta (mirrors ``voice_metric_distances``). When NO metric is
    comparable on either side the trend point carries ``match_subscore=0.0``,
    an empty ``per_metric_deltas`` dict, and band ``"major"`` — the caller
    (drift agent) treats such a point as 'unscorable' but keeps it in the
    trend so the longitudinal shape is preserved.

    Deterministic (ADR-021): identical inputs always yield identical output.

    Args:
        per_chapter: The per-chapter metrics for one character (from
            :func:`compute_per_chapter_metrics`).
        profile_metrics: The stored profile's metrics (from
            :attr:`CharacterVoiceProfile.voice_metrics` — ADR-057).

    Returns:
        Ordered list of :class:`TrendPoint`, one per supplied
        :class:`PerChapterMetrics`. Empty when *per_chapter* is empty.
    """
    trend: list[TrendPoint] = []
    for pcm in per_chapter:
        distances = voice_metric_distances(profile_metrics, pcm.metrics)
        subscore = subscore_from_distances(distances)
        trend.append(
            TrendPoint(
                chapter_id=pcm.chapter_id,
                match_subscore=subscore,
                per_metric_deltas=dict(distances),
                band=drift_band_for_subscore(subscore),
            )
        )
    return trend


# ---------------------------------------------------------------------------
# Shared trend/jump builders (ADR-073 D2 — one aggregation, two consumers)
# ---------------------------------------------------------------------------
#
# Extracted so ANAL-009 Phase 2B author drift
# (:mod:`narrare_core.analysis.author_voice_drift_scoring`) reuses the SAME
# subscore / band / jump aggregation as character drift — only the distance
# *source* differs (voice deltas vs merged voice+author deltas). This is the
# ADR-057 Risk #3 / ADR-073 D2 no-duplication guarantee applied to the
# orchestration layer (the delta normalization itself is shared via
# ``voice_metric_distances`` / ``author_metric_distances``).


def subscore_from_distances(distances: Mapping[str, float]) -> float:
    """[0, 100] match sub-score from a per-metric [0, 1] distance dict.

    The mean-distance rule shared by character + author drift:
    ``(1 - mean(distances)) * 100`` (100 = identical). An empty distance dict
    (no metric comparable on both sides) yields ``0.0`` — RULE-11 graceful
    (the trend shape is preserved, the point flagged 'unscorable' via band
    'major').

    Clamped to ``[0.0, 100.0]`` defensively (the mean of [0, 1] values cannot
    escape, but the clamp keeps the :class:`TrendPoint` Field invariant honest
    under float rounding at the boundaries).

    Args:
        distances: Per-metric normalized ``[0, 1]`` distances (from
            :func:`voice_metric_distances` and/or
            :func:`author_metric_distances`).

    Returns:
        Match sub-score in ``[0.0, 100.0]``.
    """
    if distances:
        mean_distance = sum(distances.values()) / len(distances)
        subscore = (1.0 - mean_distance) * 100.0
    else:
        subscore = 0.0
    return max(0.0, min(100.0, subscore))


def drift_band_for_subscore(subscore: float) -> str:
    """Drift-facing band label (``stable|minor|moderate|major``) for a sub-score.

    Wraps :func:`band_for_score` (the WRITE-010 thresholds) via
    :data:`_VOICE_CHECK_BAND_TO_DRIFT_LABEL` so character + author drift share
    IDENTICAL band boundaries with WRITE-010 (ADR-073 Decision 4).
    """
    return _VOICE_CHECK_BAND_TO_DRIFT_LABEL[band_for_score(subscore)]


def jumped_metrics_from_distances(
    distances: Mapping[str, float],
    *,
    jump_threshold: float,
) -> tuple[list[str], float] | None:
    """Metrics that jumped between two points + their mean magnitude.

    Returns ``(sorted jumped metric names, mean [0, 1] magnitude)`` when at
    least one metric's distance exceeds *jump_threshold*; ``None`` otherwise
    (no jump — the caller emits no :class:`JumpPoint`). Shared by character +
    author adjacent-chapter jump detection (ADR-073 D2 — one jump builder).

    Args:
        distances: Per-metric normalized ``[0, 1]`` distances between the two
            chapters.
        jump_threshold: A metric is flagged as "jumped" when its distance
            exceeds this value (RULE-18 eval-tunable via ADR-032).

    Returns:
        ``(jumped_metrics, magnitude)`` or ``None`` when nothing jumped.
    """
    jumped = sorted(name for name, d in distances.items() if d > jump_threshold)
    if not jumped:
        return None
    magnitude = sum(distances[name] for name in jumped) / len(jumped)
    # Defensive clamp — distances are each in [0, 1] so the mean is too, but
    # the clamp keeps the JumpPoint Field invariant honest at the boundaries.
    return jumped, max(0.0, min(1.0, magnitude))


# ---------------------------------------------------------------------------
# Signal (iii) — adjacent-chapter jump detection
# ---------------------------------------------------------------------------


def detect_adjacent_jumps(
    per_chapter: list[PerChapterMetrics],
    *,
    jump_threshold: float = DEFAULT_JUMP_THRESHOLD,
) -> list[JumpPoint]:
    """Detect adjacent-chapter metric jumps (signal iii).

    For each consecutive pair of chapters, computes the per-metric [0,1]
    distance via :func:`voice_metric_distances` (the same primitive
    :func:`trend_against_profile` uses — ADR-073 D2: one primitive, two
    consumers) and records a :class:`JumpPoint` when at least one metric's
    distance exceeds *jump_threshold*.

    RULE-11 graceful: a metric that is ``None`` on either side is skipped
    (never falsely flagged as a jump).

    Deterministic (ADR-021): identical inputs always yield identical output.

    Args:
        per_chapter: The per-chapter metrics for one character (from
            :func:`compute_per_chapter_metrics`). Order is significant —
            jumps are computed between consecutive list entries.
        jump_threshold: A metric is flagged as "jumped" when its [0,1]
            distance between two adjacent chapters exceeds this value.
            Defaults to :data:`DEFAULT_JUMP_THRESHOLD` (0.3 — the lower edge
            of the "moderate" band; RULE-18 eval-tunable via ADR-032).

    Returns:
        Ordered list of :class:`JumpPoint`, one per adjacent pair with at
        least one jumped metric. Empty when *per_chapter* has < 2 entries or
        no metric shifted beyond the threshold.
    """
    if len(per_chapter) < 2:
        return []
    jumps: list[JumpPoint] = []
    # itertools.pairwise yields (prev, curr) tuples for each consecutive pair
    # — the canonical Python 3.10+ idiom (ruff RUF007).
    for prev, curr in pairwise(per_chapter):
        distances = voice_metric_distances(prev.metrics, curr.metrics)
        result = jumped_metrics_from_distances(distances, jump_threshold=jump_threshold)
        if result is None:
            continue
        jumped, magnitude = result
        jumps.append(
            JumpPoint(
                from_chapter_id=prev.chapter_id,
                to_chapter_id=curr.chapter_id,
                jumped_metrics=jumped,
                magnitude=magnitude,
            )
        )
    return jumps


__all__ = [
    "DEFAULT_JUMP_THRESHOLD",
    "JumpPoint",
    "PerChapterMetrics",
    "TrendPoint",
    "band_for_score",
    "compute_per_chapter_metrics",
    "detect_adjacent_jumps",
    "drift_band_for_subscore",
    "jumped_metrics_from_distances",
    "subscore_from_distances",
    "trend_against_profile",
    "voice_metric_distances",
]
