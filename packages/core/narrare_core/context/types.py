"""Shared types for context assembly.

Contains data classes used across all context assembler implementations.
Moved from ``writing/budget.py`` per ADR-025 Decision 3.

See: docs/architecture/decisions/025-feature-adoption-infrastructure.md
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TierBudget:
    """Token budget for a single context tier."""

    tier_name: str
    percentage: float
    token_limit: int
    pinned_bypass: bool = False


__all__ = ["TierBudget"]
