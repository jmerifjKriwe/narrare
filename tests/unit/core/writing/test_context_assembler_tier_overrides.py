"""Tests for ``WritingContextAssembler`` tier-percentage overrides (FIND-012).

CR-AUFG-08-02 / FIND-012: The Settings UI/API expose configurable
``tier_percentages`` (``TokenLimitOverrides.tier_percentages``).  The
``TokenBudgetManager`` already honours ``tier_overrides`` on its own
constructor, but ``WritingContextAssembler`` previously constructed the
manager WITHOUT forwarding the overrides — so user-configured tier
percentages had zero effect on the emitted tier budgets.

These tests pin the contract that overrides flow through the assembler:

1. Default behaviour (no overrides) is unchanged.
2. Overrides are reflected in ``get_tier_allocation()`` (the public tier
   allocation API).
3. Overrides are reflected end-to-end in ``assemble()`` output (the
   emitted content is budgeted according to the overridden tiers).
4. Partial overrides rescale the non-overridden tiers.
5. The ``WritingPipeline`` uses the injected assembler as-is (it does not
   re-construct or re-wrap it), so overrides configured at factory time
   flow through unchanged.

Note on the override type: it mirrors ``TokenBudgetManager.tier_overrides``
and the backend ``TokenLimitOverrides.tier_percentages`` field
(``dict[str, float]``).  Core stays backend-agnostic — it knows only the
primitive mapping; the backend resolves the limits and passes them in at
factory time (out of scope for core).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.gateway import ModelRegistry
from narrare_core.prompts.composer import PromptComposer
from narrare_core.writing._enums import GenerationMode
from narrare_core.writing.context_assembler import WritingContextAssembler
from narrare_core.writing.context_models import RecentChapter
from narrare_core.writing.draft_processor import DraftProcessor
from narrare_core.writing.models import WritingContext
from narrare_core.writing.requests import GenerationRequest


def _word_counter(text: str) -> int:
    """Deterministic token counter: 1 word == 1 token.

    ``truncate_to_budget`` truncates at word boundaries using a word
    estimate, so a word-counting counter makes budget/truncation
    assertions exact and observable instead of relying on the heuristic
    char/1.3 estimator.
    """
    return len(text.split())


def _recent_chapter(text: str = "A short recent chapter summary.") -> RecentChapter:
    """A minimal recent chapter so ``is_first`` is ``False`` (base percentages)."""
    return RecentChapter(
        chapter_id=uuid4(),
        title="Chapter 1",
        full_text=text,
        summary=text,
        position=1,
    )


class TestWritingContextAssemblerTierOverrides:
    """Overrides injected via constructor must reach the budget manager."""

    # ------------------------------------------------------------------
    # Regression (FIND-012) — this MUST fail before the fix.
    # ------------------------------------------------------------------

    def test_single_tier_override_reflected_in_allocation(self) -> None:
        """REGRESSION (FIND-012): overrides change the emitted tier allocation.

        Before the fix ``WritingContextAssembler`` did not accept
        ``tier_overrides`` at all (TypeError) and would not have forwarded
        them regardless.  This test is the red→green anchor.
        """
        assembler = WritingContextAssembler(
            total_budget=6000,
            tier_overrides={"immediate": 0.50},
        )
        budgets = assembler.get_tier_allocation()

        assert budgets["immediate"].percentage == pytest.approx(0.50)
        assert budgets["immediate"].token_limit == 3000  # 50% of 6000

    # ------------------------------------------------------------------
    # Default behaviour unchanged (no overrides)
    # ------------------------------------------------------------------

    def test_default_no_overrides_uses_default_distribution(self) -> None:
        """No overrides == identical to the original default allocation."""
        assembler = WritingContextAssembler(total_budget=6000)
        budgets = assembler.get_tier_allocation()

        # Base percentages (get_tier_allocation defaults to first_chapter=False):
        # 30/20/25/15/10.
        assert budgets["immediate"].percentage == pytest.approx(0.30)
        assert budgets["recent"].percentage == pytest.approx(0.20)
        assert budgets["kb_referenced"].percentage == pytest.approx(0.25)
        assert budgets["kb_suggested"].percentage == pytest.approx(0.15)
        assert budgets["pinned"].percentage == pytest.approx(0.10)

    def test_default_overrides_none_matches_explicit_none(self) -> None:
        """``tier_overrides=None`` (explicit) == omitting it entirely."""
        default = WritingContextAssembler(total_budget=6000)
        explicit_none = WritingContextAssembler(
            total_budget=6000,
            tier_overrides=None,
        )
        assert default.get_tier_allocation() == explicit_none.get_tier_allocation()

    # ------------------------------------------------------------------
    # Full + partial overrides
    # ------------------------------------------------------------------

    def test_full_tier_overrides_all_reflected(self) -> None:
        """Overriding every tier keeps exact values (sums to 1.0)."""
        overrides = {
            "immediate": 0.25,
            "recent": 0.20,
            "kb_referenced": 0.20,
            "kb_suggested": 0.20,
            "pinned": 0.15,
        }
        assembler = WritingContextAssembler(
            total_budget=10000,
            tier_overrides=overrides,
        )
        budgets = assembler.get_tier_allocation()

        for tier, expected in overrides.items():
            assert budgets[tier].percentage == pytest.approx(expected), tier

        total = sum(b.percentage for b in budgets.values())
        assert total == pytest.approx(1.0)

    def test_partial_override_keeps_others_proportionally_rescaled(self) -> None:
        """Non-overridden tiers retain their *relative* proportions, rescaled.

        Overriding ``immediate`` to 0.50 leaves 0.50 for the other four
        tiers.  Their original proportions (0.20, 0.25, 0.15, 0.10) keep
        the same ratios after rescaling.
        """
        assembler = WritingContextAssembler(
            total_budget=6000,
            tier_overrides={"immediate": 0.50},
        )
        budgets = assembler.get_tier_allocation()

        assert budgets["immediate"].percentage == pytest.approx(0.50)

        remaining = {
            "recent": budgets["recent"].percentage,
            "kb_referenced": budgets["kb_referenced"].percentage,
            "kb_suggested": budgets["kb_suggested"].percentage,
            "pinned": budgets["pinned"].percentage,
        }
        assert sum(remaining.values()) == pytest.approx(0.50)

        # Relative proportions preserved: recent/kb_referenced stays 20/25.
        assert remaining["recent"] / remaining["kb_referenced"] == pytest.approx(0.20 / 0.25)

    def test_overrides_apply_in_first_chapter_mode(self) -> None:
        """Overrides compose with the first-chapter base percentages."""
        assembler = WritingContextAssembler(
            total_budget=6000,
            tier_overrides={"immediate": 0.40},
        )
        budgets = assembler.get_tier_allocation(first_chapter=True)

        assert budgets["immediate"].percentage == pytest.approx(0.40)
        assert budgets["recent"].percentage == pytest.approx(0.0)
        total = sum(b.percentage for b in budgets.values())
        assert total == pytest.approx(1.0)

    def test_invalid_override_value_propagates_valueerror(self) -> None:
        """Invalid overrides raise at construction (delegated to budget manager)."""
        with pytest.raises(ValueError, match=r"must not exceed 1\.0"):
            WritingContextAssembler(
                total_budget=6000,
                tier_overrides={"immediate": 1.5},
            )

    # ------------------------------------------------------------------
    # End-to-end: assemble() output honours overrides
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_assemble_reflects_overrides_in_emitted_content(self) -> None:
        """Overriding ``immediate`` to a larger share preserves more content.

        With total_budget=1000, a word counter, and 350 words of content:
          - default immediate share (0.30) → 300-token limit → truncated
            to ~230 words (truncate_to_budget word estimate)
          - overridden immediate share (0.50) → 500-token limit → intact

        A non-empty recent chapter keeps ``is_first`` False (base pcts).
        """
        content = " ".join(f"word{i}" for i in range(350))  # 350 distinct words

        default_asm = WritingContextAssembler(
            total_budget=1000,
            token_counter=_word_counter,
        )
        override_asm = WritingContextAssembler(
            total_budget=1000,
            token_counter=_word_counter,
            tier_overrides={"immediate": 0.50},
        )

        default_ctx = await default_asm.assemble(
            chapter_content=content,
            recent_chapters=[_recent_chapter()],
        )
        override_ctx = await override_asm.assemble(
            chapter_content=content,
            recent_chapters=[_recent_chapter()],
        )

        default_words = len(default_ctx.chapter_content.split())
        override_words = len(override_ctx.chapter_content.split())

        # The overridden assembler lets strictly more content survive.
        assert override_words > default_words
        # Under the 0.50 share the 350-word content fits intact.
        assert override_words == 350
        # Under the 0.30 share the content is truncated below its full size.
        assert default_words < 350

    @pytest.mark.asyncio
    async def test_assemble_total_budget_tokens_unaffected_by_overrides(self) -> None:
        """Overrides redistribute the *share*, never the total budget."""
        assembler = WritingContextAssembler(
            total_budget=6000,
            tier_overrides={"immediate": 0.50},
        )
        ctx = await assembler.assemble()
        assert ctx.total_budget_tokens == 6000


class TestWritingPipelineForwardsOverrides:
    """The pipeline must use the injected assembler without re-wrapping it.

    FIND-012 root cause lives in the assembler constructor, not the
    pipeline: ``WritingPipeline`` receives its ``context_assembler`` via DI
    and calls ``assemble()`` on that exact instance.  These tests pin that
    contract so the override configured at factory time is guaranteed to
    flow through.
    """

    def test_pipeline_holds_injected_assembler_instance(self) -> None:
        """The pipeline keeps the very instance it was given (no re-wrap)."""
        from narrare_core.writing.pipeline import WritingPipeline

        injected = MagicMock(spec=WritingContextAssembler)

        pipeline = WritingPipeline(
            registry=MagicMock(spec=ModelRegistry),
            composer=MagicMock(spec=PromptComposer),
            context_assembler=injected,
            draft_processor=MagicMock(spec=DraftProcessor),
        )

        assert pipeline._context_assembler is injected

    @pytest.mark.asyncio
    async def test_pipeline_generate_delegates_to_injected_assembler(self) -> None:
        """``generate()`` forwards to the injected assembler's ``assemble()``.

        Uses INTERACTIVE_SESSION mode, which raises ``ValueError`` right
        AFTER the context is assembled — so we can assert the injected
        assembler was awaited without spinning up an LLM call.
        """
        from narrare_core.writing.pipeline import WritingPipeline

        fake_context = MagicMock(spec=WritingContext)
        fake_context.to_metadata.return_value.to_dict.return_value = {
            "total_budget_tokens": 6000,
        }
        injected = MagicMock(spec=WritingContextAssembler)
        injected.assemble = AsyncMock(return_value=fake_context)

        pipeline = WritingPipeline(
            registry=MagicMock(spec=ModelRegistry),
            composer=MagicMock(spec=PromptComposer),
            context_assembler=injected,
            draft_processor=MagicMock(spec=DraftProcessor),
        )

        request = GenerationRequest(
            chapter_id=uuid4(),
            project_id=uuid4(),
            user_id=uuid4(),
            mode=GenerationMode.INTERACTIVE_SESSION,
        )

        chunks: list[object] = []
        with pytest.raises(ValueError, match="WebSocket"):
            async for chunk in pipeline.generate(
                request, config=MagicMock(spec=ResolvedModelConfig)
            ):
                chunks.append(chunk)

        # Context-metadata chunk is yielded before the mode dispatch raises.
        assert len(chunks) == 1
        injected.assemble.assert_awaited_once()
