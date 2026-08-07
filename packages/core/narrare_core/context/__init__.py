"""Context assembly — proactive KB suggestion and generic context assembly.

Two concerns live here:

1. **Proactive KB suggestion** — three-stage pipeline
   (name matching → embedding search → hybrid scoring) for suggesting
   relevant KB entries based on chapter content.

2. **Generic context assembly** (ADR-025 Decision 3) — abstract base
   class, token budget manager, and shared types that feature-specific
   assemblers (writing, analysis, KB) inherit from.

Core types:
- Suggestion: A ranked KB entry returned to the caller.
- EntityMetadata: Lightweight KB entry info from the API layer.
- TierBudget: Token budget for a single context tier.

Contracts:
- ProactiveContextProtocol: Interface for suggestion services.
- ContextAssemblerProtocol: Interface for generic context assembly.

Base class:
- ContextAssembler: Abstract base for context assembly with budgets.

Budget:
- TokenBudgetManager: Tier-based token allocation and enforcement.

Service:
- ProactiveContextService: Implements the 3-stage suggestion pipeline.

Utility:
- match_entity_names: Standalone name matching function.

See: docs/_shared/CONSTRAINTS.md (RULE-03 contracts first, RULE-07 dependency direction)
See: docs/architecture/decisions/ADR-025-feature-adoption-infrastructure.md (Decision 3)
"""

from __future__ import annotations

from narrare_core.context.assembler import ContextAssembler
from narrare_core.context.budget import TokenBudgetManager
from narrare_core.context.contracts import ContextAssemblerProtocol, ProactiveContextProtocol
from narrare_core.context.name_matching import match_entity_names
from narrare_core.context.proactive_service import ProactiveContextService
from narrare_core.context.series_history import BandSummaryData, SeriesHistoryTier
from narrare_core.context.suggestion import EntityMetadata, Suggestion
from narrare_core.context.types import TierBudget

__all__ = [
    "BandSummaryData",
    "ContextAssembler",
    "ContextAssemblerProtocol",
    "EntityMetadata",
    "ProactiveContextProtocol",
    "ProactiveContextService",
    "SeriesHistoryTier",
    "Suggestion",
    "TierBudget",
    "TokenBudgetManager",
    "match_entity_names",
]
