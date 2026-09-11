"""Scoring engine for KB entity resolution (ADR-085).

Aggregates the five detection signals — S1 name tier, S2 temporal, S3
attributes, S4 neighborhood, S5 embedding — into a calibrated confidence
and a resolution band per candidate pair, semantics per spec §4:

``raw = 0.35·S1 + 0.30·S2 + 0.20·S3 + 0.10·S4 + 0.05·S5`` (weights sum to
1.0), ``conf = clamp01(raw)``, then deterministic overrides:

- **veto cap** — any signal veto → ``conf = min(conf, VETO_CAP)``; the
  band can never be AUTO_ELIGIBLE and the veto signal names are listed.
- **name-only ceiling** — zero corroborations (a corroboration is
  ``S2 > 0`` or ``S3 > 0`` or ``S4 > 0``) → ``conf = min(conf,
  NAME_ONLY_CEILING)``: an S1-only or S1+S5 pair can never reach
  AUTO_ELIGIBLE.

Bands: ``AUTO_ELIGIBLE`` iff ``conf ≥ AUTO_THRESHOLD`` AND no veto AND
``S1 ≥ SUBSET (0.7)`` AND ≥ 2 corroborations AND ``S2 == +1.0``;
``REVIEW`` iff ``conf ≥ REVIEW_THRESHOLD``; else ``SUPPRESSED``.

The engine is pure: no I/O, no clock, no randomness — identical inputs
always yield an identical :class:`PairScore`.  Phase P1 ends here; app
wiring lands in later phases.
"""

from __future__ import annotations

from itertools import combinations
from typing import TYPE_CHECKING, Final

from narrare_core.kb.resolution.models import (
    EntitySnapshot,
    PairScore,
    ResolutionBand,
    SignalResult,
)
from narrare_core.kb.resolution.name_tiers import NONE, SUBSET, classify_name_tier
from narrare_core.kb.resolution.signals import (
    attributes_signal,
    embedding_signal,
    neighborhood_signal,
    temporal_signal,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

# The five signal results in canonical order: S1..S5.
type _FiveSignals = tuple[SignalResult, SignalResult, SignalResult, SignalResult, SignalResult]

# Signal weights (spec §4 confidence formula) — ADR-085-referenced defaults,
# not runtime configuration; recalibration is a spec edit with benchmark evidence.
W_NAME: Final[float] = 0.35
W_TEMPORAL: Final[float] = 0.30
W_ATTRIBUTES: Final[float] = 0.20
W_NEIGHBORHOOD: Final[float] = 0.10
W_EMBEDDING: Final[float] = 0.05

# Band thresholds and override caps (spec §4 "Confidence formula"/"Bands").
AUTO_THRESHOLD: Final[float] = 0.85
REVIEW_THRESHOLD: Final[float] = 0.45
VETO_CAP: Final[float] = 0.40
NAME_ONLY_CEILING: Final[float] = 0.55


class ResolutionEngine:
    """Pure pair scorer and candidate enumerator over entity snapshots."""

    def score_pair(self, a: EntitySnapshot, b: EntitySnapshot) -> PairScore:
        """Score one candidate pair; entry ids are normalized to (min, max).

        Runs all five signals (S1 is classified here and fed into the
        temporal signal as the already-computed tier — it is not
        re-derived inside the signals layer), aggregates the weighted
        raw confidence, applies the veto cap and name-only ceiling, and
        resolves the band.
        """
        signals = _all_signals(a, b)
        confidence = _confidence(signals)
        return PairScore(
            entry_a_id=min(a.entry_id, b.entry_id),
            entry_b_id=max(a.entry_id, b.entry_id),
            confidence=confidence,
            band=_band(signals, confidence),
            signals=signals,
            vetoes=tuple(signal.signal for signal in signals if signal.veto),
        )

    def find_candidates(
        self, snapshots: Sequence[EntitySnapshot]
    ) -> tuple[tuple[EntitySnapshot, EntitySnapshot], ...]:
        """Enumerate candidate pairs worth scoring (spec §4 candidate filter).

        A pair qualifies when both snapshots share ``entity_type``, do not
        share an entry id (no self-pairs), and classify above the NONE name
        tier (EXACT, SUBSET, or FUZZY).  Each unordered pair appears exactly
        once; within a pair the snapshot with the smaller entry id comes
        first, so the output is deterministic for a given input order.
        """
        candidates: list[tuple[EntitySnapshot, EntitySnapshot]] = []
        for a, b in combinations(snapshots, 2):
            if a.entity_type != b.entity_type or a.entry_id == b.entry_id:
                continue
            tier_value, _ = classify_name_tier(a.name, b.name)
            if tier_value == NONE:
                continue
            candidates.append((a, b) if a.entry_id < b.entry_id else (b, a))
        return tuple(candidates)


# --- Internal helpers ---------------------------------------------------------


def _all_signals(a: EntitySnapshot, b: EntitySnapshot) -> _FiveSignals:
    """Run all five detection signals in canonical S1..S5 order."""
    s1_value, s1_name = classify_name_tier(a.name, b.name)
    return (
        SignalResult(
            "name_tier",
            s1_value,
            detail=f"{s1_name} tier ({s1_value:g}) for '{a.name}' vs '{b.name}'",
        ),
        temporal_signal(a, b, s1_tier=s1_value),
        attributes_signal(a, b),
        neighborhood_signal(a, b),
        embedding_signal(a, b),
    )


def _confidence(signals: _FiveSignals) -> float:
    """Weighted aggregation with clamp and the two deterministic overrides."""
    raw = (
        W_NAME * signals[0].value
        + W_TEMPORAL * signals[1].value
        + W_ATTRIBUTES * signals[2].value
        + W_NEIGHBORHOOD * signals[3].value
        + W_EMBEDDING * signals[4].value
    )
    confidence = max(0.0, min(1.0, raw))
    if any(signal.veto for signal in signals):
        confidence = min(confidence, VETO_CAP)
    if _corroborations(signals) == 0:
        confidence = min(confidence, NAME_ONLY_CEILING)
    return confidence


def _corroborations(signals: _FiveSignals) -> int:
    """Count positive corroborators among S2/S3/S4 (S5 never corroborates)."""
    return sum(1 for signal in signals[1:4] if signal.value > 0)


def _band(signals: _FiveSignals, confidence: float) -> ResolutionBand:
    """Resolve the band per spec §4 thresholds and AUTO preconditions.

    The veto cap already forces ``conf ≤ VETO_CAP < REVIEW_THRESHOLD``,
    and the AUTO branch additionally requires "no veto" explicitly — a
    vetoed pair can therefore never be AUTO_ELIGIBLE (band ≤ REVIEW).
    """
    if (
        confidence >= AUTO_THRESHOLD
        and not any(signal.veto for signal in signals)
        and signals[0].value >= SUBSET
        and _corroborations(signals) >= 2
        and signals[1].value == 1.0
    ):
        return "AUTO_ELIGIBLE"
    if confidence >= REVIEW_THRESHOLD:
        return "REVIEW"
    return "SUPPRESSED"


__all__ = [
    "AUTO_THRESHOLD",
    "NAME_ONLY_CEILING",
    "REVIEW_THRESHOLD",
    "VETO_CAP",
    "W_ATTRIBUTES",
    "W_EMBEDDING",
    "W_NAME",
    "W_NEIGHBORHOOD",
    "W_TEMPORAL",
    "ResolutionEngine",
]
