"""Abstract base class for context assembly with token budgets.

Provides the shared foundation that all feature-specific assemblers
inherit from.  Subclasses define their own tier schemas and context
sources, but share ``TokenBudgetManager`` for budget enforcement.

Per ADR-025 Decision 3 (RULE-03: contract before implementation).

See: docs/architecture/decisions/025-feature-adoption-infrastructure.md
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from narrare_core.context.types import TierBudget


class ContextAssembler[T](ABC):
    """Abstract base for context assembly with token budgets.

    Subclasses define their own tier schemas and context sources,
    but share the ``TokenBudgetManager`` for budget enforcement.

    Usage::

        class MyAssembler(ContextAssembler[dict[str, str]]):
            async def assemble(self, **kwargs) -> dict[str, str]:
                ...

            def get_tier_allocation(self, **kwargs) -> dict[str, TierBudget]:
                ...

    The constructor requires a ``total_budget`` so every assembler
    enforces token limits from day one (no bypass possible).
    """

    def __init__(self, total_budget: int) -> None:
        self._total_budget = total_budget

    @property
    def total_budget(self) -> int:
        """Total token budget for context assembly."""
        return self._total_budget

    @abstractmethod
    async def assemble(self, **kwargs: Any) -> T:
        """Assemble context into the feature-specific return type.

        Subclasses define their own return type via the generic
        parameter ``T``.  Writing features return ``WritingContext``,
        analysis features return ``dict[str, str]``.
        """
        ...

    @abstractmethod
    def get_tier_allocation(self, **kwargs: Any) -> dict[str, TierBudget]:
        """Return tier allocation for this assembler's configuration.

        Returns:
            Mapping of tier name to its budget allocation.
        """
        ...


__all__ = ["ContextAssembler"]
