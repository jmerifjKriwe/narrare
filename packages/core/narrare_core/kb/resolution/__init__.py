"""KB entity resolution layer (ADR-085).

Deterministic, pure-Core engine that scores candidate KB entry pairs for
identity and surfaces merge suggestions.  This package hosts the data
models; signals, scoring, and orchestration land in later phases.
"""

from narrare_core.kb.resolution.models import (
    EntitySnapshot,
    EntryProvenance,
    PairScore,
    ResolutionBand,
    SignalResult,
)

__all__ = [
    "EntitySnapshot",
    "EntryProvenance",
    "PairScore",
    "ResolutionBand",
    "SignalResult",
]
