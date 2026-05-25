"""Context assembly — proactive KB context suggestion pipeline.

Suggests relevant KB entries based on chapter content using a three-stage
pipeline: name matching -> embedding search -> hybrid scoring.

Core types:
- Suggestion: A ranked KB entry returned to the caller.
- EntityMetadata: Lightweight KB entry info from the API layer.

Contracts:
- ProactiveContextProtocol: Interface for suggestion services.

Service:
- ProactiveContextService: Implements the 3-stage pipeline.

Utility:
- match_entity_names: Standalone name matching function.

See: docs/_shared/CONSTRAINTS.md (RULE-03 contracts first, RULE-07 dependency direction)
"""

from __future__ import annotations

from narrare_core.context.contracts import ProactiveContextProtocol
from narrare_core.context.name_matching import match_entity_names
from narrare_core.context.proactive_service import ProactiveContextService
from narrare_core.context.suggestion import EntityMetadata, Suggestion

__all__ = [
    "EntityMetadata",
    "ProactiveContextProtocol",
    "ProactiveContextService",
    "Suggestion",
    "match_entity_names",
]
