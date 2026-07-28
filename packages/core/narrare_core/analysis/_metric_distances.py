"""_metric_distances — the shared per-metric delta normalization
(WRITE-010 / ADR-057 / ANAL-009 / ADR-074).

The single home of the bounded-relative-difference normalization consumed by
every voice/metric comparison in the codebase:

- WRITE-010 voice-check (:mod:`voice_check_scoring`).
- ANAL-009 Phase 1 character drift (:mod:`voice_drift_scoring`).
- ANAL-009 Phase 2B author drift (:mod:`author_voice_drift_scoring`).

ADR-057 Risk #3 / ADR-073 D2 no-duplication guarantee: exactly ONE
normalization (:func:`_scalar_distance` / :func:`_dict_distance`) lives here,
exposed via two typed facades — :func:`voice_metric_distances` (for
:class:`~narrare_core.kb.schemas.character.VoiceMetrics`) and
:func:`author_metric_distances` (for
:class:`~narrare_core.analysis.author_metrics.AuthorMetrics`) — that share it
through :func:`_scalar_field_distances`. Adding a new metric block means adding
a new typed facade here, never a new normalization.

Split out of :mod:`voice_check_scoring` so that module stays under the RULE-04
400-line hard limit (modularise, not minify) once author drift added a second
typed facade. :mod:`voice_check_scoring` re-exports these names so existing
``from voice_check_scoring import voice_metric_distances`` callers (and tests)
are unaffected.

The module is **pure** — no I/O, no LLM, no state — and **deterministic**
(ADR-021).

See Also
--------
ADR-057 — Voice-check checking-path contract (the delta primitive reused here).
ADR-073 — Character Voice Drift (Decision 2 — one primitive, two consumers).
ADR-074 — Author Voice Storage Contract (AuthorMetrics facade).
"""

from __future__ import annotations

# Runtime imports (not TYPE_CHECKING): VoiceMetrics is constructed at runtime by
# callers + referenced in signatures. AuthorMetrics is annotation-only here but
# kept as a runtime import for parity + so the facade is self-contained. Both
# carry a TC001 suppression to match voice_drift_scoring.py's VoiceMetrics
# convention.
from narrare_core.analysis.author_metrics import AuthorMetrics  # noqa: TC001
from narrare_core.kb.schemas.character import VoiceMetrics  # noqa: TC001


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


def _scalar_field_distances(
    pairs: list[tuple[str, float | None, float | None]],
) -> dict[str, float]:
    """Per-scalar-field [0, 1] distance, skipping any field None on a side.

    The shared core of :func:`voice_metric_distances` +
    :func:`author_metric_distances` (ADR-057 Risk #3 — one normalization, two
    typed facades). Explicit ``(name, stored, current)`` tuples keep pyright
    strict happy (no ``getattr`` → ``Any``) — mirroring the original
    ``voice_metric_distances`` access style.

    RULE-11 graceful: a field that is ``None`` on either side is skipped
    (never a crash, never a fabricated distance).
    """
    distances: dict[str, float] = {}
    for name, s, c in pairs:
        if s is None or c is None:
            continue
        distances[name] = _scalar_distance(s, c)
    return distances


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
    # Scalar metrics -- explicit access keeps pyright strict (no getattr -> Any).
    distances = _scalar_field_distances(
        [
            ("avg_sentence_length", stored.avg_sentence_length, current.avg_sentence_length),
            ("sentence_length_std", stored.sentence_length_std, current.sentence_length_std),
            ("type_token_ratio", stored.type_token_ratio, current.type_token_ratio),
            (
                "avg_syllables_per_word",
                stored.avg_syllables_per_word,
                current.avg_syllables_per_word,
            ),
            ("contraction_rate", stored.contraction_rate, current.contraction_rate),
        ]
    )
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


def author_metric_distances(stored: AuthorMetrics, current: AuthorMetrics) -> dict[str, float]:
    """Normalized [0, 1] distance per comparable AuthorMetrics field (Phase 2B).

    The author-voice analogue of :func:`voice_metric_distances`, for the
    prose-level :class:`AuthorMetrics` block (ANAL-009 Phase 2B / ADR-074).
    Reuses the SAME :func:`_scalar_distance` normalization via the shared
    :func:`_scalar_field_distances` helper (ADR-057 Risk #3 — zero
    duplication; one normalization, two typed facades).

    Every AuthorMetrics field is a scalar ``float | None`` in ``[0.0, 1.0]`` —
    there are no dict fields (unlike VoiceMetrics), so the comparison is purely
    scalar. ``extra="allow"`` fields on AuthorMetrics are forward-compat
    storage (ADR-074) and are intentionally NOT compared here — only the four
    governed scalar fields participate, mirroring how
    :func:`voice_metric_distances` compares only the governed VoiceMetrics
    fields. A future ADR-032 metric gets added here explicitly.

    RULE-11 graceful: a field that is ``None`` on either side is skipped
    (never a crash) — identical contract to :func:`voice_metric_distances`.

    Args:
        stored: The stored (profiled) author metrics.
        current: The current-chapter author metrics (from
            :class:`~narrare_core.analysis.author_metrics.AuthorMetricsAnalyzer`).

    Returns:
        Mapping from metric name to its [0, 1] distance. Only fields present on
        both sides appear.
    """
    return _scalar_field_distances(
        [
            ("dialogue_ratio", stored.dialogue_ratio, current.dialogue_ratio),
            ("description_density", stored.description_density, current.description_density),
            (
                "action_introspection_ratio",
                stored.action_introspection_ratio,
                current.action_introspection_ratio,
            ),
            ("metaphor_density", stored.metaphor_density, current.metaphor_density),
        ]
    )


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


__all__ = [
    "author_metric_distances",
    "metric_delta_subscore",
    "voice_metric_distances",
]
