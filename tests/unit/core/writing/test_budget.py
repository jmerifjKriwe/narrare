"""Tests for writing/budget.py — TokenBudgetManager and cap_to_budget.

Covers:
1. Default allocation percentages
2. First-chapter reallocation
3. Pinned bypass flag
4. Custom total budget
5. Percentages sum to 1.0
6. Tier order preserved
7. cap_to_budget — within budget, over budget, edge cases
"""

from __future__ import annotations

import pytest

from narrare_core.writing.budget import TokenBudgetManager, cap_to_budget


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


class TestCapToBudget:
    """Tests for the cap_to_budget utility function."""

    # -- within budget --

    def test_text_within_budget_returned_unchanged(self) -> None:
        text = "hello world"
        # 2 words * 1.3 ~ 3 tokens -> well within 100
        assert cap_to_budget(text, max_tokens=100) == text

    def test_text_exactly_at_budget_not_truncated(self) -> None:
        # "a b c" -> 3 words * 1.3 = round(3.9) = 4 tokens
        text = "a b c"
        assert cap_to_budget(text, max_tokens=4) == text

    # -- over budget --

    def test_text_exceeding_budget_is_truncated(self) -> None:
        text = "one two three four five"
        # 5 words * 1.3 = round(6.5) = 7 tokens
        result = cap_to_budget(text, max_tokens=4)
        assert result != text
        # Result should be fewer words
        assert len(result.split()) < len(text.split())

    # -- edge cases --

    def test_empty_text_returns_empty_string(self) -> None:
        assert cap_to_budget("", max_tokens=100) == ""

    def test_max_tokens_zero_returns_empty_string(self) -> None:
        assert cap_to_budget("some text", max_tokens=0) == ""

    def test_max_tokens_negative_returns_empty_string(self) -> None:
        assert cap_to_budget("some text", max_tokens=-5) == ""

    # -- word boundaries --

    def test_truncation_preserves_word_boundaries(self) -> None:
        text = "alpha beta gamma delta epsilon"
        # 5 words * 1.3 ~ 7 tokens; allow only 3 tokens
        result = cap_to_budget(text, max_tokens=3)
        # 2 words * 1.3 = round(2.6) = 3 tokens -> within budget
        assert result.split() == ["alpha", "beta"]

    # -- custom counter --

    def test_custom_token_counter_is_used(self) -> None:
        # Count each character as 1 token for predictability
        char_counter = lambda t: len(t)  # noqa: E731
        text = "abcdefghij"  # 10 chars = 10 tokens
        result = cap_to_budget(text, max_tokens=5, token_counter=char_counter)
        assert len(result) <= 5

    def test_custom_counter_within_budget_returned_unchanged(self) -> None:
        char_counter = lambda t: len(t)  # noqa: E731
        text = "abc"  # 3 chars = 3 tokens, within budget of 10
        assert cap_to_budget(text, max_tokens=10, token_counter=char_counter) == text
