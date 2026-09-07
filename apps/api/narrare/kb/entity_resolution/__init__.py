"""KB entity resolution orchestration (ADR-085 app-side sub-package).

Contracts-first sub-package (spec §2): snapshot building (P3), detection
analysis (P3/P4), merge execution (P4), and the endorsement adjudication
surface (P4) land here slice by slice. Dependency direction is one-way
(RULE-07) — routers → services → repository protocols; the pure scoring
engine lives in ``narrare_core.kb.resolution`` and stays I/O-free.
"""

from narrare.kb.entity_resolution.analysis_cache import ResolutionAnalysisCache
from narrare.kb.entity_resolution.analysis_service import ResolutionAnalysisService
from narrare.kb.entity_resolution.contracts import (
    DismissedSuggestionStoreProtocol,
    MergeExecutorProtocol,
    ResolutionAnalyzerProtocol,
    SnapshotBuilderProtocol,
    UncertainBandAdjudicatorProtocol,
)
from narrare.kb.entity_resolution.endorse_service import ResolutionEndorseService
from narrare.kb.entity_resolution.snapshot_service import SnapshotBuilder

__all__ = [
    "DismissedSuggestionStoreProtocol",
    "MergeExecutorProtocol",
    "ResolutionAnalysisCache",
    "ResolutionAnalysisService",
    "ResolutionAnalyzerProtocol",
    "ResolutionEndorseService",
    "SnapshotBuilder",
    "SnapshotBuilderProtocol",
    "UncertainBandAdjudicatorProtocol",
]
