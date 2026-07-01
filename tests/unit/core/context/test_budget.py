"""Unit tests for ``TokenBudgetManager`` allocation modes.

Covers the ``mode`` dispatch branches in ``allocate()`` — particularly the
rewrite percentages (40/15/25/10/10) and the ``wiki_optimized`` shift.
"""

from __future__ import annotations

import pytest

from narrare_core.context.budget import TokenBudgetManager


class TestAllocateModes:
    def test_rewrite_mode_uses_rewrite_percentages(self) -> None:
        manager = TokenBudgetManager(total_budget=10000)

        budgets = manager.allocate(mode="rewrite")

        # Rewrite percentages are 40/15/25/10/10 across the five tiers.
        total = sum(b.percentage for b in budgets.values())
        assert total == pytest.approx(1.0, abs=0.01)
        # The immediate tier receives 40% under rewrite (more headroom).
        assert budgets["immediate"].percentage == pytest.approx(0.40, abs=0.01)

    def test_rewrite_selection_mode_matches_rewrite(self) -> None:
        manager = TokenBudgetManager(total_budget=10000)

        rewrite = manager.allocate(mode="rewrite")
        selection = manager.allocate(mode="rewrite_selection")

        assert {k: v.token_limit for k, v in selection.items()} == {
            k: v.token_limit for k, v in rewrite.items()
        }

    def test_extend_mode_distinct_from_rewrite(self) -> None:
        manager = TokenBudgetManager(total_budget=10000)

        extend = manager.allocate(mode="extend")
        rewrite = manager.allocate(mode="rewrite")

        # Extend uses a different immediate percentage (50) than rewrite (40).
        assert extend["immediate"].percentage != rewrite["immediate"].percentage

    def test_default_mode_uses_base_percentages(self) -> None:
        manager = TokenBudgetManager(total_budget=10000)

        budgets = manager.allocate()

        total = sum(b.percentage for b in budgets.values())
        assert total == pytest.approx(1.0, abs=0.01)

    def test_first_chapter_mode_redistributes_recent_budget(self) -> None:
        manager = TokenBudgetManager(total_budget=10000)

        default = manager.allocate()
        first = manager.allocate(first_chapter=True)

        # On first chapter the recent tier gives up its budget to the KB tiers.
        assert first["recent"].token_limit < default["recent"].token_limit


class TestAllocateWikiOptimized:
    def test_wiki_optimized_shifts_budget_to_immediate(self) -> None:
        manager = TokenBudgetManager(total_budget=10000)

        default = manager.allocate()
        optimized = manager.allocate(wiki_optimized=True)

        assert optimized["immediate"].percentage > default["immediate"].percentage
        assert optimized["kb_referenced"].percentage < default["kb_referenced"].percentage
        # Total still normalises to ~1.0 after the shift.
        total = sum(b.percentage for b in optimized.values())
        assert total == pytest.approx(1.0, abs=0.01)


class TestTokenBudgetManagerOverrides:
    def test_override_exceeding_one_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match=r"must not exceed 1\.0"):
            TokenBudgetManager(total_budget=10000, tier_overrides={"immediate": 1.5})

    def test_negative_override_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match=r"must not be negative"):
            TokenBudgetManager(total_budget=10000, tier_overrides={"immediate": -0.1})

    def test_total_budget_property(self) -> None:
        manager = TokenBudgetManager(total_budget=8000)
        assert manager.total_budget == 8000
