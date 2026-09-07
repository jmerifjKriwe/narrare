"""KB entity resolution layer (ADR-085).

Deterministic, pure-Core engine that scores candidate KB entry pairs for
identity and surfaces merge suggestions.  This package hosts the data
models, name-tier classification, and detection signals; scoring and
orchestration land in later phases.
"""

from narrare_core.kb.resolution.models import (
    EntitySnapshot,
    EntryProvenance,
    PairScore,
    ResolutionBand,
    SignalResult,
)
from narrare_core.kb.resolution.name_tiers import (
    classify_name_tier,
    normalize_name,
)
from narrare_core.kb.resolution.signals import (
    attributes_signal,
    embedding_signal,
    neighborhood_signal,
    temporal_signal,
)

__all__ = [
    "EntitySnapshot",
    "EntryProvenance",
    "PairScore",
    "ResolutionBand",
    "SignalResult",
    "attributes_signal",
    "classify_name_tier",
    "embedding_signal",
    "neighborhood_signal",
    "normalize_name",
    "temporal_signal",
]
