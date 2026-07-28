"""author_voice_drift_scoring — pure longitudinal narrator-voice drift primitives
(ANAL-009 Phase 2B / ADR-074).

The author-voice analogue of Phase 1's :mod:`voice_drift_scoring`. Where Phase
1 compares per-chapter :class:`~narrare_core.kb.schemas.character.VoiceMetrics`
for ONE CHARACTER against the stored
:class:`~narrare_core.profiles.models.CharacterVoiceProfile`, this module
compares per-chapter **narrator** metrics — BOTH
:class:`VoiceMetrics` (via
:meth:`~narrare_core.analysis.voice_metrics.VoiceMetricsAnalyzer.analyze_text`)
AND :class:`~narrare_core.analysis.author_metrics.AuthorMetrics` (via
:class:`~narrare_core.analysis.author_metrics.AuthorMetricsAnalyzer`) — against
the stored :class:`~narrare_core.profiles.author_voice.AuthorVoiceProfile`'s
metric group.

Two complementary signals, mirroring Phase 1:

- **Signal (i) — profile-trend** (:func:`trend_against_author_profile`): for
  each chapter, the merged per-metric distance (voice deltas + author deltas)
  is aggregated to a match sub-score (0-100) + severity band via the SHARED
  Phase 1 builders (:func:`subscore_from_distances` /
  :func:`drift_band_for_subscore`). Metric names do not collide (voice =
  avg_sentence_length / type_token_ratio / …; author = dialogue_ratio /
  description_density / action_introspection_ratio / metaphor_density), so the
  author deltas are MERGED into the same :class:`TrendPoint.per_metric_deltas`
  dict — the trend-point type is REUSED, not duplicated (the task's "reuse
  TrendPoint + add author-metric deltas" option).
- **Signal (iii) — adjacent-chapter jumps** (:func:`detect_adjacent_author_jumps`):
  the merged distance primitive applied to chapter N vs N+1 via the SHARED
  :func:`jumped_metrics_from_distances` builder.

:func:`compute_per_chapter_author_metrics` is the per-chapter measurement entry
point — it runs the deterministic analyzers once per chapter over the full
prose (narration + dialogue together).

ADR-057 Risk #3 / ADR-073 D2 no-duplication guarantee (binding): this module
reuses :func:`voice_metric_distances` + :func:`author_metric_distances` (one
delta normalization, two typed facades) AND the shared Phase 1 trend/jump
builders — it only supplies the distance *source* (merged voice + author
deltas), never re-implements aggregation.

The module is **pure** — no I/O, no LLM, no state — and **deterministic**
(ADR-021). RULE-11 graceful: an empty/blank chapter is OMITTED; a metric that
is ``None`` on either side is skipped (never a crash). No stored profile → the
caller (Layer 3 service) skips drift entirely (RULE-11).

RULE-04: this is a sibling module to ``voice_drift_scoring`` (which was already
328 lines) — the author concern is modularised, not crammed into Phase 1's
module.

See Also
--------
ADR-074 — Author Voice Storage Contract.
ADR-073 — Character Voice Drift (the Phase 1 parallel mirrored here).
ADR-021 — Deterministic analysis strategy.
narrare_core.analysis.voice_drift_scoring — Phase 1 (character) + shared builders.
narrare_core.analysis.voice_check_scoring — the shared delta normalization.
"""

from __future__ import annotations

from itertools import pairwise
from typing import TYPE_CHECKING

# Runtime imports (not TYPE_CHECKING): VoiceMetrics + AuthorMetrics are used in
# the trend/jump function signatures + the merge helper. noqa: TC001.
from narrare_core.analysis.author_metrics import AuthorMetrics  # noqa: TC001
from narrare_core.analysis.author_voice_drift_scoring_types import (
    PerAuthorChapterMetrics,
)
from narrare_core.analysis.voice_check_scoring import (
    author_metric_distances,
    voice_metric_distances,
)
from narrare_core.analysis.voice_drift_scoring import (
    DEFAULT_JUMP_THRESHOLD,
    drift_band_for_subscore,
    jumped_metrics_from_distances,
    subscore_from_distances,
)

# Value type lives in its own module (RULE-04 split — mirrors Phase 1's
# voice_drift_scoring_types). Re-exported via ``__all__`` so callers can import
# PerAuthorChapterMetrics from this module.
from narrare_core.analysis.voice_drift_scoring_types import JumpPoint, TrendPoint
from narrare_core.kb.schemas.character import VoiceMetrics  # noqa: TC001

if TYPE_CHECKING:
    from collections.abc import Mapping

    from narrare_core.analysis.author_metrics import AuthorMetricsAnalyzer
    from narrare_core.analysis.voice_metrics import VoiceMetricsAnalyzer


# ---------------------------------------------------------------------------
# Signal (i) — per-chapter measurement + profile-trend
# ---------------------------------------------------------------------------


def compute_per_chapter_author_metrics(
    chapter_texts: Mapping[str, str],
    *,
    voice_analyzer: VoiceMetricsAnalyzer,
    author_analyzer: AuthorMetricsAnalyzer,
) -> list[PerAuthorChapterMetrics]:
    """Compute per-chapter narrator metrics (VoiceMetrics + AuthorMetrics).

    For each chapter: runs the deterministic
    :meth:`VoiceMetricsAnalyzer.analyze_text` (voice-generic, over the full
    prose) and :meth:`AuthorMetricsAnalyzer.analyze` (author-specific prose-
    level) and emits a :class:`PerAuthorChapterMetrics` row. Empty/blank
    chapters are **omitted** from the result (RULE-11 graceful — no artificial
    zeros in the trend, mirroring Phase 1 omitting chapters where the character
    is silent).

    Deterministic (ADR-021): identical inputs always yield identical output.

    Args:
        chapter_texts: Mapping from chapter_id to raw chapter prose (narration
            + dialogue together). Iteration order is preserved in the result.
        voice_analyzer: A :class:`VoiceMetricsAnalyzer` instance (caller-owned;
            configurable per RULE-18). Used via ``analyze_text`` (prose-level).
        author_analyzer: A :class:`AuthorMetricsAnalyzer` instance (caller-
            owned; configurable per RULE-18).

    Returns:
        Ordered list of :class:`PerAuthorChapterMetrics`. One row per chapter
        with non-empty prose. Empty when no chapter has prose.
    """
    results: list[PerAuthorChapterMetrics] = []
    for chapter_id, text in chapter_texts.items():
        # RULE-11 graceful — omit empty/blank chapters (no artificial zeros).
        if not text or not text.strip():
            continue
        voice_metrics = voice_analyzer.analyze_text([text])
        author_metrics = author_analyzer.analyze([text])
        results.append(
            PerAuthorChapterMetrics(
                chapter_id=chapter_id,
                voice_metrics=voice_metrics,
                author_metrics=author_metrics,
            )
        )
    return results


def _merged_distances(
    voice_stored: VoiceMetrics,
    voice_current: VoiceMetrics,
    author_stored: AuthorMetrics,
    author_current: AuthorMetrics,
) -> dict[str, float]:
    """Merge voice + author per-metric [0, 1] distances into one dict.

    Metric names do not collide across the two blocks (voice metrics vs the
    four author-specific fields), so the merge is unambiguous. This is the ONLY
    author-specific logic — the aggregation is delegated to the shared Phase 1
    builders (ADR-073 D2 no-duplication).
    """
    distances = voice_metric_distances(voice_stored, voice_current)
    distances.update(author_metric_distances(author_stored, author_current))
    return distances


def trend_against_author_profile(
    per_chapter: list[PerAuthorChapterMetrics],
    profile_voice_metrics: VoiceMetrics,
    profile_author_metrics: AuthorMetrics,
) -> list[TrendPoint]:
    """Compute the per-chapter match trend against the stored author profile.

    For each supplied :class:`PerAuthorChapterMetrics`, computes the MERGED
    per-metric distance (voice deltas + author deltas via
    :func:`voice_metric_distances` + :func:`author_metric_distances`),
    aggregates to a match sub-score in [0, 100] via the SHARED
    :func:`subscore_from_distances`, and bands it via :func:`drift_band_for_subscore`
    (identical thresholds to Phase 1 + WRITE-010 — ADR-073 D4).

    RULE-11 graceful: a metric ``None`` on either side is skipped (by the delta
    primitives). When NO metric is comparable the trend point carries
    ``match_subscore=0.0``, an empty ``per_metric_deltas`` dict, and band
    ``"major"`` — the caller treats such a point as 'unscorable' but keeps it
    in the trend so the longitudinal shape is preserved.

    Author deltas are MERGED into :attr:`TrendPoint.per_metric_deltas` (the
    trend-point type is REUSED — metric names do not collide).

    Deterministic (ADR-021): identical inputs always yield identical output.

    Args:
        per_chapter: The per-chapter narrator metrics (from
            :func:`compute_per_chapter_author_metrics`).
        profile_voice_metrics: The stored profile's voice-generic metrics (from
            :attr:`AuthorVoiceProfile.voice_analysis.voice_metrics`).
        profile_author_metrics: The stored profile's author-specific metrics
            (from :attr:`AuthorVoiceProfile.author_metrics`).

    Returns:
        Ordered list of :class:`TrendPoint`, one per supplied
        :class:`PerAuthorChapterMetrics`. Empty when *per_chapter* is empty.
    """
    trend: list[TrendPoint] = []
    for pacm in per_chapter:
        distances = _merged_distances(
            profile_voice_metrics,
            pacm.voice_metrics,
            profile_author_metrics,
            pacm.author_metrics,
        )
        subscore = subscore_from_distances(distances)
        trend.append(
            TrendPoint(
                chapter_id=pacm.chapter_id,
                match_subscore=subscore,
                per_metric_deltas=distances,
                band=drift_band_for_subscore(subscore),
            )
        )
    return trend


# ---------------------------------------------------------------------------
# Signal (iii) — adjacent-chapter jump detection
# ---------------------------------------------------------------------------


def detect_adjacent_author_jumps(
    per_chapter: list[PerAuthorChapterMetrics],
    *,
    jump_threshold: float = DEFAULT_JUMP_THRESHOLD,
) -> list[JumpPoint]:
    """Detect adjacent-chapter metric jumps over merged voice + author deltas.

    For each consecutive pair of chapters, computes the MERGED per-metric
    distance (voice deltas + author deltas) and records a :class:`JumpPoint`
    when at least one metric's distance exceeds *jump_threshold* — via the
    SHARED :func:`jumped_metrics_from_distances` builder (ADR-073 D2 — one jump
    builder, two consumers).

    RULE-11 graceful: a metric ``None`` on either side is skipped (never
    falsely flagged as a jump).

    Deterministic (ADR-021): identical inputs always yield identical output.

    Args:
        per_chapter: The per-chapter narrator metrics (from
            :func:`compute_per_chapter_author_metrics`). Order is significant —
            jumps are computed between consecutive list entries.
        jump_threshold: A metric is flagged as "jumped" when its [0,1] distance
            between two adjacent chapters exceeds this value. Defaults to
            :data:`DEFAULT_JUMP_THRESHOLD` (0.3; RULE-18 eval-tunable).

    Returns:
        Ordered list of :class:`JumpPoint`, one per adjacent pair with at least
        one jumped metric. Empty when *per_chapter* has < 2 entries or no
        metric shifted beyond the threshold.
    """
    if len(per_chapter) < 2:
        return []
    jumps: list[JumpPoint] = []
    # itertools.pairwise yields (prev, curr) tuples for each consecutive pair
    # — the canonical Python 3.10+ idiom (ruff RUF007).
    for prev, curr in pairwise(per_chapter):
        distances = _merged_distances(
            prev.voice_metrics,
            curr.voice_metrics,
            prev.author_metrics,
            curr.author_metrics,
        )
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


# Late import (TYPE_CHECKING guard at module top): the analyzer classes are only
# needed for type hints on compute_per_chapter_author_metrics.


__all__ = [
    "PerAuthorChapterMetrics",
    "compute_per_chapter_author_metrics",
    "detect_adjacent_author_jumps",
    "trend_against_author_profile",
]
