"""Data models for the KB entity resolution layer (ADR-085, Phase P1).

Pure frozen dataclasses describing the shape consumed and produced by the
resolution engine.  No I/O, no side effects, no validation logic — value
normalization and clamping live in the signal/scoring layers, not here.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

ResolutionBand = Literal["SUPPRESSED", "REVIEW", "AUTO_ELIGIBLE"]


@dataclass(frozen=True, slots=True)
class EntryProvenance:
    """Where and when an entry was extracted or updated."""

    chapters: tuple[int, ...]  # ordered chapter positions
    first_seen_chapter: int | None
    last_seen_chapter: int | None
    name_variants: tuple[str, ...]  # names used in updates


@dataclass(frozen=True, slots=True)
class EntitySnapshot:
    """Immutable view of one KB entry as consumed by the resolution engine.

    Built by the snapshot service; deprecated entries are excluded by the
    builder, not by the engine.
    """

    entry_id: UUID
    name: str
    entity_type: str
    status: str
    metadata: Mapping[str, object]
    provenance: EntryProvenance | None  # None = unknown (never negative)
    neighbor_ids: frozenset[UUID]  # via relationship adjacency
    embedding: Sequence[float] | None  # precomputed; None = unknown


@dataclass(frozen=True, slots=True)
class SignalResult:
    """Outcome of one detection signal for a candidate pair.

    ``value`` is normalized to ``[-1, 1]`` (+ corroborating, - contradicting,
    0 unknown/neutral) and is NOT validated at model level — the scoring
    layer clamps.  ``detail`` surfaces as human-readable evidence in the
    suggestion response.
    """

    signal: str  # e.g. "name_tier", "temporal", ...
    value: float
    veto: bool = False
    detail: str = ""


@dataclass(frozen=True, slots=True)
class PairScore:
    """Aggregated confidence verdict for one candidate entry pair.

    The constructor takes the entry ids exactly as given — it does NOT
    normalize their order.  Ordering (``entry_a_id`` = min, ``entry_b_id``
    = max by id) is the responsibility of the scoring layer that creates
    the ``PairScore``.
    """

    entry_a_id: UUID
    entry_b_id: UUID
    confidence: float  # [0, 1]
    band: ResolutionBand
    signals: tuple[SignalResult, ...]
    vetoes: tuple[str, ...]


__all__ = [
    "EntitySnapshot",
    "EntryProvenance",
    "PairScore",
    "ResolutionBand",
    "SignalResult",
]
