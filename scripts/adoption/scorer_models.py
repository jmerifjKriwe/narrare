"""Adoption scorer data models.

Extracted from ``scorer.py`` to keep score arithmetic, status policy, and data
shape responsibilities separate under RULE-04/RULE-06.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from adoption.scorer_modes import ModeScore


def _empty_modes() -> list[ModeScore]:
    """Return a typed empty mode list for dataclass defaults."""
    return []


@dataclass
class CheckDetail:
    """One dimension of the adoption check."""

    name: str
    weight: float
    adopted: float  # 0.0-1.0 (for partial: 0.5 when missing)
    applicable: bool = True
    note: str = ""


@dataclass
class CategoryScore:
    """Adoption score for a single feature category."""

    category: str
    score: float
    status: str
    details: list[CheckDetail] = field(default_factory=list[CheckDetail])
    missing_must: list[str] = field(default_factory=list[str])
    missing_should: list[str] = field(default_factory=list[str])
    missing_locales: dict[str, list[str]] = field(default_factory=dict[str, list[str]])
    inline_fallbacks: int = 0
    modes: list[ModeScore] = field(default_factory=_empty_modes)


@dataclass
class AdoptionReport:
    """Complete adoption report across all feature categories."""

    overall_score: float
    status: str
    categories: list[CategoryScore] = field(default_factory=list[CategoryScore])
    total_inline_fallbacks: int = 0
    mode_count: int = 0
    runtime_verified_count: int = 0
    adopted_count: int = 0
    runtime_evidence_gap_count: int = 0
