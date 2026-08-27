"""Worldbuilding analysis service contract — Protocol definitions.

Contracts are written before implementation (RULE-03).
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from uuid import UUID


# ---------------------------------------------------------------------------
# Enums & Shared Types
# ---------------------------------------------------------------------------


class WorldbuildingSeverity(enum.StrEnum):
    """Severity level for worldbuilding findings."""

    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    INFO = "info"


class GapType(enum.StrEnum):
    """Types of gaps the detector can identify."""

    MISSING_ENTITY = "missing_entity"
    MISSING_FIELD = "missing_field"
    MISSING_CONNECTION = "missing_connection"
    MISSING_BODY = "missing_body"
    UNDEFINED_TYPE = "undefined_type"


class ConsistencyCategory(enum.StrEnum):
    """Categories of consistency issues."""

    GEOGRAPHY = "geography"
    POLITICS = "politics"
    ECONOMICS = "economics"
    SYSTEM_RULES = "system_rules"
    TIMELINE = "timeline"
    CHARACTER = "character"
    # ── KB-004: Entry-internal and relationship asymmetry ──
    ENTRY_INTERNAL = "entry_internal"  # Contradictions within a single entry
    RELATIONSHIP_ASYMMETRY = "relationship_asymmetry"  # Asymmetric reciprocal relationships


# ---------------------------------------------------------------------------
# Finding Types
# ---------------------------------------------------------------------------


class GapFinding(BaseModel):
    """A gap in the project's worldbuilding."""

    entity_id: str | None = None
    entity_name: str | None = None
    entity_type: str | None = None
    gap_type: GapType
    field_key: str | None = None
    description: str
    related_entity_type: str | None = None
    story_relevance: float = Field(ge=0.0, le=1.0, default=0.5)
    severity: WorldbuildingSeverity = WorldbuildingSeverity.MAJOR


class ConnectionSuggestion(BaseModel):
    """A suggested relationship between two existing entities."""

    finding_index: int
    source_entity_id: str
    source_entity_name: str
    source_entity_type: str
    target_entity_id: str
    target_entity_name: str
    target_entity_type: str
    suggested_rel_type: str
    inverse_rel_type: str | None = None
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)
    story_relevance: float = Field(ge=0.0, le=1.0, default=0.5)


class ConsistencyIssue(BaseModel):
    """A contradiction or inconsistency found in the worldbuilding."""

    finding_index: int
    category: ConsistencyCategory
    entity_ids: list[str]
    entity_names: list[str]
    description: str
    contradiction: str
    suggested_resolution: str | None = None
    severity: WorldbuildingSeverity = WorldbuildingSeverity.MAJOR
    confidence: float = Field(ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# Request / Response Schemas
# ---------------------------------------------------------------------------


class WorldbuildingAnalysisRequest(BaseModel):
    """Request to run a worldbuilding analysis."""

    entity_types: list[str] | None = None
    include_gaps: bool = True
    include_connections: bool = True
    include_consistency: bool = True
    max_findings: int = Field(default=50, ge=1, le=200)
    refresh: bool = False


class WorldbuildingAnalysisResponse(BaseModel):
    """Complete worldbuilding analysis response."""

    novel_id: str
    entity_count: int
    gap_findings: list[GapFinding]
    connection_suggestions: list[ConnectionSuggestion]
    consistency_issues: list[ConsistencyIssue]
    worldbuilding_score: float = Field(ge=0.0, le=1.0)
    overall_assessment: str
    summary: dict[str, int]
    analyzed_at: str  # ISO datetime string


class WorldbuildingApplyRequest(BaseModel):
    """Request to apply selected connection suggestions."""

    finding_indices: list[int]


class WorldbuildingApplyResponse(BaseModel):
    """Response after applying connection suggestions."""

    success: bool
    created_count: int
    failed_count: int
    errors: list[str] = []


# ---------------------------------------------------------------------------
# Worldbuilding Service Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class WorldbuildingProtocol(Protocol):
    """Protocol for worldbuilding analysis services.

    Provides three analysis operations (gap detection, connection suggestions,
    consistency checking) delivered through a unified analyze() call, plus
    apply() for creating suggested relationships. Both operations gate on
    novel ownership (IDOR fix S8): the caller must own ``novel_id`` BEFORE
    any analysis or relationship write; foreign and unknown ids are
    indistinguishable (``NotFoundError`` → 404).
    """

    async def analyze(
        self,
        *,
        novel_id: UUID,
        request: WorldbuildingAnalysisRequest,
        user_id: UUID,
    ) -> WorldbuildingAnalysisResponse:
        """Analyze the project's worldbuilding health.

        Runs gap detection, connection suggestion, and/or consistency checking
        based on request options. Results are cached with 10min TTL.

        Args:
            novel_id: The project to analyze.
            request: Analysis options and filters.
            user_id: The caller — must own the novel (ownership gate).

        Returns:
            Complete analysis with all requested finding types.
        """
        ...

    async def apply_connections(
        self,
        *,
        novel_id: UUID,
        user_id: UUID,
        request: WorldbuildingApplyRequest,
        analysis: WorldbuildingAnalysisResponse,
    ) -> WorldbuildingApplyResponse:
        """Apply selected connection suggestions as real relationships.

        Creates KBRelationship entries for the selected suggestions.
        Requires the original analysis response for context (entity IDs, rel types).

        Args:
            novel_id: The project containing the entities.
            user_id: The caller — must own the novel (ownership gate).
            request: Which connection indices to apply.
            analysis: The analysis response containing the suggestions.

        Returns:
            Result with counts of created/failed relationships.
        """
        ...
