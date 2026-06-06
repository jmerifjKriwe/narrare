"""Output budget types and resolver for the AI invocation pipeline.

Contains:
- :class:`OutputBudget` — validated token-limit value object.
- :class:`OutputBudgetDecision` — budget with provenance metadata.
- :class:`IntentOutputBudgetResolverImpl` — production resolver that bridges
  intent categories → profile → token limits.

This package replaces the former flat ``budgets.py`` module. All existing
imports (``from narrare_core.ai_invocation.budgets import OutputBudget``)
continue to work unchanged.

See: ADR-038, INFRA-013, CONSTRAINTS.md RULE-04/RULE-06.
"""

from __future__ import annotations

from narrare_core.ai_invocation.budgets._types import (
    OutputBudget,
    OutputBudgetDecision,
)
from narrare_core.ai_invocation.budgets.resolver import (
    IntentOutputBudgetResolverImpl,
)

__all__ = [
    "IntentOutputBudgetResolverImpl",
    "OutputBudget",
    "OutputBudgetDecision",
]
