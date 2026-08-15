"""3-tier context assembly for analysis features with token budgets.

Simpler than ``WritingContextAssembler`` — analysis features need
content + KB context + preferences, but no outline/frontmatter or
recent chapters.  Inherits from ``ContextAssembler`` (ADR-025
Decision 3) so all feature-specific assemblers share the same budget
enforcement base.

This is a pure data transformation — no I/O, no DB, no LLM calls.
The API layer provides all data; this class enforces token budgets
and returns prompt variables.

Per CONSTRAINTS.md RULE-02: No prompt building outside ``core/prompts/``.
This module only truncates and returns strings — it does not construct
prompt templates.

See: docs/architecture/decisions/ADR-025-feature-adoption-infrastructure.md
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from narrare_core.analysis.budget import AnalysisBudgetManager
from narrare_core.context.assembler import ContextAssembler
from narrare_core.writing._token_utils import default_token_counter

if TYPE_CHECKING:
    from collections.abc import Callable

    from narrare_core.context.types import TierBudget


class AnalysisContextAssembler(ContextAssembler[dict[str, str]]):
    """3-tier context assembly for analysis features.

    Simpler than ``WritingContextAssembler`` — analysis features need
    content + KB context + preferences, but no outline/frontmatter.

    Tier allocation (default 32,000-token budget, ADR-082 Decision 5):
        content:      50%  — chapter text / content to analyze
        kb_context:   30%  — KB entities (characters, locations, factions, relationships)
        preferences:  20%  — user preferences, avoidance patterns

    Unused tokens from each tier cascade to the next (overflow).

    Usage::

        assembler = AnalysisContextAssembler(total_budget=32_000)
        result = await assembler.assemble(
            content="Chapter text...",
            kb_characters="Alice: A brave warrior\\nBob: A wise mage",
            kb_locations="Castle: An ancient fortress",
        )
        # result = {"content": "...", "kb_characters": "...", ...}
    """

    def __init__(
        self,
        total_budget: int = AnalysisBudgetManager.DEFAULT_TOTAL_BUDGET,
        token_counter: Callable[[str], int] | None = None,
    ) -> None:
        super().__init__(total_budget)
        self._budget_manager = AnalysisBudgetManager(total_budget)
        self._count_tokens = token_counter or default_token_counter

    # ------------------------------------------------------------------
    # ContextAssembler contract
    # ------------------------------------------------------------------

    def get_tier_allocation(self, **kwargs: Any) -> dict[str, TierBudget]:
        """Return tier allocation for this assembler's configuration."""
        return self._budget_manager.allocate()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def assemble(
        self,
        *,
        content: str = "",
        kb_characters: str = "",
        kb_locations: str = "",
        kb_factions: str = "",
        kb_relationships: str = "",
        user_preferences: str = "",
        avoidance_patterns: str = "",
        **_extra: Any,  # absorb unknown kwargs for ABC compatibility
    ) -> dict[str, str]:
        """Assemble analysis context with budget enforcement.

        All data is provided by the caller — no I/O happens here.
        The method is ``async`` to match the protocol but performs
        only synchronous data transformation internally.

        Args:
            content: The text to analyze (chapter content).
            kb_characters: Pre-formatted character descriptions.
            kb_locations: Pre-formatted location descriptions.
            kb_factions: Pre-formatted faction descriptions.
            kb_relationships: Pre-formatted relationship descriptions.
            user_preferences: User preference text.
            avoidance_patterns: User avoidance pattern text.

        Returns:
            Dictionary of prompt variable names to their
            budget-enforced text values.
        """
        budgets = self._budget_manager.allocate()

        # --- Tier 1: Core (50%) — content to analyze ---
        t1_limit = budgets["content"].token_limit
        content_text, overflow = self._enforce_budget(content, t1_limit)

        # --- Tier 2: KB Context (30%) — KB entities ---
        t2_limit = budgets["kb_context"].token_limit + overflow
        kb_items: dict[str, str] = {
            "kb_characters": kb_characters,
            "kb_locations": kb_locations,
            "kb_factions": kb_factions,
            "kb_relationships": kb_relationships,
        }
        kb_result, overflow = self._distribute_budget(kb_items, t2_limit)

        # --- Tier 3: Preferences (20%) — user preferences ---
        t3_limit = budgets["preferences"].token_limit + overflow
        pref_items: dict[str, str] = {
            "user_preferences": user_preferences,
            "avoidance_patterns": avoidance_patterns,
        }
        pref_result, _ = self._distribute_budget(pref_items, t3_limit)

        return {"content": content_text, **kb_result, **pref_result}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _enforce_budget(self, text: str, limit: int) -> tuple[str, int]:
        """Enforce token budget on text.  Returns (text, overflow)."""
        if not text:
            return "", limit
        tokens = self._count_tokens(text)
        if tokens <= limit:
            return text, limit - tokens
        truncated = self._truncate_to_budget(text, limit)
        return truncated, 0

    def _truncate_to_budget(self, text: str, token_limit: int) -> str:
        """Truncate text to fit within token budget.

        Uses word-level truncation, verified with the actual token
        counter (supports custom counters, not just the default 1.3x
        heuristic).  Returns empty string when ``token_limit <= 0``.
        """
        if not text or token_limit <= 0:
            return ""
        current = self._count_tokens(text)
        if current <= token_limit:
            return text
        words = text.split()
        # Estimate starting point from current-to-target ratio
        if current > 0:
            ratio = token_limit / current
            start = max(1, int(len(words) * ratio))
        else:
            start = len(words)
        # Trim words until within budget
        candidate = " ".join(words[:start])
        while start > 0 and self._count_tokens(candidate) > token_limit:
            start -= 1
            candidate = " ".join(words[:start])
        return candidate

    def _distribute_budget(
        self,
        items: dict[str, str],
        limit: int,
    ) -> tuple[dict[str, str], int]:
        """Distribute token budget proportionally among named items.

        Empty items receive no budget allocation.  Remaining budget
        is distributed proportionally among non-empty items based on
        their current token counts.

        When everything fits within budget, returns items unchanged
        with the overflow.  When truncation is needed, each item gets
        a proportional share of the limit.

        Returns:
            Tuple of (result dict, overflow tokens).
        """
        # Count tokens for each non-empty item
        token_counts: dict[str, int] = {}
        for name, text in items.items():
            if text:
                token_counts[name] = self._count_tokens(text)

        # If all empty, return empty strings with full budget as overflow
        if not token_counts:
            return dict.fromkeys(items, ""), limit

        total_tokens = sum(token_counts.values())

        # If everything fits, return as-is with overflow
        if total_tokens <= limit:
            result = {name: items.get(name, "") for name in items}
            return result, limit - total_tokens

        # Truncate proportionally
        result: dict[str, str] = {}
        used = 0
        for name in items:
            text = items.get(name, "")
            if not text or name not in token_counts:
                result[name] = ""
                continue
            proportion = token_counts[name] / total_tokens
            item_budget = max(1, round(limit * proportion))
            truncated = self._truncate_to_budget(text, item_budget)
            result[name] = truncated
            used += self._count_tokens(truncated)

        return result, max(0, limit - used)


__all__ = ["AnalysisContextAssembler"]
