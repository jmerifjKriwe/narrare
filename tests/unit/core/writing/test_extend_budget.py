"""Tests for extend-mode budget allocation — tasks 4.1 & 4.3.

Covers:
1. Default budget allocation matches existing (30/20/25/15/10)
2. Extend mode budget allocation is shifted (50/15/20/10/5)
3. "extend_chapter" string also activates extend allocation
4. Extend mode ignores first_chapter flag
5. Extend percentages sum to 1.0
6. WritingContextAssembler passes mode to budget manager
7. Assembler produces correct WritingContext with extend mode
8. existing_content flow verified (pre-text + marker + post-text)
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from narrare_core.writing.budget import TokenBudgetManager
from narrare_core.writing.context_assembler import WritingContextAssembler
from narrare_core.writing.context_models import KBEntity, RecentChapter
from narrare_core.writing.models import WritingContext

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _entity(
    entity_id: str = "ent-1",
    entity_type: str = "character",
    name: str = "Alice",
    content: str = "A brave warrior.",
) -> KBEntity:
    """Build a KBEntity with sensible defaults."""
    return KBEntity(
        entity_id=entity_id,
        entity_type=entity_type,
        name=name,
        content=content,
        similarity_score=0.5,
        frequency_score=0.5,
        recency_score=0.5,
    )


def _chapter(
    title: str = "Chapter 1",
    full_text: str = "Once upon a time there was a brave warrior.",
    summary: str = "A warrior's introduction.",
    position: int = 1,
) -> RecentChapter:
    """Build a RecentChapter."""
    return RecentChapter(
        chapter_id=uuid4(),
        title=title,
        full_text=full_text,
        summary=summary,
        position=position,
    )


# ---------------------------------------------------------------------------
# Task 4.1: Mode-aware budget allocation (TokenBudgetManager)
# ---------------------------------------------------------------------------


class TestDefaultBudgetAllocation:
    """Default allocation (no mode) matches existing 30/20/25/15/10."""

    def test_immediate_30_pct(self) -> None:
        mgr = TokenBudgetManager(6000)
        budgets = mgr.allocate()
        assert budgets["immediate"].percentage == pytest.approx(0.30)
        assert budgets["immediate"].token_limit == 1800

    def test_recent_20_pct(self) -> None:
        mgr = TokenBudgetManager(6000)
        budgets = mgr.allocate()
        assert budgets["recent"].percentage == pytest.approx(0.20)
        assert budgets["recent"].token_limit == 1200

    def test_kb_referenced_25_pct(self) -> None:
        mgr = TokenBudgetManager(6000)
        budgets = mgr.allocate()
        assert budgets["kb_referenced"].percentage == pytest.approx(0.25)
        assert budgets["kb_referenced"].token_limit == 1500

    def test_kb_suggested_15_pct(self) -> None:
        mgr = TokenBudgetManager(6000)
        budgets = mgr.allocate()
        assert budgets["kb_suggested"].percentage == pytest.approx(0.15)
        assert budgets["kb_suggested"].token_limit == 900

    def test_pinned_10_pct(self) -> None:
        mgr = TokenBudgetManager(6000)
        budgets = mgr.allocate()
        assert budgets["pinned"].percentage == pytest.approx(0.10)
        assert budgets["pinned"].token_limit == 600

    def test_percentages_sum_to_one(self) -> None:
        mgr = TokenBudgetManager(6000)
        budgets = mgr.allocate()
        total_pct = sum(b.percentage for b in budgets.values())
        assert total_pct == pytest.approx(1.0)


class TestExtendBudgetAllocation:
    """Extend mode shifts to 50/15/20/10/5."""

    def test_immediate_50_pct(self) -> None:
        mgr = TokenBudgetManager(6000)
        budgets = mgr.allocate(mode="extend")
        assert budgets["immediate"].percentage == pytest.approx(0.50)
        assert budgets["immediate"].token_limit == 3000

    def test_recent_15_pct(self) -> None:
        mgr = TokenBudgetManager(6000)
        budgets = mgr.allocate(mode="extend")
        assert budgets["recent"].percentage == pytest.approx(0.15)
        assert budgets["recent"].token_limit == 900

    def test_kb_referenced_20_pct(self) -> None:
        mgr = TokenBudgetManager(6000)
        budgets = mgr.allocate(mode="extend")
        assert budgets["kb_referenced"].percentage == pytest.approx(0.20)
        assert budgets["kb_referenced"].token_limit == 1200

    def test_kb_suggested_10_pct(self) -> None:
        mgr = TokenBudgetManager(6000)
        budgets = mgr.allocate(mode="extend")
        assert budgets["kb_suggested"].percentage == pytest.approx(0.10)
        assert budgets["kb_suggested"].token_limit == 600

    def test_pinned_5_pct(self) -> None:
        mgr = TokenBudgetManager(6000)
        budgets = mgr.allocate(mode="extend")
        assert budgets["pinned"].percentage == pytest.approx(0.05)
        assert budgets["pinned"].token_limit == 300

    def test_percentages_sum_to_one(self) -> None:
        mgr = TokenBudgetManager(6000)
        budgets = mgr.allocate(mode="extend")
        total_pct = sum(b.percentage for b in budgets.values())
        assert total_pct == pytest.approx(1.0)

    def test_extend_chapter_string_also_activates(self) -> None:
        """``mode="extend_chapter"`` uses the same extend percentages."""
        mgr = TokenBudgetManager(6000)
        budgets = mgr.allocate(mode="extend_chapter")
        assert budgets["immediate"].percentage == pytest.approx(0.50)
        assert budgets["pinned"].percentage == pytest.approx(0.05)

    def test_extend_mode_ignores_first_chapter_flag(self) -> None:
        """Extend mode uses extend percentages regardless of first_chapter."""
        mgr = TokenBudgetManager(6000)
        budgets = mgr.allocate(mode="extend", first_chapter=True)
        # Still uses extend percentages, not first_chapter percentages
        assert budgets["immediate"].percentage == pytest.approx(0.50)
        assert budgets["recent"].percentage == pytest.approx(0.15)

    def test_tier_order_preserved(self) -> None:
        mgr = TokenBudgetManager(6000)
        budgets = mgr.allocate(mode="extend")
        assert list(budgets.keys()) == list(TokenBudgetManager.TIER_ORDER)

    def test_pinned_bypass_still_true(self) -> None:
        mgr = TokenBudgetManager(6000)
        budgets = mgr.allocate(mode="extend")
        assert budgets["pinned"].pinned_bypass is True


class TestExtendWithOverrides:
    """Extend mode + tier_overrides compose correctly."""

    def test_extend_with_override(self) -> None:
        """tier_overrides can further adjust extend percentages."""
        mgr = TokenBudgetManager(6000, tier_overrides={"immediate": 0.60})
        budgets = mgr.allocate(mode="extend")
        assert budgets["immediate"].percentage == pytest.approx(0.60)
        total_pct = sum(b.percentage for b in budgets.values())
        assert total_pct == pytest.approx(1.0)

    def test_extend_with_custom_budget(self) -> None:
        mgr = TokenBudgetManager(10_000)
        budgets = mgr.allocate(mode="extend")
        assert budgets["immediate"].token_limit == 5000  # 50%
        assert budgets["recent"].token_limit == 1500  # 15%


# ---------------------------------------------------------------------------
# Task 4.3: WritingContextAssembler integration with extend mode
# ---------------------------------------------------------------------------


class TestAssemblerExtendMode:
    """Assembler produces correct WritingContext with extend mode."""

    @pytest.mark.asyncio
    async def test_extend_mode_assembles_correctly(self) -> None:
        assembler = WritingContextAssembler(total_budget=6000)
        ctx = await assembler.assemble(
            chapter_content="The chapter text begins.",
            mode="extend",
        )
        assert isinstance(ctx, WritingContext)
        assert ctx.chapter_content == "The chapter text begins."

    @pytest.mark.asyncio
    async def test_default_mode_unchanged_backward_compat(self) -> None:
        """Without mode parameter, behaviour is identical to before."""
        assembler = WritingContextAssembler(total_budget=6000)
        ctx_no_mode = await assembler.assemble(
            chapter_content="Some content.",
        )
        ctx_none_mode = await assembler.assemble(
            chapter_content="Some content.",
            mode=None,
        )
        assert ctx_no_mode.chapter_content == ctx_none_mode.chapter_content

    @pytest.mark.asyncio
    async def test_extend_mode_gives_more_immediate_budget(self) -> None:
        """Extend mode allocates more tokens to immediate tier.

        With a large chapter content, extend mode should preserve more
        of it than default mode because the immediate tier gets 50%
        instead of 30%.
        """
        # Create content large enough to exceed 30% budget but fit in 50%
        # 6000 tokens * 30% = 1800 tokens, 6000 * 50% = 3000 tokens
        # ~1.3 tokens per word, so 1800/1.3 ~ 1385 words at 30%
        # We need content between 1385 and ~2300 words to see the difference
        large_content = " ".join(["word"] * 1500)  # ~1950 tokens
        assembler = WritingContextAssembler(total_budget=6000)

        # Default mode — immediate tier is 1800 tokens, content will be truncated
        ctx_default = await assembler.assemble(chapter_content=large_content)

        # Extend mode — immediate tier is 3000 tokens, content fits
        ctx_extend = await assembler.assemble(chapter_content=large_content, mode="extend")

        # Extend mode preserves more of the content
        assert len(ctx_extend.chapter_content) > len(ctx_default.chapter_content)

    @pytest.mark.asyncio
    async def test_extend_mode_with_recent_chapters(self) -> None:
        """Extend mode with recent chapters: 15% recent still works."""
        assembler = WritingContextAssembler(total_budget=6000)
        chapters = [
            _chapter("Ch 1", "Short text one.", "Summary one.", 1),
        ]
        ctx = await assembler.assemble(
            chapter_content="New content.",
            recent_chapters=chapters,
            mode="extend",
        )
        assert ctx.recent_chapters != ""
        assert "Short text one." in ctx.recent_chapters
        assert ctx.recent_chapter_count == 1

    @pytest.mark.asyncio
    async def test_extend_mode_with_kb_entities(self) -> None:
        """Extend mode with KB entities: 20% referenced, 10% suggested."""
        assembler = WritingContextAssembler(total_budget=6000)
        entities = [
            _entity("char-1", "character", "Alice", "A warrior."),
            _entity("char-2", "character", "Bob", "A mage."),
            _entity("loc-1", "location", "Castle", "An ancient fortress."),
            _entity("fac-1", "faction", "Rebels", "Freedom fighters."),
        ]
        ctx = await assembler.assemble(
            chapter_content="Content.",
            kb_entities=entities,
            mode="extend",
        )
        assert isinstance(ctx, WritingContext)
        # At least some entities should be present
        assert ctx.kb_characters != "" or ctx.kb_suggested != ""

    @pytest.mark.asyncio
    async def test_extend_first_chapter_overflows_correctly(self) -> None:
        """Extend + first chapter: recent tier overflows to later tiers."""
        assembler = WritingContextAssembler(total_budget=6000)
        entities = [
            _entity(f"ent-{i}", "character", f"Char {i}", f"Description {i}.") for i in range(10)
        ]
        # No recent chapters → is_first_chapter=True, recent overflows
        ctx = await assembler.assemble(
            chapter_content="Opening.",
            kb_entities=entities,
            mode="extend",
        )
        assert ctx.is_first_chapter is True
        assert ctx.recent_chapters == ""
        # Some KB content should be present (overflow from recent tier)
        assert ctx.kb_characters != "" or ctx.kb_suggested != ""


# ---------------------------------------------------------------------------
# Task 4.2: existing_content flow verification
# ---------------------------------------------------------------------------


class TestExistingContentFlow:
    """Verify that pre-text + marker + post-text flows through correctly.

    The extend service builds:
        chapter_content = text_before + "\\n[CONTINUE FROM HERE]\\n" + text_after

    The assembler passes this through tier 1 processing and sets
    WritingContext.chapter_content. The pipeline_extend module then
    uses context.chapter_content as PromptContext.existing_content.
    """

    @pytest.mark.asyncio
    async def test_pre_text_marker_post_text_preserved(self) -> None:
        """Assembler preserves pre-text + marker + post-text as chapter_content."""
        combined = "Alice walked through the forest.\n[CONTINUE FROM HERE]\nThe sun was setting."
        assembler = WritingContextAssembler(total_budget=6000)
        ctx = await assembler.assemble(
            chapter_content=combined,
            mode="extend",
        )
        assert ctx.chapter_content == combined
        assert "[CONTINUE FROM HERE]" in ctx.chapter_content

    @pytest.mark.asyncio
    async def test_pre_text_only_no_post_text(self) -> None:
        """When text_after is empty, marker is still present."""
        combined = "Alice walked through the forest.\n[CONTINUE FROM HERE]\n"
        assembler = WritingContextAssembler(total_budget=6000)
        ctx = await assembler.assemble(
            chapter_content=combined,
            mode="extend",
        )
        assert ctx.chapter_content == combined

    @pytest.mark.asyncio
    async def test_large_pre_text_preserved_with_extend_budget(self) -> None:
        """Large pre-text is NOT truncated with extend's 50% immediate budget."""
        # ~1500 tokens worth of text — exceeds 30% (1800 tokens) but well within 50% (3000 tokens)
        pre_text = " ".join(["The story continues with vivid detail."] * 100)
        combined = f"{pre_text}\n[CONTINUE FROM HERE]\n"
        assembler = WritingContextAssembler(total_budget=6000)

        ctx = await assembler.assemble(
            chapter_content=combined,
            mode="extend",
        )
        assert "[CONTINUE FROM HERE]" in ctx.chapter_content
        assert ctx.chapter_content.startswith("The story continues")
