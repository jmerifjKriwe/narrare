"""Token budget management for context assembly tiers.

Implements the 5-tier allocation system with overflow redistribution.
Pinned tier always receives its full budget regardless of constraints.

Moved from ``writing/budget.py`` per ADR-025 Decision 3.

Tier allocation (default 32,000-token budget, ADR-082 Decision 2):
    immediate:     30%  — current chapter content + frontmatter + outline
    recent:        20%  — recent chapter summaries or full text
    kb_referenced: 25%  — KB entities referenced in frontmatter
    kb_suggested:  15%  — KB entities via similarity/frequency ranking
    pinned:        10%  — user-pinned KB entities (bypass limits)

When ``first_chapter=True``, the recent tier budget (20%) is
redistributed to KB tiers since there is no history.

When ``mode="extend"`` or ``mode="extend_chapter"``, the allocation
shifts to prioritise immediate context (50/15/20/10/5) because the
pre-text + marker + post-text is critical for seamless continuation.

When ``mode="rewrite"`` or ``mode="rewrite_selection"``, the allocation
balances selection context with KB entity emphasis (40/15/25/10/10)
because the selection and its surrounding context need strong
representation while KB entities (especially character voice profiles)
are critical for mode-specific rewrites.

Configuration overrides
-----------------------
The ``tier_overrides`` parameter on ``__init__`` allows callers to
adjust individual tier percentages at runtime.  Non-overridden tiers
keep their default proportions, rescaled so the total sums to 1.0::

    manager = TokenBudgetManager(
        total_budget=8000,
        tier_overrides={"immediate": 0.40},
    )
    budgets = manager.allocate()
    # immediate → 40%, recent/KB/pinned → defaults (rescaled)
"""

from __future__ import annotations

from typing import ClassVar

from narrare_core.context.types import TierBudget

# ---------------------------------------------------------------------------
# ADR-082 cascade constants — single source for every input-context budget
# default (backend defaults import these; no literal may exist twice).
# ---------------------------------------------------------------------------

#: Default total input-context budget for writing **and** analysis
#: (ADR-082 Decisions 2/5). Ceiling, not a consumption mandate — tiers
#: fill by content availability (design doc D6).
DEFAULT_TOTAL_BUDGET: int = 32_000

#: Default series-history block ceiling **within** the total (ADR-082
#: Decisions 1/3 — guarded carve-out, not additive). Sits exactly at the
#: 50% guard boundary (16k = 50% of 32k).
DEFAULT_SERIES_HISTORY_BUDGET: int = 16_000

#: Fixed reserve component (ADR-082 Decision 4): auto-injected meta +
#: universal capabilities (≈750 tok), feature system prompt (≈900 tok),
#: unbudgeted pass-through variables (≈1,350 tok) — headroom-rounded.
RESERVE_FIXED: int = 4_000

#: Maximum share of the effective total the series-history block may
#: consume (ADR-082 Axis 3 Option C): structurally prevents the
#: degenerate small-window carve-out (both sides always ≥ half).
SERIES_HISTORY_MAX_SHARE: float = 0.5


class TokenBudgetManager:
    """Manages token budgets across all 5 context tiers.

    Usage::

        manager = TokenBudgetManager(total_budget=8000)
        budgets = manager.allocate(first_chapter=False)
        immediate_limit = budgets["immediate"].token_limit
    """

    DEFAULT_TOTAL_BUDGET: int = DEFAULT_TOTAL_BUDGET

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

    _EXTEND_PERCENTAGES: ClassVar[dict[str, float]] = {
        "immediate": 0.50,
        "recent": 0.15,
        "kb_referenced": 0.20,
        "kb_suggested": 0.10,
        "pinned": 0.05,
    }

    _REWRITE_PERCENTAGES: ClassVar[dict[str, float]] = {
        "immediate": 0.40,
        "recent": 0.15,
        "kb_referenced": 0.25,
        "kb_suggested": 0.10,
        "pinned": 0.10,
    }

    def __init__(
        self,
        total_budget: int = DEFAULT_TOTAL_BUDGET,
        tier_overrides: dict[str, float] | None = None,
    ) -> None:
        """Initialise the budget manager.

        Args:
            total_budget:
                Total token budget across all tiers.
            tier_overrides:
                Optional per-tier percentage overrides.  Non-overridden
                tiers keep their default proportions, rescaled so the
                sum equals 1.0.
        """
        self._total_budget = total_budget
        self._tier_overrides = tier_overrides
        if tier_overrides is not None:
            self._validate_overrides(tier_overrides)

    @property
    def total_budget(self) -> int:
        """Total token budget across all tiers."""
        return self._total_budget

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_overrides(overrides: dict[str, float]) -> None:
        """Validate individual override values."""
        for tier, val in overrides.items():
            if val > 1.0:
                raise ValueError(f"Override for '{tier}' is {val}, must not exceed 1.0")
            if val < 0.0:
                raise ValueError(f"Override for '{tier}' is {val}, must not be negative")

    @staticmethod
    def _validate_percentages(pcts: dict[str, float]) -> None:
        """Validate that percentages sum to ~1.0 with 0.01 tolerance."""
        total = sum(pcts.values())
        if not (0.99 <= total <= 1.01):
            raise ValueError(f"Percentages sum to {total}, expected ~1.0 (within 0.01 tolerance)")
        for tier, val in pcts.items():
            if val > 1.0:
                raise ValueError(f"Percentage for '{tier}' is {val}, must not exceed 1.0")

    def _compute_percentages(self, base: dict[str, float]) -> dict[str, float]:
        """Merge *tier_overrides* with *base* and normalise to sum 1.0.

        1. Start with base percentages.
        2. Apply any user overrides — overridden tiers keep their value
           exactly.
        3. Non-overridden tiers are rescaled proportionally so the total
           equals 1.0.
        """
        if not self._tier_overrides:
            return base

        result: dict[str, float] = {}
        override_sum = 0.0
        non_overridden: dict[str, float] = {}

        for tier in self.TIER_ORDER:
            if tier in self._tier_overrides:
                val = self._tier_overrides[tier]
                result[tier] = val
                override_sum += val
            else:
                non_overridden[tier] = base[tier]

        non_overridden_sum = sum(non_overridden.values())
        remaining = 1.0 - override_sum

        if remaining < 0:
            # Overrides alone exceed 100% — scale everything down.
            scale = 1.0 / override_sum
            for tier in result:
                result[tier] *= scale
        elif non_overridden_sum > 0 and remaining >= 0:
            # Scale non-overridden tiers to fill the remaining budget.
            scale = remaining / non_overridden_sum
            for tier, val in non_overridden.items():
                result[tier] = val * scale

        return result

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def allocate(
        self,
        *,
        first_chapter: bool = False,
        mode: str | None = None,
        wiki_optimized: bool = False,
    ) -> dict[str, TierBudget]:
        """Calculate token limits for each tier.

        Parameters
        ----------
        first_chapter:
            When ``True`` and *mode* is not extend or rewrite, the
            *recent* tier receives 0 tokens and the KB tiers get the
            redistributed budget.
        mode:
            Generation mode string.  When ``"extend"`` or
            ``"extend_chapter"``, the extend-specific percentages are
            used (50/15/20/10/5) regardless of *first_chapter*.  When
            ``"rewrite"`` or ``"rewrite_selection"``, the
            rewrite-specific percentages are used (40/15/25/10/10).
            Overflow handles the no-recent-chapters case naturally.
        wiki_optimized:
            When ``True``, shifts 5 percentage points from
            ``kb_referenced`` to ``immediate``.  Wiki summaries are
            ~40 tokens/entity vs ~200 for raw content, so the
            ``kb_referenced`` tier needs less budget and the
            immediate chapter content gets more room.  Applied
            on top of *mode* and *first_chapter* adjustments.

        Returns
        -------
        dict[str, TierBudget]
            Mapping of tier name to its budget allocation.
        """
        if mode in ("extend", "extend_chapter"):
            base = self._EXTEND_PERCENTAGES
        elif mode in ("rewrite", "rewrite_selection"):
            base = self._REWRITE_PERCENTAGES
        elif first_chapter:
            base = self._FIRST_CHAPTER_PERCENTAGES
        else:
            base = self._BASE_PERCENTAGES
        pcts = self._compute_percentages(base)
        if wiki_optimized:
            pcts = dict(pcts)
            pcts["immediate"] = round(pcts["immediate"] + 0.05, 4)
            pcts["kb_referenced"] = round(pcts["kb_referenced"] - 0.05, 4)
        self._validate_percentages(pcts)
        return {
            name: TierBudget(
                tier_name=name,
                percentage=pct,
                token_limit=round(self._total_budget * pct),
                pinned_bypass=(name == "pinned"),
            )
            for name, pct in pcts.items()
        }


__all__ = ["TokenBudgetManager"]
