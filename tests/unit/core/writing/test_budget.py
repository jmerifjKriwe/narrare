"""Tests for writing/budget.py — TokenBudgetManager.

Covers:
1. Default allocation percentages
2. First-chapter reallocation
3. Pinned bypass flag
4. Custom total budget
5. Percentages sum to 1.0
6. Tier order preserved
"""

from __future__ import annotations

import pytest

from narrare_core.writing.budget import TokenBudgetManager


class TestTokenBudgetManager:
    """Tests for the budget manager."""

    def test_default_allocation(self) -> None:
        mgr = TokenBudgetManager(6000)
        budgets = mgr.allocate()

        assert budgets["immediate"].token_limit == 1800  # 30%
        assert budgets["recent"].token_limit == 1200  # 20%
        assert budgets["kb_referenced"].token_limit == 1500  # 25%
        assert budgets["kb_suggested"].token_limit == 900  # 15%
        assert budgets["pinned"].token_limit == 600  # 10%

    def test_first_chapter_reallocation(self) -> None:
        mgr = TokenBudgetManager(6000)
        budgets = mgr.allocate(first_chapter=True)

        assert budgets["recent"].token_limit == 0
        assert budgets["kb_referenced"].token_limit == 2100  # 35%
        assert budgets["kb_suggested"].token_limit == 1500  # 25%
        assert budgets["immediate"].token_limit == 1800  # 30% unchanged
        assert budgets["pinned"].token_limit == 600  # 10% unchanged

    def test_pinned_has_bypass_flag(self) -> None:
        mgr = TokenBudgetManager(6000)
        budgets = mgr.allocate()

        assert budgets["pinned"].pinned_bypass is True
        for name, budget in budgets.items():
            if name != "pinned":
                assert budget.pinned_bypass is False

    def test_custom_total_budget(self) -> None:
        mgr = TokenBudgetManager(10_000)
        budgets = mgr.allocate()

        assert budgets["immediate"].token_limit == 3000  # 30%
        assert mgr.total_budget == 10_000

    def test_percentages_sum_to_one(self) -> None:
        mgr = TokenBudgetManager(6000)
        budgets = mgr.allocate()
        total_pct = sum(b.percentage for b in budgets.values())
        assert total_pct == pytest.approx(1.0)

    def test_first_chapter_percentages_sum_to_one(self) -> None:
        mgr = TokenBudgetManager(6000)
        budgets = mgr.allocate(first_chapter=True)
        total_pct = sum(b.percentage for b in budgets.values())
        assert total_pct == pytest.approx(1.0)

    def test_tier_order_preserved(self) -> None:
        mgr = TokenBudgetManager(6000)
        budgets = mgr.allocate()
        assert list(budgets.keys()) == list(TokenBudgetManager.TIER_ORDER)
