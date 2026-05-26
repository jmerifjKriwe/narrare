"""KB improve service contract and response schemas.

Contracts are written before implementation (RULE-03).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from uuid import UUID


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class ImproveSuggestionResponse(BaseModel):
    """A single improvement suggestion returned to the frontend."""

    type: str  # "add_field", "connect", "expand", "reorganize"
    target: str
    description: str
    proposed_content: str | None = None
    related_entity_id: str | None = None
    related_entity_name: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str | None = None
    suggestion_id: int  # Index for the frontend to reference when applying


class KBImproveAnalysisResponse(BaseModel):
    """Response from improve analysis."""

    suggestions: list[ImproveSuggestionResponse]
    overall_assessment: str
    completeness_score: float = Field(ge=0.0, le=1.0)


class KBImproveApplyRequest(BaseModel):
    """Request to apply selected improvement suggestions."""

    suggestion_ids: list[int]  # Indices from the analysis response


class KBImproveApplyResponse(BaseModel):
    """Response after applying improvements."""

    success: bool
    entry_id: str
    applied_count: int
    message: str


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class KBImproveProtocol(Protocol):
    """Protocol for KB improve service.

    Provides two operations:
    - analyze: Analyze an existing entry and return improvement suggestions
    - apply: Apply selected suggestions to the entry
    """

    async def analyze(
        self,
        *,
        novel_id: UUID,
        entry_id: UUID,
    ) -> KBImproveAnalysisResponse: ...

    async def apply(
        self,
        *,
        novel_id: UUID,
        entry_id: UUID,
        suggestion_ids: list[int],
    ) -> KBImproveApplyResponse: ...
