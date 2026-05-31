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

__all__ = [
    "AdoptionReport",
    "CategoryScore",
    "CheckDetail",
    "compute_adoption_report",
]
