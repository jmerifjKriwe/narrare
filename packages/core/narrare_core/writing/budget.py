"""Backward-compatible re-exports from core/context/.

TokenBudgetManager and TierBudget were moved to ``core/context/`` per
ADR-025 Decision 3.  This module re-exports them so existing imports
continue to work without changes.

See: docs/architecture/decisions/025-feature-adoption-infrastructure.md
"""

from __future__ import annotations

from narrare_core.context.budget import TokenBudgetManager
from narrare_core.context.types import TierBudget
from narrare_core.writing._token_utils import (
    cap_to_budget as cap_to_budget,
)

__all__ = ["TierBudget", "TokenBudgetManager", "cap_to_budget"]
