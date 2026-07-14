"""Context assembly contracts — Protocol definitions.

Defines the interface for proactive context suggestion services and
the generic ContextAssembler protocol (ADR-025 Decision 3).
Contracts are written before implementation (RULE-03).

The **KBContextEnvelope** contract (ADR-050 P1-A) lives in
:mod:`narrare_core.context._kb_envelope` and is re-exported here for
public API stability. Every KB-context render path must satisfy it:
provenance metadata must either be preserved in the rendered text OR
explicitly omitted with a documented rationale (RULE-22).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from narrare_core.context._kb_envelope import (
    KBContextEnvelope,
    KBContextSource,
    OmissionReason,
    ProvenanceField,
    RenderedKBContext,
)
from narrare_core.context._render_options import RenderOptions

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.context.suggestion import EntityMetadata, Suggestion
    from narrare_core.context.types import TierBudget


__all__ = [
    "ContextAssemblerProtocol",
    "KBContextEnvelope",
    "KBContextSource",
    "OmissionReason",
    "ProactiveContextProtocol",
    "ProvenanceField",
    "RenderOptions",
    "RenderedKBContext",
]


@runtime_checkable
class ProactiveContextProtocol(Protocol):
    """Protocol for proactive KB context suggestion.

    Suggests relevant KB entries based on chapter content using
    a three-stage pipeline: name matching -> embedding search -> hybrid scoring.
    """

    async def suggest(
        self,
        chapter_content: str,
        *,
        novel_id: UUID,
        chapter_frontmatter: dict[str, object] | None = None,
        entity_names: list[str] | None = None,
        max_results: int = 20,
        entity_metadata: dict[UUID, EntityMetadata] | None = None,
    ) -> list[Suggestion]:
        """Suggest relevant KB entries for a chapter.

        Args:
            chapter_content: The chapter text to analyze.
            novel_id: Novel UUID to scope the embedding search.
            chapter_frontmatter: Optional frontmatter (POV character, location, etc.).
            entity_names: Known entity names for name matching.
            max_results: Maximum suggestions to return (1-100, default 20).
            entity_metadata: Optional metadata mapping entry_id to name, type,
                usage_count, and last_referenced_at. Used for name-match boost,
                hybrid scoring, and building Suggestion objects.

        Returns:
            Ranked list of Suggestions sorted by relevance_score descending.
        """
        ...


@runtime_checkable
class ContextAssemblerProtocol(Protocol):
    """Protocol for generic context assembly with token budgets.

    Defines the contract that all feature-specific assemblers must
    implement.  Each assembler owns its tier schema and context sources
    but shares ``TokenBudgetManager`` for budget enforcement.

    Per ADR-025 Decision 3: ``core/context/`` owns the abstraction;
    feature modules (``core/writing/``, ``core/analysis/``) own the
    concrete implementations.
    """

    async def assemble(self, **kwargs: Any) -> dict[str, str]:
        """Assemble context into prompt variables dict.

        Returns:
            Flat dictionary of prompt variable names to their text
            values, ready for template substitution.
        """
        ...

    @property
    def total_budget(self) -> int:
        """Total token budget for context assembly."""
        ...

    def get_tier_allocation(self, **kwargs: Any) -> dict[str, TierBudget]:
        """Return tier allocation for this assembler's configuration.

        Returns:
            Mapping of tier name to its budget allocation.
        """
        ...
