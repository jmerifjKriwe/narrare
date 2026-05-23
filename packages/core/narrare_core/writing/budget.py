"""Token budget management for writing context tiers.

Implements the 5-tier allocation system with overflow redistribution.
Pinned tier always receives its full budget regardless of constraints.

Tier allocation (default 6000-token budget):
    immediate:     30%  — current chapter content + frontmatter + outline
    recent:        20%  — recent chapter summaries or full text
    kb_referenced: 25%  — KB entities referenced in frontmatter
    kb_suggested:  15%  — KB entities via similarity/frequency ranking
    pinned:        10%  — user-pinned KB entities (bypass limits)

When ``first_chapter=True``, the recent tier budget (20%) is
redistributed to KB tiers since there is no history.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass(frozen=True, slots=True)
class TierBudget:
    """Token budget for a single context tier."""

    tier_name: str
    percentage: float
    token_limit: int
    pinned_bypass: bool = False


class TokenBudgetManager:
    """Manages token budgets across all 5 context tiers.

    Usage::

        manager = TokenBudgetManager(total_budget=8000)
        budgets = manager.allocate(first_chapter=False)
        immediate_limit = budgets["immediate"].token_limit
    """

    DEFAULT_TOTAL_BUDGET: int = 6000

    TIER_ORDER: ClassVar[tuple[str, ...]] = (
        "immediate",
        "recent",
        "kb_referenced",
        "kb_suggested",
        "pinned",
    )

    _BASE_PERCENTAGES: ClassVar[dict[str, float]] = {
        "immediate": 0.30,
        "recent": 0.20,
        "kb_referenced": 0.25,
        "kb_suggested": 0.15,
        "pinned": 0.10,
    }

    _FIRST_CHAPTER_PERCENTAGES: ClassVar[dict[str, float]] = {
        "immediate": 0.30,
        "recent": 0.0,
        "kb_referenced": 0.35,
        "kb_suggested": 0.25,
        "pinned": 0.10,
    }

    def __init__(self, total_budget: int = DEFAULT_TOTAL_BUDGET) -> None:
        self._total_budget = total_budget

    @property
    def total_budget(self) -> int:
        """Total token budget across all tiers."""
        return self._total_budget

    def allocate(
        self,
        *,
        first_chapter: bool = False,
    ) -> dict[str, TierBudget]:
        """Calculate token limits for each tier.

        Parameters
        ----------
        first_chapter:
            When ``True``, the *recent* tier receives 0 tokens and
            the KB tiers get the redistributed budget.

        Returns
        -------
        dict[str, TierBudget]
            Mapping of tier name to its budget allocation.
        """
        pcts = self._FIRST_CHAPTER_PERCENTAGES if first_chapter else self._BASE_PERCENTAGES
        return {
            name: TierBudget(
                tier_name=name,
                percentage=pct,
                token_limit=round(self._total_budget * pct),
                pinned_bypass=(name == "pinned"),
            )
            for name, pct in pcts.items()
        }


# ---------------------------------------------------------------------------
# Lightweight token-budget utility
# ---------------------------------------------------------------------------

_APPROX_TOKEN_FACTOR = 1.3
"""Multiplier applied to word count to approximate BPE token length."""


def _default_token_counter(text: str) -> int:
    """Approximate token count: words * 1.3.

    Avoids a tiktoken dependency in core.  Consumers that need an
    accurate count (e.g. the API layer) can inject their own counter
    via the ``token_counter`` parameter of :func:`cap_to_budget`.
    """
    if not text:
        return 0
    return round(len(text.split()) * _APPROX_TOKEN_FACTOR)


def cap_to_budget(
    text: str,
    max_tokens: int,
    token_counter: Callable[[str], int] | None = None,
) -> str:
    """Cap text to a token budget, truncating from the end if needed.

    Lightweight utility for services that need simple token enforcement
    without the full 5-tier allocation system.

    Args:
        text: The text to potentially truncate.
        max_tokens: Maximum allowed tokens.
        token_counter: Optional token counting function.
            Defaults to word-count * 1.3 approximation.

    Returns:
        Original text if within budget, otherwise truncated text.
        Returns empty string if *max_tokens* <= 0.
    """
    if max_tokens <= 0:
        return ""

    count = token_counter or _default_token_counter

    if count(text) <= max_tokens:
        return text

    # Truncate at word boundaries by progressively removing trailing words.
    words = text.split()
    while words and count(" ".join(words)) > max_tokens:
        words.pop()

    return " ".join(words)
