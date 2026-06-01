"""Tests for analysis/assembler.py — AnalysisContextAssembler.

Covers:
1. Full assembly — all tiers populated correctly
2. Budget enforcement — content truncated when over limit
3. Overflow cascade — unused tokens flow to next tier
4. KB proportional distribution — truncation distributed proportionally
5. Empty inputs — all empty strings, partial empty
6. Custom token counter — injection works
7. Protocol compliance — satisfies ContextAssembler base and AnalysisAssemblerProtocol
"""

from __future__ import annotations

import pytest

from narrare_core.analysis.assembler import AnalysisContextAssembler
from narrare_core.analysis.contracts import AnalysisAssemblerProtocol
from narrare_core.context.assembler import ContextAssembler


def _make_long_text(target_tokens: int) -> str:
    """Generate text with approximately ``target_tokens`` tokens.

    Uses ~5 chars per word, so target_tokens words give roughly
    target_tokens * 1.3 tokens via the default counter.
    """
    words_per_token = 1.3
    word_count = int(target_tokens / words_per_token)
    return " ".join(f"word{i}" for i in range(word_count))


@pytest.fixture()
def assembler() -> AnalysisContextAssembler:
    """Default assembler with 6000-token budget."""
    return AnalysisContextAssembler(total_budget=6000)


@pytest.fixture()
def small_assembler() -> AnalysisContextAssembler:
    """Assembler with 1000-token budget for truncation testing."""
    return AnalysisContextAssembler(total_budget=1000)


class TestFullAssembly:
    """All tiers populated correctly when within budget."""

    @pytest.mark.asyncio
    async def test_returns_dict_with_all_keys(self, assembler: AnalysisContextAssembler) -> None:
        result = await assembler.assemble(
            content="Chapter text.",
            kb_characters="Alice: A warrior.",
            kb_locations="Castle: A fortress.",
            kb_factions="Rebels: Freedom fighters.",
            kb_relationships="Alice → ally → Bob",
            user_preferences="Prefers dark themes.",
            avoidance_patterns="No graphic violence.",
        )

        assert isinstance(result, dict)
        expected_keys = {
            "content",
            "kb_characters",
            "kb_locations",
            "kb_factions",
            "kb_relationships",
            "user_preferences",
            "avoidance_patterns",
        }
        assert set(result.keys()) == expected_keys

    @pytest.mark.asyncio
    async def test_returns_input_when_within_budget(
        self, assembler: AnalysisContextAssembler
    ) -> None:
        """Short inputs pass through unchanged when within budget."""
        result = await assembler.assemble(
            content="Short content.",
            kb_characters="Alice.",
        )

        assert result["content"] == "Short content."
        assert result["kb_characters"] == "Alice."

    @pytest.mark.asyncio
    async def test_empty_input_returns_empty_strings(
        self, assembler: AnalysisContextAssembler
    ) -> None:
        result = await assembler.assemble()

        assert result["content"] == ""
        assert result["kb_characters"] == ""
        assert result["kb_locations"] == ""
        assert result["kb_factions"] == ""
        assert result["kb_relationships"] == ""
        assert result["user_preferences"] == ""
        assert result["avoidance_patterns"] == ""


class TestBudgetEnforcement:
    """Content is truncated when it exceeds tier budget."""

    @pytest.mark.asyncio
    async def test_content_truncated_when_over_budget(
        self, small_assembler: AnalysisContextAssembler
    ) -> None:
        """With 1000 budget, content tier gets 500 tokens."""
        long_content = _make_long_text(800)

        result = await small_assembler.assemble(content=long_content)

        # Content should be truncated to fit ~500 tokens (50% of 1000)
        assert len(result["content"]) < len(long_content)
        assert result["content"] != ""

    @pytest.mark.asyncio
    async def test_content_preserved_when_under_budget(
        self, small_assembler: AnalysisContextAssembler
    ) -> None:
        """Content under 500 tokens (50% of 1000) passes through."""
        short_content = _make_long_text(200)

        result = await small_assembler.assemble(content=short_content)

        assert result["content"] == short_content

    @pytest.mark.asyncio
    async def test_kb_items_truncated_proportionally(
        self, small_assembler: AnalysisContextAssembler
    ) -> None:
        """KB items over budget are truncated proportionally."""
        long_chars = _make_long_text(600)
        long_locs = _make_long_text(600)

        result = await small_assembler.assemble(
            kb_characters=long_chars,
            kb_locations=long_locs,
        )

        # Both should be truncated (combined 1200 tokens, budget ~300)
        assert len(result["kb_characters"]) < len(long_chars)
        assert len(result["kb_locations"]) < len(long_locs)
        # Both should still have content
        assert result["kb_characters"] != ""
        assert result["kb_locations"] != ""


class TestOverflowCascade:
    """Unused tokens from each tier flow to the next."""

    @pytest.mark.asyncio
    async def test_empty_content_overflows_to_kb(self, assembler: AnalysisContextAssembler) -> None:
        """When content is empty, its 3000 tokens flow to KB tier."""
        long_kb = _make_long_text(4500)  # Would overflow 30% (1800) but fits with overflow

        result = await assembler.assemble(
            content="",  # 0 tokens → 3000 overflow
            kb_characters=long_kb,
        )

        # KB should get more room due to overflow
        # Exact fit depends on token counting, but should be significantly preserved
        assert len(result["kb_characters"]) > 1800  # More than original 30% budget

    @pytest.mark.asyncio
    async def test_empty_content_and_kb_overflows_to_preferences(
        self, assembler: AnalysisContextAssembler
    ) -> None:
        """When content and KB are empty, all budget flows to preferences."""
        long_prefs = _make_long_text(5500)

        result = await assembler.assemble(
            content="",
            kb_characters="",
            user_preferences=long_prefs,
        )

        # Preferences should get almost the entire budget
        assert len(result["user_preferences"]) > 1200  # More than original 20%

    @pytest.mark.asyncio
    async def test_partial_content_overflow(
        self, small_assembler: AnalysisContextAssembler
    ) -> None:
        """Content using only part of its budget overflows the remainder."""
        # Content that uses ~100 tokens out of 500 budget → ~400 overflow
        short_content = _make_long_text(100)
        long_kb = _make_long_text(500)

        result = await small_assembler.assemble(
            content=short_content,
            kb_characters=long_kb,
        )

        # Content preserved exactly
        assert result["content"] == short_content
        # KB gets its 300 budget + ~400 overflow = ~700 tokens
        assert result["kb_characters"] != ""


class TestProportionalDistribution:
    """Budget distributed proportionally among non-empty items."""

    @pytest.mark.asyncio
    async def test_single_item_gets_full_tier_budget(
        self, assembler: AnalysisContextAssembler
    ) -> None:
        """When only one KB item is non-empty, it gets the full KB budget."""
        result = await assembler.assemble(
            kb_characters="Alice is a brave warrior who fights for justice.",
        )

        assert result["kb_characters"] != ""
        assert result["kb_locations"] == ""
        assert result["kb_factions"] == ""

    @pytest.mark.asyncio
    async def test_two_items_share_proportionally(
        self, small_assembler: AnalysisContextAssembler
    ) -> None:
        """Two equal-length items get roughly equal budget."""
        text_a = _make_long_text(400)
        text_b = _make_long_text(400)

        result = await small_assembler.assemble(
            kb_characters=text_a,
            kb_locations=text_b,
        )

        # Both should be non-empty and roughly equal length
        len_a = len(result["kb_characters"])
        len_b = len(result["kb_locations"])
        assert len_a > 0
        assert len_b > 0
        # Proportional allocation for equal sizes → roughly equal
        assert abs(len_a - len_b) < max(len_a, len_b) * 0.5

    @pytest.mark.asyncio
    async def test_larger_item_gets_proportionally_more(
        self, small_assembler: AnalysisContextAssembler
    ) -> None:
        """A larger item gets more budget than a smaller one."""
        short_text = "Alice: A warrior."
        long_text = _make_long_text(500)

        result = await small_assembler.assemble(
            kb_characters=long_text,
            kb_locations=short_text,
        )

        # Characters (longer input) should get more output than locations
        assert len(result["kb_characters"]) >= len(result["kb_locations"])


class TestCustomTokenCounter:
    """Injected token counter is used instead of default."""

    @pytest.mark.asyncio
    async def test_custom_counter_is_used(self) -> None:
        """Custom counter with different counting affects truncation."""

        # A counter that counts every character as a token
        def char_counter(text: str) -> int:
            return len(text)

        assembler = AnalysisContextAssembler(
            total_budget=100,  # 100 "tokens" = 100 chars
            token_counter=char_counter,
        )

        # 200 chars → 200 "tokens" → over 50-char content budget
        long_content = "a" * 200

        result = await assembler.assemble(content=long_content)

        # Should be truncated to ~50 chars (50% of 100)
        assert len(result["content"]) <= 60  # Some slack for word boundaries


class TestProtocolCompliance:
    """Assembler satisfies base class and protocol contracts."""

    def test_inherits_from_context_assembler(self) -> None:
        assembler = AnalysisContextAssembler()
        assert isinstance(assembler, ContextAssembler)

    def test_satisfies_analysis_assembler_protocol(self) -> None:
        assembler = AnalysisContextAssembler()
        assert isinstance(assembler, AnalysisAssemblerProtocol)

    def test_total_budget_property(self) -> None:
        assembler = AnalysisContextAssembler(total_budget=8000)
        assert assembler.total_budget == 8000

    def test_get_tier_allocation_returns_correct_structure(self) -> None:
        assembler = AnalysisContextAssembler(total_budget=6000)
        allocation = assembler.get_tier_allocation()

        assert set(allocation.keys()) == {"content", "kb_context", "preferences"}
        for name, budget in allocation.items():
            assert budget.tier_name == name
            assert budget.token_limit > 0

    @pytest.mark.asyncio
    async def test_assemble_accepts_extra_kwargs(self, assembler: AnalysisContextAssembler) -> None:
        """Extra kwargs are absorbed (ABC compatibility)."""
        result = await assembler.assemble(
            content="test",
            unknown_param="ignored",
        )
        assert result["content"] == "test"


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_zero_budget(self) -> None:
        """Zero budget produces empty strings."""
        assembler = AnalysisContextAssembler(total_budget=0)

        result = await assembler.assemble(content="Some text")

        assert result["content"] == ""

    @pytest.mark.asyncio
    async def test_very_small_budget(self) -> None:
        """Very small budget still produces valid output."""
        assembler = AnalysisContextAssembler(total_budget=10)

        result = await assembler.assemble(content="Hello world")

        # 10 tokens, content gets 5 → "Hello" might survive
        assert isinstance(result["content"], str)

    @pytest.mark.asyncio
    async def test_whitespace_only_content(self, assembler: AnalysisContextAssembler) -> None:
        """Whitespace-only content is handled gracefully."""
        result = await assembler.assemble(content="   \n\t  ")

        assert isinstance(result["content"], str)

    @pytest.mark.asyncio
    async def test_single_very_long_item_truncated(
        self, small_assembler: AnalysisContextAssembler
    ) -> None:
        """A single KB item that vastly exceeds budget is truncated."""
        very_long = _make_long_text(5000)

        result = await small_assembler.assemble(kb_characters=very_long)

        assert len(result["kb_characters"]) < len(very_long)
        assert result["kb_characters"] != ""

    @pytest.mark.asyncio
    async def test_all_tiers_simultaneously_over_budget(
        self, small_assembler: AnalysisContextAssembler
    ) -> None:
        """All tiers over budget → each truncated within its allocation."""
        long_text = _make_long_text(800)

        result = await small_assembler.assemble(
            content=long_text,
            kb_characters=long_text,
            kb_locations=long_text,
            user_preferences=long_text,
            avoidance_patterns=long_text,
        )

        # All should be truncated but non-empty
        for key in [
            "content",
            "kb_characters",
            "kb_locations",
            "user_preferences",
            "avoidance_patterns",
        ]:
            assert result[key] != "", f"{key} should not be empty"
            assert len(result[key]) < len(long_text), f"{key} should be truncated"
