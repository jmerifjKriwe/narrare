"""voice_check_scoring — pure hybrid voice-check scorer (WRITE-010/ADR-057 Decision 2).

Deterministic metric-delta + LLM qualitative blend for per-character voice
consistency checking. The module is **pure** — no I/O, no LLM, no state — and
**deterministic** (ADR-021): identical inputs always yield identical output. The
qualitative sub-score is supplied by the checker agent (Layer 2b); everything in
this file is fully unit-testable without an LLM.

Normalization
-------------
Scalars (avg_sentence_length, sentence_length_std, type_token_ratio,
avg_syllables_per_word, contraction_rate) use the symmetric bounded relative
difference::

    d(a, b) = |a - b| / (|a| + |b|)    for a != b, else 0.0

This is scale-invariant (so avg_sentence_length ~10 and contraction_rate ~0.1
become comparable), symmetric (ADR-021), and bounded [0, 1] by the triangle
inequality (|a - b| <= |a| + |b|). One side 0 -> 1.0; a == b -> 0.0; both 0 -> 0.0
(not 0/0).

Dict metrics (verbal_tic_frequency, punctuation_profile) take the union of keys:
shared keys use the scalar rule on their values; a key present on only one side is
a full mismatch (1.0); the dict distance is the mean over the union. Both empty
dicts are identical (0.0).

The aggregate metric-delta sub-score = (1 - mean_distance) * 100 (100 == identical);
``None`` when no metric is comparable on both sides (RULE-11 graceful).

The blend combines the metric-delta sub-score with an agent qualitative sub-score
(0-100). When either sub-score is ``None`` the blend collapses onto the available
signal. Weights are configurable per RULE-18 (class-level annotated defaults +
constructor injection, mirroring ``DialogueParser.DEFAULT_CONTEXT_WINDOW`` and
``VoiceMetricsAnalyzer`` defaults) and are eval-tunable (ADR-032 / ADR-057 Risk #2).

The per-metric distance + aggregate sub-score are exposed as module-level
primitives so ANAL-009 (voice drift) can reuse them (ADR-057 Review Trigger #2).

See Also
--------
ADR-057 — Voice-check checking-path contract (Decision 2 hybrid scoring).
ADR-021 — Deterministic analysis strategy.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar

from narrare_core.kb.schemas.character import VoiceMetrics

# Match-band thresholds (ADR-057 Decision 2: green >=90, yellow 70-89, fair 50-69,
# red <50). Three literals only -- RULE-18 safe at module level (cf.
# voice_metrics._PUNCTUATION_HABITS). Consumed by :func:`band_for_score`.
_GREEN_THRESHOLD: float = 90.0
_YELLOW_THRESHOLD: float = 70.0
_FAIR_THRESHOLD: float = 50.0


class VoiceCheckBand(StrEnum):
    """Per-character voice-match severity band (ADR-057 Decision 2)."""

    GREEN = "green"  # >= 90: strong match
    YELLOW = "yellow"  # 70-89: minor drift
    FAIR = "fair"  # 50-69: noticeable drift
    RED = "red"  # < 50: strong mismatch


def band_for_score(score: float) -> VoiceCheckBand:
    """Map a 0-100 match score to its severity band.

    green >= 90; 70 <= yellow < 90; 50 <= fair < 70; red < 50.

    Args:
        score: Match score in [0, 100].

    Returns:
        The severity band for *score*.
    """
    if score >= _GREEN_THRESHOLD:
        return VoiceCheckBand.GREEN
    if score >= _YELLOW_THRESHOLD:
        return VoiceCheckBand.YELLOW
    if score >= _FAIR_THRESHOLD:
        return VoiceCheckBand.FAIR
    return VoiceCheckBand.RED


# ---------------------------------------------------------------------------
# Per-metric distance primitives (reusable by ANAL-009 drift -- ADR-057 Risk #3)
# ---------------------------------------------------------------------------


def _scalar_distance(a: float, b: float) -> float:
    """Symmetric bounded relative difference in [0, 1].

    ``d = |a - b| / (|a| + |b|)``; ``0.0`` when ``a == b`` (incl. both ``0``).
    Bounded by the triangle inequality (``|a - b| <= |a| + |b|``).
    """
    if a == b:
        return 0.0
    return abs(a - b) / (abs(a) + abs(b))


def _dict_distance(stored: dict[str, float], current: dict[str, float]) -> float:
    """Mean per-key distance over the union of keys.

    Shared keys use :func:`_scalar_distance` on their values; a key present on
    only one side is a full mismatch (``1.0``). Two empty dicts are identical
    (``0.0``).
    """
    keys = stored.keys() | current.keys()
    if not keys:
        return 0.0
    total = 0.0
    for key in keys:
        if key in stored and key in current:
            total += _scalar_distance(stored[key], current[key])
        else:
            total += 1.0
    return total / len(keys)


def voice_metric_distances(stored: VoiceMetrics, current: VoiceMetrics) -> dict[str, float]:
    """Normalized [0, 1] distance per comparable metric (ADR-057 Decision 2).

    A metric that is ``None`` on either side is skipped (RULE-11 graceful: nothing
    to compare, never a crash). Dict metrics are skipped unless both sides provide
    a dict; their value is the mean per-key distance over the key union.

    Args:
        stored: The character's stored (profiled) metrics.
        current: The current-chapter metrics (from ``VoiceMetricsAnalyzer``).

    Returns:
        Mapping from metric name to its [0, 1] distance. Only metrics present on
        both sides appear.
    """
    distances: dict[str, float] = {}
    # Scalar metrics -- explicit access keeps pyright strict (no getattr -> Any).
    scalar_pairs: list[tuple[str, float | None, float | None]] = [
        ("avg_sentence_length", stored.avg_sentence_length, current.avg_sentence_length),
        ("sentence_length_std", stored.sentence_length_std, current.sentence_length_std),
        ("type_token_ratio", stored.type_token_ratio, current.type_token_ratio),
        ("avg_syllables_per_word", stored.avg_syllables_per_word, current.avg_syllables_per_word),
        ("contraction_rate", stored.contraction_rate, current.contraction_rate),
    ]
    for name, s, c in scalar_pairs:
        if s is None or c is None:
            continue
        distances[name] = _scalar_distance(s, c)
    # Dict metrics.
    dict_pairs: list[tuple[str, dict[str, float] | None, dict[str, float] | None]] = [
        ("verbal_tic_frequency", stored.verbal_tic_frequency, current.verbal_tic_frequency),
        ("punctuation_profile", stored.punctuation_profile, current.punctuation_profile),
    ]
    for name, s, c in dict_pairs:
        if s is None or c is None:
            continue
        distances[name] = _dict_distance(s, c)
    return distances


def metric_delta_subscore(stored: VoiceMetrics, current: VoiceMetrics) -> float | None:
    """Aggregate deterministic metric-delta sub-score in [0, 100] (100 == identical).

    Returns ``None`` when no metric is comparable on both sides (RULE-11 graceful);
    the caller then falls back to the qualitative signal alone.

    Args:
        stored: The character's stored (profiled) metrics.
        current: The current-chapter metrics.

    Returns:
        Sub-score in [0, 100], or ``None`` if nothing is comparable.
    """
    distances = voice_metric_distances(stored, current)
    if not distances:
        return None
    mean_distance = sum(distances.values()) / len(distances)
    return (1.0 - mean_distance) * 100.0


# ---------------------------------------------------------------------------
# Blend
# ---------------------------------------------------------------------------


def blend_scores(
    metric_subscore: float | None,
    qualitative_subscore: float | None,
    *,
    metric_weight: float,
    qualitative_weight: float,
) -> float | None:
    """Deterministic weighted blend of the two sub-scores into [0, 100].

    When one sub-score is ``None`` (e.g. no comparable metrics), the blend collapses
    onto the available signal. Returns ``None`` only when both are ``None``
    (nothing to score). Deterministic (ADR-021): identical inputs -> identical output.

    Args:
        metric_subscore: Deterministic metric-delta sub-score [0, 100] or ``None``.
        qualitative_subscore: Agent qualitative sub-score [0, 100] or ``None``.
        metric_weight: Weight of the metric sub-score (0-1).
        qualitative_weight: Weight of the qualitative sub-score (0-1).

    Returns:
        Blended score, or ``None`` if both inputs are ``None``.
    """
    # Collapse: if the metric half is absent, use the qualitative half (or None
    # when both are absent). Structured so pyright narrows each branch cleanly.
    if metric_subscore is None:
        return None if qualitative_subscore is None else float(qualitative_subscore)
    if qualitative_subscore is None:
        return float(metric_subscore)
    return metric_weight * metric_subscore + qualitative_weight * qualitative_subscore


# ---------------------------------------------------------------------------
# Result + orchestrator
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VoiceCheckScore:
    """Per-character voice-check result (ADR-057 Decision 2).

    Attributes:
        match_score: Overall blended match score [0, 100]. ``None`` when the
            character has no stored profile OR no sub-score is available.
        band: Severity band of *match_score* (``None`` when *match_score* is None).
        metric_delta_subscore: Deterministic metric-delta sub-score [0, 100] or
            ``None`` when no metric is comparable. Surfaced so the checker agent /
            report can show the deterministic half.
        has_profile: ``False`` iff the character has no stored voice profile -- the
            "no profile" signal the caller surfaces (RULE-11). ``True`` otherwise.
        n_comparable_metrics: Number of metrics that contributed to the delta.
    """

    match_score: float | None
    band: VoiceCheckBand | None
    metric_delta_subscore: float | None
    has_profile: bool
    n_comparable_metrics: int


class VoiceCheckScorer:
    """Pure deterministic voice-check scorer (WRITE-010 / ADR-057 Decision 2).

    Orchestrates the metric-delta sub-score, the agent qualitative sub-score, and
    the deterministic blend into a :class:`VoiceCheckScore`. Degrades gracefully
    when a character has no stored profile (RULE-11) -- returns a "no profile"
    signal rather than a fabricated score.

    The blend weights are configurable per RULE-18 (class-level annotated defaults
    + constructor injection, mirroring
    :class:`~narrare_core.analysis.dialogue_parser.DialogueParser.DEFAULT_CONTEXT_WINDOW`
    and :class:`~narrare_core.analysis.voice_metrics.VoiceMetricsAnalyzer`). They
    are eval-tunable (ADR-032 / ADR-057 Risk #2).

    Args:
        metric_weight: Weight of the deterministic metric-delta sub-score (0-1).
            Defaults to :attr:`DEFAULT_METRIC_WEIGHT`.
        qualitative_weight: Weight of the agent qualitative sub-score (0-1).
            Defaults to :attr:`DEFAULT_QUALITATIVE_WEIGHT`. Must be in [0, 1] and
            sum with *metric_weight* to 1.0 (within tolerance).

    Raises:
        ValueError: If either weight is outside [0, 1] or they do not sum to 1.0.
    """

    #: Weight of the deterministic metric-delta sub-score. Weighted slightly above
    #: the qualitative half because it is reproducible (ADR-021). Class-level
    #: annotated default + constructor injection -- RULE-18 pattern.
    DEFAULT_METRIC_WEIGHT: ClassVar[float] = 0.6

    #: Weight of the agent qualitative sub-score. Sums with
    #: :attr:`DEFAULT_METRIC_WEIGHT` to 1.0. RULE-18 pattern.
    DEFAULT_QUALITATIVE_WEIGHT: ClassVar[float] = 0.4

    def __init__(
        self,
        *,
        metric_weight: float = DEFAULT_METRIC_WEIGHT,
        qualitative_weight: float = DEFAULT_QUALITATIVE_WEIGHT,
    ) -> None:
        if not (0.0 <= metric_weight <= 1.0 and 0.0 <= qualitative_weight <= 1.0):
            raise ValueError(
                "weights must each be in [0, 1] "
                f"(got metric_weight={metric_weight}, qualitative_weight={qualitative_weight})"
            )
        if abs((metric_weight + qualitative_weight) - 1.0) > 1e-9:
            raise ValueError(
                "metric_weight + qualitative_weight must sum to 1.0 "
                f"(got {metric_weight} + {qualitative_weight} = "
                f"{metric_weight + qualitative_weight})"
            )
        self._metric_weight = metric_weight
        self._qualitative_weight = qualitative_weight

    def score(
        self,
        stored: VoiceMetrics | None,
        current: VoiceMetrics | None,
        qualitative_subscore: float | None,
    ) -> VoiceCheckScore:
        """Score a character's current voice against its stored profile.

        Args:
            stored: The character's stored (profiled) metrics, or ``None`` if the
                character has no profile.
            current: The current-chapter metrics (from ``VoiceMetricsAnalyzer``),
                or ``None`` when no dialogue was analysed.
            qualitative_subscore: Agent qualitative sub-score [0, 100] or ``None``.

        Returns:
            A :class:`VoiceCheckScore`. ``has_profile`` is ``False`` (and all score
            fields ``None``) when *stored* is ``None`` -- the "no profile" signal
            (RULE-11). The blended score is clamped to [0, 100].
        """
        # RULE-11: no stored profile -> "no profile" signal, never a fabricated score.
        if stored is None:
            return VoiceCheckScore(
                match_score=None,
                band=None,
                metric_delta_subscore=None,
                has_profile=False,
                n_comparable_metrics=0,
            )

        current_resolved = current if current is not None else VoiceMetrics()
        distances = voice_metric_distances(stored, current_resolved)
        metric_sub = metric_delta_subscore(stored, current_resolved)

        blended = blend_scores(
            metric_sub,
            qualitative_subscore,
            metric_weight=self._metric_weight,
            qualitative_weight=self._qualitative_weight,
        )
        if blended is None:
            # Profile exists but neither sub-score is available -> unscorable.
            return VoiceCheckScore(
                match_score=None,
                band=None,
                metric_delta_subscore=metric_sub,
                has_profile=True,
                n_comparable_metrics=len(distances),
            )
        clamped = max(0.0, min(100.0, blended))
        return VoiceCheckScore(
            match_score=clamped,
            band=band_for_score(clamped),
            metric_delta_subscore=metric_sub,
            has_profile=True,
            n_comparable_metrics=len(distances),
        )
