"""Model-boundary capping for input-context token budgets (ADR-082).

Pure resolution arithmetic — no I/O. Mirrors ``DefaultRunLimitResolver``
(``llm/run_limits.py``): the window provider callable is injected
(default ``get_model_limits``, models.dev-backed with local cache), so
unit tests never touch the cache or network (RULE-07).

Arithmetic (ADR-082 Decisions 3/4):

    reserve         = min(RESERVE_FIXED + effective_output_limit, window // 4)
    effective_total = min(configured_total, window - reserve)    if window known
                    = configured_total                            if unknown
    series_history  = min(configured_sh, floor(SERIES_HISTORY_MAX_SHARE * total))
                      -- in-scope only; 0 for standalone requests
    tier_base       = total - series_history

The resolver only ever caps **down** (min() principle, design doc D5);
the ``window // 4`` guard makes ``window - reserve`` structurally
positive (reserve ≤ window/4 < window).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.context.budget import RESERVE_FIXED, SERIES_HISTORY_MAX_SHARE
from narrare_core.context.contracts import EffectiveContextBudgets
from narrare_core.llm.cost_rates import get_model_limits

if TYPE_CHECKING:
    from collections.abc import Callable

    from narrare_core.llm.cost_rates import ModelLimits

logger = structlog.get_logger(__name__)

__all__ = ["DefaultContextBudgetResolver"]


class DefaultContextBudgetResolver:
    """Default implementation of the ADR-082 ContextBudgetResolver contract."""

    def __init__(
        self,
        *,
        model_limits_provider: Callable[[str, str], ModelLimits | None] = get_model_limits,
    ) -> None:
        self._model_limits_provider = model_limits_provider

    def resolve(
        self,
        *,
        configured_total: int,
        configured_series_history: int,
        effective_output_limit: int,
        series_in_scope: bool,
        provider_name: str,
        model_id: str,
    ) -> EffectiveContextBudgets:
        """Resolve configured context budgets against the model boundary."""
        provider_limits = self._model_limits_provider(provider_name, model_id)
        window = provider_limits.context if provider_limits is not None else None

        if window is None:
            # RULE-11: unknown window (unknown model / offline no cache) →
            # no capping, proceed with configured values, tag provenance
            # (mirrors ``provider_max_unknown`` in run_limits.py).
            logger.warning(
                "context_budget_window_unknown",
                provider=provider_name,
                model=model_id,
            )
            series_history = configured_series_history if series_in_scope else 0
            return EffectiveContextBudgets(
                context_total=configured_total,
                series_history=series_history,
                writing_tier_base=configured_total - series_history,
                reserve_tokens=None,
                context_window=None,
                source="cascade:window_unknown",
            )

        reserve = min(RESERVE_FIXED + effective_output_limit, window // 4)
        capped_total = window - reserve
        if configured_total <= capped_total:
            total = configured_total
            source = "cascade:uncapped"
        else:
            total = capped_total
            source = "cascade:capped_to_window"

        series_history = 0
        if series_in_scope:
            series_history = min(
                configured_series_history,
                int(SERIES_HISTORY_MAX_SHARE * total),
            )

        return EffectiveContextBudgets(
            context_total=total,
            series_history=series_history,
            writing_tier_base=total - series_history,
            reserve_tokens=reserve,
            context_window=window,
            source=source,
        )
