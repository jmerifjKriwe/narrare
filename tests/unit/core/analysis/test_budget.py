"""Tests for analysis/budget.py — AnalysisBudgetManager.

Covers:
1. Default allocation — 50/30/20 split
2. Custom total budget — proportional scaling
3. Tier ordering — content, kb_context, preferences
4. TierBudget field values — percentage, token_limit, pinned_bypass
"""

from __future__ import annotations

import pytest

from narrare_core.analysis.budget import AnalysisBudgetManager
from narrare_core.context.types import TierBudget


class TestDefaultAllocation:
    """Default 6000-token budget with 50/30/20 split."""

    def test_returns_three_tiers(self) -> None:
        manager = AnalysisBudgetManager()
        budgets = manager.allocate()

        assert set(budgets.keys()) == {"content", "kb_context", "preferences"}

    def test_content_tier_gets_50_percent(self) -> None:
        manager = AnalysisBudgetManager(total_budget=6000)
        budgets = manager.allocate()

        assert budgets["content"].percentage == pytest.approx(0.50, abs=0.01)
        assert budgets["content"].token_limit == 3000  # 6000 * 0.50

    def test_kb_context_tier_gets_30_percent(self) -> None:
        manager = AnalysisBudgetManager(total_budget=6000)
        budgets = manager.allocate()

        assert budgets["kb_context"].percentage == pytest.approx(0.30, abs=0.01)
        assert budgets["kb_context"].token_limit == 1800  # 6000 * 0.30

    def test_preferences_tier_gets_20_percent(self) -> None:
        manager = AnalysisBudgetManager(total_budget=6000)
        budgets = manager.allocate()

        assert budgets["preferences"].percentage == pytest.approx(0.20, abs=0.01)
        assert budgets["preferences"].token_limit == 1200  # 6000 * 0.20

    def test_total_tokens_sum_to_budget(self) -> None:
        manager = AnalysisBudgetManager(total_budget=6000)
        budgets = manager.allocate()

        total = sum(b.token_limit for b in budgets.values())
        assert total == 6000

    def test_percentages_sum_to_one(self) -> None:
        manager = AnalysisBudgetManager()
        budgets = manager.allocate()

        total_pct = sum(b.percentage for b in budgets.values())
        assert total_pct == pytest.approx(1.0, abs=0.01)

    def test_no_pinned_bypass(self) -> None:
        """Analysis tiers have no pinned bypass (unlike writing)."""
        manager = AnalysisBudgetManager()
        budgets = manager.allocate()

        for budget in budgets.values():
            assert budget.pinned_bypass is False


class TestCustomBudget:
    """Custom total budget — proportional scaling."""

    def test_small_budget_scales_proportionally(self) -> None:
        manager = AnalysisBudgetManager(total_budget=1000)
        budgets = manager.allocate()

        assert budgets["content"].token_limit == 500  # 50%
        assert budgets["kb_context"].token_limit == 300  # 30%
        assert budgets["preferences"].token_limit == 200  # 20%

    def test_large_budget_scales_proportionally(self) -> None:
        manager = AnalysisBudgetManager(total_budget=20000)
        budgets = manager.allocate()

        assert budgets["content"].token_limit == 10000  # 50%
        assert budgets["kb_context"].token_limit == 6000  # 30%
        assert budgets["preferences"].token_limit == 4000  # 20%


class TestTierOrder:
    """TIER_ORDER matches the allocation keys."""

    def test_tier_order_matches_allocation(self) -> None:
        manager = AnalysisBudgetManager()
        budgets = manager.allocate()

        assert tuple(budgets.keys()) == AnalysisBudgetManager.TIER_ORDER


class TestTierBudgetFields:
    """Each TierBudget has correct field values."""

    def test_tier_budget_fields_populated(self) -> None:
        manager = AnalysisBudgetManager(total_budget=6000)
        budgets = manager.allocate()

        for name, budget in budgets.items():
            assert isinstance(budget, TierBudget)
            assert budget.tier_name == name
            assert budget.percentage > 0
            assert budget.token_limit > 0


class TestTotalBudgetProperty:
    """total_budget property reflects constructor value."""

    def test_default_total_budget(self) -> None:
        manager = AnalysisBudgetManager()
        assert manager.total_budget == 6000

    def test_custom_total_budget(self) -> None:
        manager = AnalysisBudgetManager(total_budget=8000)
        assert manager.total_budget == 8000
