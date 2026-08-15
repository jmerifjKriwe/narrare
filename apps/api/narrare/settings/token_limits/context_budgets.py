"""Cascade → effective context budgets adapter (ADR-082 Decision 3).

Single API-side seam turning resolved ``TokenLimitOverrides`` plus the
routed model config into model-boundary-capped
:class:`~narrare_core.context.contracts.EffectiveContextBudgets`.

Pure delegation — all arithmetic lives in Core
(``DefaultContextBudgetResolver``); this adapter exists so the six
production wiring points (five writing deps factories + the beta-reader
factory) share one resolution call instead of each constructing the
resolver (RULE-04). Window source: ``get_model_limits`` (models.dev,
24 h local cache, typed offline statuses — ADR-082 finding F1).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare_core.context.budget_resolver import DefaultContextBudgetResolver

if TYPE_CHECKING:
    from narrare.settings.token_limits.contracts import TokenLimitOverrides
    from narrare_core.context.contracts import ContextBudgetResolver, EffectiveContextBudgets
    from narrare_core.llm.model_config import ResolvedModelConfig

__all__ = ["resolve_context_budgets"]


def resolve_context_budgets(
    *,
    limits: TokenLimitOverrides,
    config: ResolvedModelConfig,
    series_in_scope: bool,
    resolver: ContextBudgetResolver | None = None,
) -> EffectiveContextBudgets:
    """Resolve configured context budgets against the model boundary.

    Args:
        limits: Fully resolved cascade values (TokenLimitsService).
        config: Routed model config — provider/model identify the window.
        series_in_scope: Whether this request assembles the series-history
            block (series novel on the writing path; always ``False`` for
            analysis and for paths that never inject ``{{series_history}}``
            — ADR-082 Decision 6 asymmetry).
        resolver: Optional resolver override (tests inject a fake; the
            default constructs ``DefaultContextBudgetResolver`` with the
            real models.dev-backed window provider).

    Returns:
        Frozen effective budgets (capped totals, series-history ceiling,
        tier base, applied reserve, provenance source tag).
    """
    effective_resolver = resolver or DefaultContextBudgetResolver()
    return effective_resolver.resolve(
        configured_total=limits.context_total_budget,
        configured_series_history=limits.series_history_budget,
        effective_output_limit=limits.effective_output_limit,
        series_in_scope=series_in_scope,
        provider_name=config.provider_name,
        model_id=config.model_id,
    )
