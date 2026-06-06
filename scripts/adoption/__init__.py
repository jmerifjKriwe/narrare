"""Narrare Feature Adoption Scoring — public API.

Computes per-category and overall adoption scores based on the
``adoption-registry.yaml`` and the current state of bundled prompts.

ADR-025 Decision 5 is the authoritative specification.
"""

from adoption.scorer import (
    AdoptionReport,
    CategoryScore,
    CheckDetail,
    compute_adoption_report,
)
from adoption.scorer_modes import ModeScore, RuntimeCheckDetail

__all__ = [
    "AdoptionReport",
    "CategoryScore",
    "CheckDetail",
    "ModeScore",
    "RuntimeCheckDetail",
    "compute_adoption_report",
]
