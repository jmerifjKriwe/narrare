"""KB entity resolution orchestration (ADR-085 app-side sub-package).

Contracts-first sub-package (spec §2): snapshot building (P3), detection
analysis (P3/P4), merge execution (P4), and the uncertain-band
adjudicator (P5) land here slice by slice. Dependency direction is
one-way (RULE-07) — routers → services → repository protocols; the pure
scoring engine lives in ``narrare_core.kb.resolution`` and stays I/O-free.
"""

from narrare.kb.entity_resolution.contracts import (
    MergeExecutorProtocol,
    ResolutionAnalyzerProtocol,
    SnapshotBuilderProtocol,
    UncertainBandAdjudicatorProtocol,
)
from narrare.kb.entity_resolution.snapshot_service import SnapshotBuilder

__all__ = [
    "MergeExecutorProtocol",
    "ResolutionAnalyzerProtocol",
    "SnapshotBuilder",
    "SnapshotBuilderProtocol",
    "UncertainBandAdjudicatorProtocol",
]
