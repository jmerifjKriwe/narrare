"""3-tier token budget management for analysis features.

Simpler than the writing-specific 5-tier ``TokenBudgetManager`` —
analysis features need only content, KB context, and preferences,
with no mode-specific overrides or wiki optimization.

Per ADR-025 Decision 3 (Phase 5): ``core/analysis/`` owns its own
budget manager with analysis-specific tier names and percentages.

Tier allocation (default 32,000-token budget, ADR-082 Decision 5 —
shares context_total_budget with writing):
    content:      50%  — chapter text / content to analyze
    kb_context:   30%  — KB entities (characters, locations, factions, relationships)
    preferences:  20%  — user preferences, avoidance patterns
"""

from __future__ import annotations

from typing import ClassVar

from narrare_core.context.budget import DEFAULT_TOTAL_BUDGET
from narrare_core.context.types import TierBudget


class AnalysisBudgetManager:
    """Manages token budgets across 3 analysis context tiers.

    Usage::

        manager = AnalysisBudgetManager(total_budget=32_000)
        budgets = manager.allocate()
        content_limit = budgets["content"].token_limit
    """

    # ADR-082 Decision 5: analysis joins context_total_budget — same Core
    # constant as the writing manager, never a third literal.
    DEFAULT_TOTAL_BUDGET: int = DEFAULT_TOTAL_BUDGET

    TIER_ORDER: ClassVar[tuple[str, ...]] = (
        "content",
        "kb_context",
        "preferences",
    )

    _PERCENTAGES: ClassVar[dict[str, float]] = {
        "content": 0.50,
        "kb_context": 0.30,
        "preferences": 0.20,
    }

    def __init__(self, total_budget: int = DEFAULT_TOTAL_BUDGET) -> None:
        self._total_budget = total_budget

    @property
    def total_budget(self) -> int:
        """Total token budget across all tiers."""
        return self._total_budget

    def allocate(self) -> dict[str, TierBudget]:
        """Calculate token limits for each tier.

        Returns:
            Mapping of tier name to its budget allocation.
        """
        return {
            name: TierBudget(
                tier_name=name,
                percentage=pct,
                token_limit=round(self._total_budget * pct),
                pinned_bypass=False,
            )
            for name, pct in self._PERCENTAGES.items()
        }


__all__ = ["AnalysisBudgetManager"]
