# KB-006b: Worldbuilding AI Assistant — Architecture Specification

> **Status**: Draft
> **Area**: KB / AI Analysis
> **Depends on**: KB-006a (view), KB-003 (improve pattern), INFRA-001/002/003
> **Author**: Architecture Specialist
> **Date**: 2026-05-26

---

## Table of Contents

1. [Executive Summary & Decision](#1-executive-summary--decision)
2. [Root Cause & Motivation](#2-root-cause--motivation)
3. [Alternatives Considered](#3-alternatives-considered)
4. [Contracts](#4-contracts)
5. [Module Map](#5-module-map)
6. [Data Flow](#6-data-flow)
7. [Caching Strategy](#7-caching-strategy)
8. [Frontend Integration](#8-frontend-integration)
9. [Prompt Strategy & Context Management](#9-prompt-strategy--context-management)
10. [RULE-XX Compliance Matrix](#10-rule-xx-compliance-matrix)
11. [Work Plan](#11-work-plan)

---

## 1. Executive Summary & Decision

### Decision: Option C — Hybrid

Create a new `WorldbuildingService` + `WorldbuildingAnalyzer` + `WorldbuildingAgent` that **reuses the architectural pattern** (analyze → cache → apply) from `KBImproveAnalyzer` without coupling to it. This gives clean separation of concerns while leveraging proven infrastructure.

| Aspect | Approach |
|--------|----------|
| **Service scope** | Project-level (not entry-level) — analyzes all entities |
| **Pattern reuse** | analyze/apply/cache pattern from KB-003, not the code itself |
| **Infrastructure reuse** | `KBAgent` (tools), `KBImproveCache` (Redis, new key prefix), `ProactiveContextService` (world context), `ModelRegistry` (model resolution), `PromptComposer` (prompt building) |
| **Analysis types** | 3 separate phases orchestrated by the service: gap detection, connection suggestions, consistency checking |
| **Prompt strategy** | 2 prompts: Phase 1 combined (gap + connections), Phase 2 separate (consistency). Context-window-managed via entity summaries. |
| **Streaming** | No SSE for MVP — follows existing KB analysis pattern (POST → full response). SSE possible in future via RULE-13 interface. |

### Key Architectural Insight

KB-003 (Improve) operates on **one entry** → returns suggestions for **that entry**. KB-006b operates on **the project** → returns findings across **all entities**. This fundamental scope difference demands a separate service, not an extension of improve.

---

## 2. Root Cause & Motivation

### Symptom

Writers build worldbuilding entities (characters, locations, factions, systems) but lack automated tooling to detect gaps, suggest connections, and find contradictions across their entire project.

### Root Cause

The existing KB infrastructure (KB-001 through KB-005, KB-007) is **entry-centric**: each service operates on a single entity. No service analyzes the **project-level** health of the worldbuilding:

- `KBImproveService` — analyzes one entry for improvement opportunities
- `KBSuggestService` — suggests values for one field during creation
- `RelationshipService` — creates/deletes individual relationships, no analysis

### Design Principle

> A worldbuilding assistant must see the **forest** (the project's entire KB graph), not just individual **trees** (single entries).

The solution is a project-level analysis service that scans all entities, their fields, their relationships, and their story context to produce an integrated worldbuilding health report.

---

## 3. Alternatives Considered

### Option A — Extend Improve System (REJECTED)

Add worldbuilding analysis modes to `KBImproveAnalyzer`/`KBImproveService`.

| Pro | Con |
|-----|-----|
| No new files for analyze/apply/cache pattern | **Violates RULE-06**: `improve_analyzer.py` would have two fundamentally different scopes (entry-level AND project-level) |
| Same endpoint pattern | **Wrong cache scope**: entry-level cache key (`kb:improve:{entry_id}`) doesn't fit project-level analysis |
| Same dependency injection | **Different apply semantics**: improve applies field changes to one entry; worldbuilding creates relationships across entities |
| - | **Conditional complexity**: every method would need "am I in entry mode or project mode?" branching |
| - | Would exceed 300-line soft limit on improve_analyzer.py (already at 275 lines) |

**Verdict**: REJECTED — violates architectural integrity. Single-responsibility principle demands separation.

### Option B — Pure New Service (REJECTED)

Standalone `WorldbuildingService` + `WorldbuildingAgent` with zero reuse.

| Pro | Con |
|-----|-----|
| Cleanest separation | Duplicates analyze/apply/cache pattern already proven in KBImproveAnalyzer |
| No risk of coupling | Duplicates caching infrastructure even though KBImproveCache exists |
| Independent evolution | Reinstantiates KBAgent, ProactiveContextService, ModelRegistry — all already wired in existing DI |
| - | More boilerplate, more testing surface, more files |
| - | No architectural benefit over Option C |

**Verdict**: REJECTED — unnecessary duplication. The pattern is proven; only the scope changes.

### Option C — Hybrid (SELECTED)

New `WorldbuildingService` + `WorldbuildingAnalyzer` + `WorldbuildingAgent` **reusing the pattern**, not the code.

| Pro | Con |
|-----|-----|
| Clean separation of concerns | New files (but this is correct — new scope = new module) |
| Reuses proven infrastructure (KBImproveCache, KBAgent, ProactiveContext, ModelRegistry, PromptComposer) | Minor: must add new LLMIntent and prompt category |
| No risk of coupling to improve module | |
| Proper cache isolation (different key prefix) | |
| Scales independently (different context strategies for 100+ entities) | |
| Follows existing patterns — easy for future specialists to understand | |

**Verdict**: SELECTED — correct architectural separation with maximum reuse of proven infrastructure.

---

## 4. Contracts

### 4.1 Service Protocol

Location: `apps/api/narrare/kb/worldbuilding_contracts.py`

```python
"""Worldbuilding analysis service contract — Protocol definitions.

Contracts are written before implementation (RULE-03).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from uuid import UUID


# ---------------------------------------------------------------------------
# Enums & Shared Types
# ---------------------------------------------------------------------------


class WorldbuildingSeverity(str, enum.Enum):
    """Severity level for worldbuilding findings."""
    CRITICAL = "critical"    # Blocks writing — e.g., a character with no faction in a faction-driven plot
    MAJOR = "major"          # Significant issue — should address before next writing session
    MINOR = "minor"          # Nice-to-fix — no immediate impact on writing
    INFO = "info"            # Observation — not necessarily a problem


class GapType(str, enum.Enum):
    """Types of gaps the detector can identify."""
    MISSING_ENTITY = "missing_entity"           # Entity type not represented in project
    MISSING_FIELD = "missing_field"             # Required template field is empty
    MISSING_CONNECTION = "missing_connection"   # Entity is isolated (no relationships)
    MISSING_BODY = "missing_body"              # Entity has no body/description
    UNDEFINED_TYPE = "undefined_type"           # Entity type not yet used


class ConsistencyCategory(str, enum.Enum):
    """Categories of consistency issues."""
    GEOGRAPHY = "geography"       # Distance, terrain, climate contradictions
    POLITICS = "politics"         # Faction relationship conflicts
    ECONOMICS = "economics"       # Trade/resource contradictions
    SYSTEM_RULES = "system_rules"  # Magic/technology rule violations
    TIMELINE = "timeline"         # Chronological contradictions
    CHARACTER = "character"       # Character information contradictions


# ---------------------------------------------------------------------------
# Finding Types
# ---------------------------------------------------------------------------


class GapFinding(BaseModel):
    """A gap in the project's worldbuilding.

    Attributes:
        entity_id: Entity with the gap, or None for project-level gaps.
        entity_name: Name of the entity.
        entity_type: Entity type (character, location, etc.), or None.
        gap_type: What kind of gap was found.
        field_key: For MISSING_FIELD — which template field is empty.
        description: Human-readable description of the gap.
        related_entity_type: For MISSING_ENTITY — what type is missing from the project.
        story_relevance: How relevant this gap is to current story content (0.0-1.0).
        severity: How urgently this should be addressed.
    """

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
    """A suggested relationship between two existing entities.

    Attributes:
        source_entity_id: UUID of the source entity.
        source_entity_name: Name of the source entity.
        source_entity_type: Entity type of the source.
        target_entity_id: UUID of the target entity.
        target_entity_name: Name of the target entity.
        target_entity_type: Entity type of the target.
        suggested_rel_type: The suggested relationship type (from RelationshipType constants).
        inverse_rel_type: The suggested inverse relationship, if applicable.
        reasoning: Why this connection makes sense.
        confidence: How confident the AI is (0.0-1.0).
        story_relevance: How relevant to current story content (0.0-1.0).
    """

    finding_index: int  # Stable index for apply/dismiss
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
    """A contradiction or inconsistency found in the worldbuilding.

    Attributes:
        category: The area of worldbuilding affected.
        entity_ids: IDs of all entities involved in the inconsistency.
        entity_names: Names of entities involved (for display).
        description: What the issue is.
        contradiction: Specifically what contradicts what.
        suggested_resolution: How the user could fix this.
        severity: How urgently this should be addressed.
        confidence: How confident the AI is (0.0-1.0).
    """

    finding_index: int  # Stable index for apply/dismiss
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
    """Request to run a worldbuilding analysis.

    Attributes:
        entity_types: Optional filter — analyze only specific entity types.
            When None, analyzes all types present in the project.
        include_gaps: Whether to detect gaps (default: True).
        include_connections: Whether to suggest connections (default: True).
        include_consistency: Whether to check consistency (default: True).
        max_findings: Maximum total findings to return (default: 50).
        refresh: If True, bypass cache and force fresh analysis (default: False).
    """

    entity_types: list[str] | None = None
    include_gaps: bool = True
    include_connections: bool = True
    include_consistency: bool = True
    max_findings: int = Field(default=50, ge=1, le=200)
    refresh: bool = False


class WorldbuildingAnalysisResponse(BaseModel):
    """Complete worldbuilding analysis response.

    Attributes:
        novel_id: The project being analyzed.
        entity_count: How many entities were analyzed.
        gap_findings: Detected gaps in worldbuilding.
        connection_suggestions: Suggested new relationships.
        consistency_issues: Detected contradictions.
        worldbuilding_score: Overall worldbuilding health (0.0-1.0).
        overall_assessment: 1-3 sentence summary of worldbuilding health.
        summary: Breakdown counts of findings by type and severity.
        analyzed_at: When the analysis was performed.
    """

    novel_id: str
    entity_count: int
    gap_findings: list[GapFinding]
    connection_suggestions: list[ConnectionSuggestion]
    consistency_issues: list[ConsistencyIssue]
    worldbuilding_score: float = Field(ge=0.0, le=1.0)
    overall_assessment: str
    summary: dict[str, int]  # e.g. {"gaps": 5, "connections": 8, "consistency": 3}
    analyzed_at: str  # ISO datetime string


class WorldbuildingApplyRequest(BaseModel):
    """Request to apply selected connection suggestions.

    Attributes:
        finding_indices: Indices of ConnectionSuggestion findings to apply.
            Only connection suggestions can be auto-applied (creates relationships).
    """

    finding_indices: list[int]


class WorldbuildingApplyResponse(BaseModel):
    """Response after applying connection suggestions.

    Attributes:
        success: Whether the operation completed (partial success possible).
        created_count: How many relationships were created.
        failed_count: How many creations failed (already exists, etc.).
        errors: Per-failure error messages.
    """

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
    apply() for creating suggested relationships.
    """

    async def analyze(
        self,
        *,
        novel_id: UUID,
        request: WorldbuildingAnalysisRequest,
    ) -> WorldbuildingAnalysisResponse:
        """Analyze the project's worldbuilding health.

        Runs gap detection, connection suggestion, and/or consistency checking
        based on request options. Results are cached with 10min TTL.

        Args:
            novel_id: The project to analyze.
            request: Analysis options and filters.

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
            user_id: The user performing the action.
            request: Which connection indices to apply.
            analysis: The analysis response containing the suggestions.

        Returns:
            Result with counts of created/failed relationships.
        """
        ...
```

### 4.2 Agent Types

Location: `packages/core/narrare_core/agents/worldbuilding_types.py`

```python
"""Output types for WorldbuildingAgent.

Two output modes:
  - Phase 1 (Gap + Connections): Entity-summary-level analysis
  - Phase 2 (Consistency): Entity-pair-depth analysis
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Phase 1: Gap Detection + Connection Suggestions (combined output)
# ---------------------------------------------------------------------------


class Phase1EntitySummary(BaseModel):
    """Summary of a single entity for the Phase 1 analysis prompt."""
    entry_id: str
    name: str
    entity_type: str
    field_fill_rate: float  # What fraction of template fields are non-empty
    relationship_count: int
    has_body: bool
    chapter_references: int  # How many chapters reference this entity


class Phase1GapOutput(BaseModel):
    """A single gap finding from Phase 1."""
    entity_id: str | None = None
    entity_name: str | None = None
    entity_type: str | None = None
    gap_type: str  # missing_entity, missing_field, missing_connection, missing_body
    field_key: str | None = None
    description: str
    related_entity_type: str | None = None
    story_relevance: float = Field(ge=0.0, le=1.0, default=0.5)
    severity: str = "major"


class Phase1ConnectionOutput(BaseModel):
    """A single connection suggestion from Phase 1."""
    source_entity_id: str
    source_entity_name: str
    target_entity_id: str
    target_entity_name: str
    suggested_rel_type: str
    inverse_rel_type: str | None = None
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)
    story_relevance: float = Field(ge=0.0, le=1.0, default=0.5)


class WorldbuildingPhase1Output(BaseModel):
    """Combined output of Phase 1 analysis."""
    gaps: list[Phase1GapOutput]
    connection_suggestions: list[Phase1ConnectionOutput]
    assessment: str
    worldbuilding_score: float = Field(ge=0.0, le=1.0)
    candidate_pairs_for_consistency: list[tuple[str, str]]  # Entity ID pairs to check


# ---------------------------------------------------------------------------
# Phase 2: Consistency Checking (separate, detailed)
# ---------------------------------------------------------------------------


class Phase2ConsistencyOutput(BaseModel):
    """A single consistency issue from Phase 2."""
    category: str
    entity_ids: list[str]
    entity_names: list[str]
    description: str
    contradiction: str
    suggested_resolution: str | None = None
    severity: str = "major"
    confidence: float = Field(ge=0.0, le=1.0)


class WorldbuildingPhase2Output(BaseModel):
    """Output of Phase 2 consistency checking."""
    issues: list[Phase2ConsistencyOutput]
    assessment: str  # Overall consistency assessment


# ---------------------------------------------------------------------------
# Agent Dependencies
# ---------------------------------------------------------------------------


class WorldbuildingDeps:
    """Dependencies for WorldbuildingAgent.

    Attributes:
        language: Output language code.
        entity_summaries: Summary list of all entities (for Phase 1).
        entity_details: Full entity details keyed by ID (for Phase 2 lookup).
        template_structures: Template field definitions keyed by entity type.
        existing_relationships: All relationships in the project.
        available_rel_types: Entity-type-pair → possible relationship types.
        world_context: KB context from ProactiveContextService.
        chapter_entity_refs: Entity IDs → chapter reference count.
        candidate_pairs: For Phase 2 — entity ID pairs to check for consistency.
    """

    def __init__(
        self,
        language: str = "en",
        entity_summaries: list[Phase1EntitySummary] | None = None,
        entity_details: dict[str, dict[str, Any]] | None = None,
        template_structures: dict[str, dict[str, Any]] | None = None,
        existing_relationships: list[dict[str, Any]] | None = None,
        available_rel_types: dict[str, list[str]] | None = None,
        world_context: str | None = None,
        chapter_entity_refs: dict[str, int] | None = None,
        candidate_pairs: list[tuple[str, str]] | None = None,
    ) -> None:
        self.language = language
        self.entity_summaries = entity_summaries or []
        self.entity_details = entity_details or {}
        self.template_structures = template_structures or {}
        self.existing_relationships = existing_relationships or []
        self.available_rel_types = available_rel_types or {}
        self.world_context = world_context
        self.chapter_entity_refs = chapter_entity_refs or {}
        self.candidate_pairs = candidate_pairs or []
```

### 4.3 Agent Definition

Location: `packages/core/narrare_core/agents/worldbuilding_agent.py`

```python
"""WorldbuildingAgent — project-level worldbuilding analysis.

Two-phase analysis:
  Phase 1: Gap detection + connection suggestions (entity summaries)
  Phase 2: Consistency checking (entity pair deep-dive)

Composes with KBAgent for entity lookup tools during analysis.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic_ai import RunContext
from pydantic_ai.capabilities import ToolSearch, Toolset

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.worldbuilding_types import (
    WorldbuildingDeps,
    WorldbuildingPhase1Output,
    WorldbuildingPhase2Output,
)

if TYPE_CHECKING:
    from narrare_core.agents.kb_agent import KBAgent


class WorldbuildingAgent(NarrareAgent[WorldbuildingDeps, WorldbuildingPhase1Output]):
    """Agent that analyzes project-level worldbuilding health.

    Phase 1: Receives entity summaries, detects gaps and suggests connections.
    Phase 2: Receives entity pairs + full details, checks consistency.

    Composes with KBAgent for optional entity lookup during analysis.
    """

    def __init__(
        self,
        model: Any,
        kb_agent: KBAgent | None = None,
        system_prompt: str | None = None,
    ) -> None:
        capabilities: list[Any] = []
        if kb_agent is not None:
            capabilities.append(ToolSearch(strategy="keywords"))
            capabilities.append(Toolset(kb_agent.get_toolset()))

        super().__init__(
            model=model,
            deps_type=WorldbuildingDeps,
            output_type=[self._process_phase1, WorldbuildingPhase1Output],
            capabilities=capabilities,
            system_prompt=system_prompt,
        )

    async def _process_phase1(
        self,
        ctx: RunContext[WorldbuildingDeps],
        gaps: list[dict[str, Any]] | None = None,
        connection_suggestions: list[dict[str, Any]] | None = None,
        assessment: str = "",
        worldbuilding_score: float = 0.0,
        candidate_pairs: list[list[str]] | None = None,
    ) -> WorldbuildingPhase1Output:
        """Output Function for Phase 1 — structures LLM response."""
        if ctx.partial_output:
            return WorldbuildingPhase1Output(
                gaps=[], connection_suggestions=[], assessment="",
                worldbuilding_score=0.0, candidate_pairs=[],
            )

        from narrare_core.agents.worldbuilding_types import (
            Phase1ConnectionOutput,
            Phase1GapOutput,
        )

        parsed_gaps = [
            Phase1GapOutput(**g) for g in (gaps or [])
        ]
        parsed_connections = [
            Phase1ConnectionOutput(**c) for c in (connection_suggestions or [])
        ]
        parsed_pairs = [
            (p[0], p[1]) for p in (candidate_pairs or []) if len(p) == 2
        ]

        return WorldbuildingPhase1Output(
            gaps=parsed_gaps,
            connection_suggestions=parsed_connections,
            assessment=assessment,
            worldbuilding_score=min(max(worldbuilding_score, 0.0), 1.0),
            candidate_pairs=parsed_pairs,
        )

    async def run_phase1(
        self,
        prompt: str,
        deps: WorldbuildingDeps,
        **kwargs: Any,
    ) -> WorldbuildingPhase1Output:
        """Execute Phase 1 analysis (gaps + connections)."""
        result = await self._agent.run(prompt, deps=deps, **kwargs)
        return result.output  # type: ignore[return-value]

    async def run_phase2(
        self,
        prompt: str,
        deps: WorldbuildingDeps,
        model: Any,  # Phase 2 can use a different model
        system_prompt: str | None = None,
    ) -> WorldbuildingPhase2Output:
        """Execute Phase 2 consistency checking with separate agent instance.

        Phase 2 uses its own agent instance because it has different
        output type and potentially different model/system prompt.
        """
        from narrare_core.agents.worldbuilding_types import WorldbuildingPhase2Output

        agent = NarrareAgent(
            model=model,
            deps_type=WorldbuildingDeps,
            output_type=[self._process_phase2, WorldbuildingPhase2Output],
            system_prompt=system_prompt,
        )
        result = await agent.run(prompt, deps=deps)
        return result.output  # type: ignore[return-value]

    async def _process_phase2(
        self,
        ctx: RunContext[WorldbuildingDeps],
        issues: list[dict[str, Any]] | None = None,
        assessment: str = "",
    ) -> WorldbuildingPhase2Output:
        """Output Function for Phase 2 consistency checking."""
        from narrare_core.agents.worldbuilding_types import Phase2ConsistencyOutput

        parsed = [
            Phase2ConsistencyOutput(**i) for i in (issues or [])
        ]
        return WorldbuildingPhase2Output(issues=parsed, assessment=assessment)

    async def run(
        self,
        prompt: str,
        deps: WorldbuildingDeps,
        **kwargs: Any,
    ) -> WorldbuildingPhase1Output:
        """Default run for Phase 1 (backwards compatibility)."""
        return await self.run_phase1(prompt, deps, **kwargs)
```

---

## 5. Module Map

### 5.1 New Files

Files are listed in implementation order (Layer Ordering).

| # | Layer | File | Purpose | Est. Lines |
|---|-------|------|---------|-----------|
| 1 | Core | `packages/core/narrare_core/agents/worldbuilding_types.py` | Agent output types (Phase1GapOutput, Phase1ConnectionOutput, Phase2ConsistencyOutput, WorldbuildingDeps) | ~180 |
| 2 | Core | `packages/core/narrare_core/agents/worldbuilding_agent.py` | WorldbuildingAgent (Phase 1 + Phase 2, composes with KBAgent) | ~160 |
| 3 | Core | `packages/core/narrare_core/prompts/_bundled/kb/en/worldbuilding/phase1/system.md` | Phase 1 prompt (gap detection + connection suggestions) | ~100 |
| 4 | Core | `packages/core/narrare_core/prompts/_bundled/kb/en/worldbuilding/phase2/system.md` | Phase 2 prompt (consistency checking) | ~100 |
| 5 | Backend | `apps/api/narrare/kb/worldbuilding_contracts.py` | WorldbuildingProtocol + all Pydantic schemas | ~250 |
| 6 | Backend | `apps/api/narrare/kb/worldbuilding_cache.py` | Redis-backed cache wrapper for project-level results | ~60 |
| 7 | Backend | `apps/api/narrare/kb/worldbuilding_analyzer.py` | LLM orchestration: deps building, cache, agent execution, entity data assembly | ~250 |
| 8 | Backend | `apps/api/narrare/kb/worldbuilding_service.py` | Business logic: analyze() orchestration + apply_connections() | ~120 |
| 9 | Backend | `apps/api/narrare/kb/router_worldbuilding.py` | FastAPI routes (thin delegation) | ~80 |
| 10 | Frontend | `packages/web/lib/api/worldbuilding.ts` | API types + client functions | ~80 |
| 11 | Frontend | `packages/web/lib/hooks/useWorldbuilding.ts` | TanStack Query hooks | ~60 |
| 12 | Frontend | `packages/web/components/studio/kb/WorldbuildingAnalysisPanel.tsx` | Analysis results panel (gaps, connections, consistency tabs) | ~350 |

### 5.2 Modified Files

| # | File | Change | Reason |
|---|------|--------|--------|
| M1 | `packages/core/narrare_core/agents/__init__.py` | Export WorldbuildingAgent | Module public API |
| M2 | `packages/core/narrare_core/llm/intents.py` | Add `KB_WORLDBUILD = "kb_worldbuild"` to `LLMIntent` + `INTENT_CATEGORY_MAP` + `INTENT_CATEGORY` | Needed for PromptComposer routing |
| M3 | `packages/core/narrare_core/prompts/composer.py` | Add `LLMIntent.KB_WORLDBUILD: "kb"` to `_INTENT_TO_CATEGORY` and `"worldbuilding"` to `_INTENT_TO_MODE` | Maps intent → prompt directory |
| M4 | `apps/api/narrare/kb/dependencies.py` | Add `get_worldbuilding_service()` factory | Dependency injection |
| M5 | `apps/api/narrare/kb/__init__.py` | Export new worldbuilding modules | Package public API |
| M6 | `packages/web/components/studio/WorldBuilding.tsx` | Add "Analyze" button in toolbar, state management for analysis panel | Frontend integration |
| M7 | `packages/web/lib/api/kb.ts` | Add `KBEntityType` export for client if missing | Type sharing |
| M8 | `tests/unit/core/agents/test_worldbuilding_agent.py` | Agent-level unit tests | RULE-10 |
| M9 | `tests/unit/api/narrare/kb/test_worldbuilding_service.py` | Service-level unit tests | RULE-10 |
| M10 | `tests/integration/api/narrare/kb/test_router_worldbuilding.py` | Router integration tests | RULE-10 |
| M11 | `packages/web/components/studio/kb/KBDetailPanel.tsx` | Add "Run Worldbuilding Analysis" button to entry detail | Entry-level integration point |

### 5.3 Module Boundary Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     apps/api/narrare/kb/                         │
│                                                                  │
│  router_worldbuilding.py ──→ worldbuilding_service.py            │
│                                  │                               │
│                                  ├──→ worldbuilding_analyzer.py  │
│                                  │       │                       │
│                                  │       ├──→ improve_cache.py   │
│                                  │       │      (reused)         │
│                                  │       │                       │
│                                  │       └──→ ModelRegistry      │
│                                  │            PromptComposer      │
│                                  │            KBAgent            │
│                                  │            (core/ via DI)     │
│                                  │                               │
│                                  └──→ RelationshipRepository     │
│                                       KBRepository               │
│                                       (for apply_connections)    │
│                                                                  │
│  worldbuilding_contracts.py ← Protocol definition                │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     packages/core/narrare_core/                   │
│                                                                  │
│  agents/                                                         │
│    worldbuilding_types.py   ← Output types                       │
│    worldbuilding_agent.py   ← NarrareAgent[WDeps, WPhase1Output]│
│    kb_agent.py              ← Tool provider (reused)             │
│                                                                  │
│  prompts/_bundled/kb/en/worldbuilding/                           │
│    phase1/system.md         ← Gap + connection prompt            │
│    phase2/system.md         ← Consistency check prompt           │
│                                                                  │
│  llm/                                                            │
│    intents.py               ← KB_WORLDBUILD added                │
│    gateway.py               ← ModelRegistry (reused)             │
│                                                                  │
│  context/                                                        │
│    contract.py              ← ProactiveContextProtocol (reused)  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Data Flow

### 6.1 General Flow (all three features)

```
User clicks "Analyze Worldbuilding"
        │
        ▼
┌────────────────────────────────┐
│  Worldbuilding.tsx              │
│  opens WorldbuildingAnalysisPanel │
│  calls useWorldbuildingAnalysis │
│  (TanStack Query mutation)     │
└──────────┬─────────────────────┘
           │ POST /novels/{id}/kb/worldbuilding/analyze
           ▼
┌────────────────────────────────┐
│  router_worldbuilding.py       │  (thin — RULE-06)
│  service.analyze(novel_id, req)│
└──────────┬─────────────────────┘
           ▼
┌──────────────────────────────────────────────┐
│  worldbuilding_service.py: analyze()          │
│                                               │
│  1. Check cache (if not refresh)              │
│     → Cache hit? Return cached response       │
│                                               │
│  2. Check cache (if not refresh)              │
│     → Cache hit? Return cached response       │
│                                               │
│  3. Delegate to worldbuilding_analyzer.py     │
│     → Phase 1: Gap + Connections              │
│     → Phase 2: Consistency (if requested)     │
│                                               │
│  4. Store in cache (10min TTL)                │
│  5. Return WorldbuildingAnalysisResponse      │
└──────────┬────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────┐
│  worldbuilding_analyzer.py                    │
│                                               │
│  build_deps(novel_id):                        │
│    1. KBRepository: list all entities         │
│    2. RelationshipRepository: all rels        │
│    3. ProactiveContext: chapter references    │
│    4. TemplateFields: per-type field defs     │
│    5. Build Phase1EntitySummary[]             │
│    6. ProactiveContext: world context          │
│    → Returns WorldbuildingDeps                │
│                                               │
│  run_phases(deps, options):                   │
│    Phase 1:                                   │
│      - PromptComposer.build(WORLDBUILD, phase1)│
│      - model = registry.get_model(config)     │
│      - agent = WorldbuildingAgent(model, ...) │
│      - result = agent.run_phase1(...)         │
│      → gaps, connections, candidate_pairs     │
│                                               │
│    Phase 2 (if requested):                    │
│      - Load full details for candidate_pairs  │
│      - PromptComposer.build(WORLDBUILD, phase2)│
│      - result = agent.run_phase2(...)         │
│      → consistency_issues                     │
│                                               │
│    → Map to response types                    │
└──────────┬────────────────────────────────────┘
           │
           ▼
┌────────────────────────────────┐
│  Frontend:                      │
│  WorldbuildingAnalysisPanel    │
│  shows:                        │
│  - Tab: Gaps (severity-sorted) │
│  - Tab: Connections (selectable)│
│  - Tab: Consistency (grouped) │
│  - Score + assessment          │
└────────────────────────────────┘
```

### 6.2 Apply Flow (connections only)

```
User selects connection suggestions → clicks "Apply"
        │
        ▼
┌────────────────────────────────┐
│  WorldbuildingAnalysisPanel     │
│  calls useWorldbuildingApply   │
└──────────┬─────────────────────┘
           │ POST /novels/{id}/kb/worldbuilding/apply
           ▼
┌────────────────────────────────┐
│  router_worldbuilding.py       │
│  service.apply_connections(...) │
└──────────┬─────────────────────┘
           ▼
┌──────────────────────────────────────────────┐
│  worldbuilding_service.py: apply_connections()│
│                                               │
│  1. For each finding_index:                   │
│     a. Look up ConnectionSuggestion from      │
│        the provided analysis response         │
│     b. Validate entities exist                │
│     c. Check for duplicate relationship       │
│     d. KBRelationship.create()                │
│                                               │
│  2. Invalidate worldbuilding cache            │
│  3. Invalidate relationship cache             │
│  4. Return WorldbuildingApplyResponse         │
└──────────────────────────────────────────────┘
```

### 6.3 Phase 1 Analysis Detail (Entity Summary Assembly)

```
worldbuilding_analyzer._build_phase1_deps(novel_id):

  1. entities = kb_repo.list_for_novel(novel_id)
     → For each entity: id, name, type, metadata (field values), body, tags

  2. template_fields = get_template_fields(entity_type)
     → Per type: list of {field_key, label, required}

  3. For each entity, compute:
     - field_fill_rate: non-empty fields ÷ total template fields
     - relationship_count: rel_repo.count_for_entity(entity_id)
     - has_body: bool(len(entity.body or "") > 50)
     - chapter_references: proactive_context.mention_count(entity.name)

  4. relationship_map = rel_repo.get_adjacency_map(novel_id)
     → dict[entity_id, set[related_entity_ids]]

  5. world_context = proactive_context.suggest(f"worldbuilding analysis for {novel_id}")
     → Top 20 relevant entities ranked by story relevance

  6. return WorldbuildingDeps(entity_summaries=..., ...)
```

### 6.4 Phase 2 Analysis Detail (Pair Assembly)

```
worldbuilding_analyzer._build_phase2_deps(novel_id, candidate_pairs):

  1. For each (entity_a_id, entity_b_id) in candidate_pairs:
     - full_details_a = kb_repo.get_by_id(entity_a_id)
       → name, type, metadata (all fields), body, tags, relationships
     - full_details_b = kb_repo.get_by_id(entity_b_id)
       → same as above

  2. Build entity_details dict: {entity_id: full_detail_dict}

  3. Return WorldbuildingDeps(entity_details=..., candidate_pairs=...)
     (entity_summaries is empty for Phase 2 — not needed)
```

---

## 7. Caching Strategy

### 7.1 Cache Design

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| **Backend** | Redis via `SessionCacheProtocol` (same as improve) | Proven infrastructure, no new dependencies |
| **Wrapper** | New `WorldbuildingCache` class (similar to `KBImproveCache`) | Different key prefix, different TTL logic |
| **Key prefix** | `kb:worldbuild:{novel_id}` | Project-scoped, not entity-scoped |
| **Entity type filter** | Append hash of `entity_types` list when filtered | `{novel_id}:{hash(["character","location"])}` |
| **TTL** | 10 minutes (600s) | Matches improve cache, balances freshness vs cost |
| **Invalidation trigger 1** | Manual `refresh=True` in request | User clicks "Refresh" in UI |
| **Invalidation trigger 2** | On entity create/update/delete | Any KB mutation makes analysis stale |
| **Invalidation trigger 3** | On relationship create/delete | Relationship changes affect gaps + connections |
| **Cache-after-apply** | Yes — explicitly invalidate after apply_connections | Fresh analysis = accurate state |

### 7.2 Cache Invalidation Points

After a successful `apply_connections()`, the worldbuilding cache is explicitly invalidated so the next `analyze()` call produces fresh results reflecting the newly created relationships.

### 7.3 Implementation Note

The `WorldbuildingCache` class follows the exact pattern of `KBImproveCache` in `improve_cache.py`:

```python
class WorldbuildingCache:
    """Redis-backed cache for worldbuilding analysis results.

    Args:
        cache: Injected cache backend via SessionCacheProtocol.
    """

    def __init__(self, cache: SessionCacheProtocol) -> None:
        self._cache = cache

    def _key(self, novel_id: str, entity_types_hash: str = "") -> str:
        return f"kb:worldbuild:{novel_id}{entity_types_hash}"

    async def get(self, novel_id: str, entity_types_hash: str = "") -> str | None: ...
    async def set(self, novel_id: str, value: str, entity_types_hash: str = "") -> None: ...
    async def delete(self, novel_id: str, entity_types_hash: str = "") -> None: ...
    async def delete_all(self, novel_id: str) -> None: ...  # Invalidate all entity type variants
```

---

## 8. Frontend Integration

### 8.1 Entry Points

The worldbuilding analysis is accessible from three places:

| Entry Point | Component | Trigger |
|-------------|-----------|---------|
| **Toolbar in KBCategorySidebar** | "Analyze Worldbuilding" button | Always visible |
| **Entry detail (KBDetailPanel)** | "Run Analysis" contextual action | When entry is selected |
| **Results from analysis** | WorldbuildingAnalysisPanel | Auto-opens after analysis |

### 8.2 Component Tree

```
WorldBuilding.tsx
├── KBCategorySidebar
│   └── [NEW] "Analyze Worldbuilding" toolbar button
├── KBEntryList
├── [NEW] WorldbuildingAnalysisPanel (replaces KBDetailPanel when active)
│   ├── Header: score + overall assessment + "Refresh" + "Close"
│   ├── Tabs:
│   │   ├── "Gaps" (severity-sorted, color-coded)
│   │   ├── "Connections" (selectable, with apply button)
│   │   └── "Consistency" (category-grouped)
│   ├── Finding detail (expandable cards per finding)
│   └── Footer: apply button (connections tab only)
└── KBDetailPanel (when analysis is not active)
```

### 8.3 State Management

```typescript
// WorldBuilding.tsx additional state
const [showWorldbuildingPanel, setShowWorldbuildingPanel] = useState(false);
const [worldbuildingResult, setWorldbuildingResult] =
  useState<WorldbuildingAnalysisResponse | null>(null);
```

### 8.4 API Layer

Location: `packages/web/lib/api/worldbuilding.ts`

```typescript
// Types (matching backend schemas — RULE-17)

interface GapFinding { ... }
interface ConnectionSuggestion { ... }
interface ConsistencyIssue { ... }
interface WorldbuildingAnalysisResponse { ... }
interface WorldbuildingApplyResponse { ... }

// API client
export const worldbuildingApi = {
  analyze: (novelId: string, options?: WorldbuildingAnalysisRequest) =>
    fetchApi<WorldbuildingAnalysisResponse>(
      `/novels/${novelId}/kb/worldbuilding/analyze`,
      { method: "POST", body: JSON.stringify(options ?? {}) }
    ),
  applyConnections: (novelId: string, request: WorldbuildingApplyRequest) =>
    fetchApi<WorldbuildingApplyResponse>(
      `/novels/${novelId}/kb/worldbuilding/apply`,
      { method: "POST", body: JSON.stringify(request) }
    ),
};
```

### 8.5 Hooks

Location: `packages/web/lib/hooks/useWorldbuilding.ts`

```typescript
export function useWorldbuildingAnalyze(novelId: string) {
  return useMutation<WorldbuildingAnalysisResponse, Error, WorldbuildingAnalysisRequest>({
    mutationFn: (options) => worldbuildingApi.analyze(novelId, options),
    onSuccess: (data) => {
      queryClient.setQueryData(worldbuildingKeys.analysis(novelId), data);
    },
  });
}

export function useWorldbuildingApply(novelId: string) {
  return useMutation<WorldbuildingApplyResponse, Error, WorldbuildingApplyRequest>({
    mutationFn: (request) => worldbuildingApi.applyConnections(novelId, request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: worldbuildingKeys.all(novelId) });
      queryClient.invalidateQueries({ queryKey: ["kb", novelId, "relationships"] });
    },
  });
}
```

### 8.6 Reuse of KBImprovePanel Patterns

The `WorldbuildingAnalysisPanel` follows the same structural patterns as `KBImprovePanel.tsx`:
- **Loading state**: Animated analysis spinner
- **Error state**: Error message + retry button
- **Empty state**: "No issues found" with checkmark
- **Results state**: Tabbed findings with selection + apply
- **Footer**: Action buttons (apply, close)

This consistency is intentional — users familiar with the improve panel will immediately understand the worldbuilding panel.

---

## 9. Prompt Strategy & Context Management

### 9.1 Two-Prompt Strategy

| Phase | Prompt | Location | Purpose | Est. Tokens |
|-------|--------|----------|---------|------------|
| Phase 1 | `phase1/system.md` | `kb/en/worldbuilding/` | Gap detection + connection suggestions | 1500-2000 (prompt) + 2000-3000 (entity summaries) |
| Phase 2 | `phase2/system.md` | `kb/en/worldbuilding/` | Consistency checking | 1500-2000 (prompt) + 3000-5000 (entity pair details) |

### 9.2 Phase 1 Prompt Structure

```
## System Role
You are a worldbuilding analyst... (persona)

## Analysis Types
### Gap Detection
- Missing entity types (project has locations but no factions)
- Missing fields (character has no "occupation" field filled)
- Missing connections (faction has no territory → no "controls" relationship)
- Missing body/description (entity has empty body)
- Prioritize by story relevance (entities referenced in chapters first)

### Connection Suggestions
- Use existing entity-type-pair → relationship type mappings
- Only suggest connections between entities that don't already have that relationship
- Prefer connections with story relevance (entities that appear in same chapters)

## Context
{{entity_summaries}}  ← Generated by analyzer, format:
  [ID] Entity Name (type) — fields: 6/8 filled, rels: 3, chapters: 2, body: yes

{{template_structures}}  ← {entity_type: {field_key: label, ...}}

{{existing_relationships}}  ← Summary: {entity_name} --[{rel_type}]--> {entity_name}

{{available_rel_types}}  ← {entity_type}→{entity_type}: [rel_type1, rel_type2, ...]

{{world_context}}  ← Top 15 relevant entities from ProactiveContext

## Output Format
{structured JSON with gaps + connections + candidate_pairs for consistency}
```

### 9.3 Phase 2 Prompt Structure

```
## System Role
You are a worldbuilding consistency checker... (persona)

## Consistency Categories
- Geography: distance/terrain/climate conflicts
- Politics: contradictory faction relationships
- Economics: resource/trade inconsistencies
- System Rules: magic/tech rule violations
- Timeline: chronological contradictions
- Character: character information contradictions

## Instructions
For each entity pair provided, check for contradictions in:
- Shared fields (both entities define the same concept differently)
- Relationships (entity A is allied and opposed to the same faction)
- Geography (two locations in the same area have contradictory features)
- Rules (a system's limitations are violated by another entity)

## Context
{{candidate_pairs}}  ← Entity pairs to check
{{entity_details}}  ← Full details for pair entities
{{existing_relationships}}  ← All relationships involving these entities

## Output Format
{structured JSON with consistency issues + assessment}
```

### 9.4 Context Window Management

For projects with 100+ entities, the WorldbuildingAnalyzer manages context strategically:

**Step 1: Entity Prioritization**
```
Priority 1: Entities referenced in 1+ chapters (from ProactiveContext)
  → Full summary: name, type, field fill rate, all filled fields, relationship list, body preview

Priority 2: Entities with 3+ relationships (hubs of the KB graph)
  → Medium summary: name, type, field fill rate, relationship count, body indicator

Priority 3: Remaining entities
  → Compact: name, type, field fill rate, relationship count

Priority 4: Entities with zero relationships and zero chapter references
  → Minimal: name, type only (or omit if > 80 entities)
```

**Step 2: Token Budget Enforcement**
```
Phase 1 budget: 8000 tokens for entity data
  → Priority 1: 500 tokens each (max 10) = 5000
  → Priority 2: 200 tokens each (max 10) = 2000
  → Priority 3: 50 tokens each (max 20) = 1000
  → Priority 4: omitted if over budget

Phase 2 budget: 5000 tokens for entity pair details
  → Max 15 pairs, ~300 tokens per pair = 4500
  → System prompt: ~1500 tokens
  → Room for response: ~2000 tokens
```

**Step 3: Fallback Strategy**
If candidate_pairs for Phase 2 exceeds budget:
1. Sort pairs by sum of story relevance scores (descending)
2. Take top N pairs that fit within budget
3. Remaining pairs are noted in the response as "not checked"

### 9.5 Agent Tool Integration

The WorldbuildingAgent composes with KBAgent's tools:
- `search_kb(query, entity_type)` — allows the LLM to look up specific entities during analysis
- `get_entity(name)` — get full details of an entity on demand
- `get_related_entities(entity_name, relation_type)` — explore relationship graph

These are deferred-loaded (only used when the model needs them), minimizing context.

---

## 10. RULE-XX Compliance Matrix

| Rule | Status | How KB-006b Satisfies It |
|------|--------|-------------------------|
| **RULE-01b** | ✅ | WorldbuildingAgent in `core/agents/`. Model comes from `ModelRegistry` via DI. No direct LLM imports. |
| **RULE-02** | ✅ | All prompts via `PromptComposer.build(LLMIntent.KB_WORLDBUILD, ctx)` in `worldbuilding_analyzer.py`. No f-strings. |
| **RULE-03** | ✅ | `WorldbuildingProtocol` in `worldbuilding_contracts.py` is written before any implementation. |
| **RULE-04** | ✅ | Max file sizes respected: agent ~160 lines (< 200), analyzer ~250 lines (< 300), service ~120 lines (< 300), router ~80 lines (< 150), contracts ~250 lines (< 400). |
| **RULE-05** | ✅ | Module boundaries: new files in `apps/api/narrare/kb/` (back end), `packages/core/narrare_core/agents/` + `prompts/` (core), `packages/web/` (frontend). Public exports only. |
| **RULE-06** | ✅ | One responsibility per file: router (delegates), service (orchestrates), analyzer (LLM orchestration), agent (LLM interaction), contracts (protocols + schemas). |
| **RULE-07** | ✅ | Dependency direction: router → service → analyzer → (ModelRegistry, PromptComposer, KBAgent). No imports from apps/ to core/. |
| **RULE-08** | ✅ | Redis via `SessionCacheProtocol` (same adapter as improve). No new external service connections. |
| **RULE-09** | ✅ | All public functions fully typed. No `Any` in contracts. Agent output types are Pydantic models. |
| **RULE-10** | ✅ | Tests planned: agent unit tests, service unit tests, router integration tests. Coverage thresholds: core 90%, api 80%. |
| **RULE-11** | ✅ | All exception paths: log with structlog, re-raise as typed errors (`WorldbuildingServiceError`). No bare `except: pass`. |
| **RULE-12** | ✅ | Service layer is the only public API. WebUI calls `WorldbuildingProtocol` via router. MCP/A2A/CLI would call the same protocol. |
| **RULE-13** | ✅ | Future streaming support: `WorldbuildingProtocol.analyze()` signature can accept `stream: bool = False` without breaking existing callers. Currently non-streaming (matches KB-003 pattern). |
| **RULE-14** | ✅ | No DB model changes — worldbuilding analysis is read-only (entities, relationships already exist). apply_connections uses existing `KBRelationship` model. |
| **RULE-16** | ✅ | Frontend i18n: new translations for worldbuilding UI text. Namespace `studio` or new `worldbuilding` namespace registered in `request.ts`. |
| **RULE-17** | ✅ | API-Frontend contract: TypeScript types in `worldbuilding.ts` match Pydantic schemas in `worldbuilding_contracts.py`. Updates happen in same commit. |
| **RULE-18** | ✅ | No hardcoded model/provider in router. Config via `ResolvedModelConfig` from dependency injection. |
| **RULE-19** | ✅ | `SessionDep` used in `dependencies.py` factory functions, not bare `AsyncSession`. |
| **RULE-20** | ✅ | Complete implementation: proper agent with output types, deduplicated discovery via KBAgent, token-budget-managed context assembly, caching, error handling. No stubs. |
| **ADR-015** | ✅ | Pydantic-ai Agent in `core/agents/`. Model from ModelRegistry. Capabilities (ToolSearch, Toolset) for KBAgent integration. |
| **ADR-019** | ✅ | System prompt consistency: WorldbuildingAgent uses `PromptComposer.build()` for production or `with_meta()` for direct agent use. Meta-prompt integration path reserved. |

---

## 11. Work Plan

### 11.1 Layer Ordering

Implementation follows the dependency chain: **Core → Backend → Frontend**.

| Phase | Step | Task | Files | Depends On | Est. Complexity |
|-------|------|------|-------|------------|-----------------|
| **Core** | C1 | Add `KB_WORLDBUILD` intent to `LLMIntent` | `intents.py` | — | ★☆☆ (trivial) |
| **Core** | C2 | Add intent→category/mode mappings to `composer.py` | `composer.py` | C1 | ★☆☆ (trivial) |
| **Core** | C3 | Write Phase 1 prompt (gap + connections) | `prompts/_bundled/kb/en/worldbuilding/phase1/system.md` | — | ★★★ (moderate) |
| **Core** | C4 | Write Phase 2 prompt (consistency) | `prompts/_bundled/kb/en/worldbuilding/phase2/system.md` | — | ★★★ (moderate) |
| **Core** | C5 | Define agent output types (WorldbuildingTypes) | `agents/worldbuilding_types.py` | — | ★★☆ (definitional) |
| **Core** | C6 | Implement WorldbuildingAgent (Phase1 + Phase2) | `agents/worldbuilding_agent.py` | C5 | ★★★ (agent wiring) |
| **Core** | C7 | Export new agent from `__init__.py` | `agents/__init__.py` | C6 | ★☆☆ (trivial) |
| **Core** | C8 | Write agent unit tests | `tests/unit/core/agents/test_worldbuilding_agent.py` | C6 | ★★☆ (testing) |
| **Backend** | B1 | Define WorldbuildingProtocol + all schemas | `worldbuilding_contracts.py` | C5 | ★★☆ (definitional) |
| **Backend** | B2 | Implement WorldbuildingCache | `worldbuilding_cache.py` | — | ★☆☆ (cache wrapper) |
| **Backend** | B3 | Implement WorldbuildingAnalyzer (deps + phases) | `worldbuilding_analyzer.py` | C6, B1, B2 | ★★★★ (complex — entity assembly + phase orchestration + token budget) |
| **Backend** | B4 | Implement WorldbuildingService | `worldbuilding_service.py` | B3 | ★★☆ (orchestration) |
| **Backend** | B5 | Add DI factory to `dependencies.py` | `dependencies.py` | B4 | ★☆☆ (wiring) |
| **Backend** | B6 | Implement router_worldbuilding.py | `router_worldbuilding.py` | B4, B5 | ★☆☆ (thin router) |
| **Backend** | B7 | Register module exports | `__init__.py` | B6 | ★☆☆ (trivial) |
| **Backend** | B8 | Write service unit tests | `tests/unit/api/narrare/kb/test_worldbuilding_service.py` | B4 | ★★★ (testing) |
| **Backend** | B9 | Write router integration tests | `tests/integration/api/narrare/kb/test_router_worldbuilding.py` | B6 | ★★☆ (testing) |
| **Frontend** | F1 | Define TypeScript types + API client | `lib/api/worldbuilding.ts` | B1 | ★★☆ (definitional) |
| **Frontend** | F2 | Implement TanStack Query hooks | `lib/hooks/useWorldbuilding.ts` | F1 | ★★☆ (hooks) |
| **Frontend** | F3 | Implement WorldbuildingAnalysisPanel | `components/studio/kb/WorldbuildingAnalysisPanel.tsx` | F2 | ★★★ (component) |
| **Frontend** | F4 | Integrate into WorldBuilding.tsx | `components/studio/WorldBuilding.tsx` | F3 | ★★☆ (integration) |
| **Frontend** | F5 | Add i18n translations | `messages/en/studio.json` etc. | F3 | ★☆☆ (text) |
| **Frontend** | F6 | Add entry detail integration button | `KBDetailPanel.tsx` | F3 | ★☆☆ (button) |

### 11.2 Dependency Graph

```
C1 ──→ C2
            ↘
C3 ──→ C5 ──→ C6 ──→ C7 ──→ C8
C4 ──→   │
         │
         ▼
         B1 ──→ B3 ──→ B4 ──→ B5 ──→ B6 ──→ B7
         │       │              │              │
C2 ──────┘       │              │              │
B2 ──────────────┘              │              │
                                 │              │
                                 ▼              ▼
                                 B8             B9

B1 ──→ F1 ──→ F2 ──→ F3 ──→ F4
                          │     └── F5
                          │
                          └── F6
```

### 11.3 Parallelization Opportunities

| Parallel Group | Tasks | Specialist |
|----------------|-------|------------|
| **Batch 1** | C1, C2, C3, C4 | Core (independent) |
| **Batch 2a** | C5, C6, C8 | Core (after C3/C4) |
| **Batch 2b** | B1, B2 | Backend (after C5) |
| **Batch 3** | B3, B4, B5, B6, B7 | Backend (after C6, B1, B2) |
| **Batch 4** | B8, B9 | Testing (after B4, B6) |
| **Batch 5** | F1, F2 | Frontend (after B1) |
| **Batch 6** | F3, F4, F5, F6 | Frontend (after F1, F2) |

### 11.4 Estimated Total Complexity

| Layer | Files | Est. Lines | Complexity |
|-------|-------|-----------|------------|
| Core | 6 new, 2 mod | ~540 lines + ~200 lines prompts | ★★★ (moderate — agent wiring, prompt engineering) |
| Backend | 5 new, 2 mod | ~760 lines | ★★★★ (complex — entity assembly, token budget management, phase orchestration) |
| Frontend | 3 new, 2 mod | ~490 lines + ~30 lines i18n | ★★★ (panel component, integration) |
| Tests | 3 new | ~400 lines | ★★☆ (standard patterns) |
| **Total** | **17 new, 6 mod** | **~2190 lines + ~200 prompts** | |

### 11.5 Definition of Done

- [ ] All contracts (Protocol + schemas) defined and reviewed
- [ ] All prompts written and reviewed for quality
- [ ] Agent types + agent implemented with unit tests
- [ ] Analyzer orchestrates both phases with token budget management
- [ ] Service implements analyze + apply_connections with cache
- [ ] Router endpoints working, integration tests pass
- [ ] Frontend panel shows all three finding types with tabs
- [ ] Apply flow creates relationships correctly
- [ ] Cache invalidation works on refresh + entity mutation
- [ ] All RULE-XX constraints satisfied (see compliance matrix)
- [ ] No workarounds, no TODOs, no half-implementations

---

## Appendix A: LLM Intent Registration

Add to `packages/core/narrare_core/llm/intents.py`:

```python
class LLMIntent(StrEnum):
    # ... existing intents ...
    KB_WORLDBUILD = "kb_worldbuild"
```

Add to `INTENT_CATEGORY_MAP`:
```python
LLMIntent.KB_WORLDBUILD: IntentCategory.KB,
```

Add to `packages/core/narrare_core/prompts/composer.py`:

```python
_INTENT_TO_CATEGORY[LLMIntent.KB_WORLDBUILD] = "kb"
_INTENT_TO_MODE[LLMIntent.KB_WORLDBUILD] = "worldbuilding"
```

## Appendix B: Relationship Type Integration

The `packages/core/narrare_core/kb/relationships.py` module already defines all entity-type-pair relationship type mappings via `_PAIR_SUGGESTIONS` and `suggested_for()` helper. The WorldbuildingAgent prompt references these types by including the `_PAIR_SUGGESTIONS` mapping in the agent deps as `available_rel_types`. This ensures suggested connections use existing relationship types — never fabricated ones.

## Appendix C: SSE Streaming — Deferral Rationale

KB-006b does NOT use SSE streaming for the MVP. This is an intentional exception:

1. **Existing pattern**: KB-003 (Improve) uses REST POST → full response for analysis. KB-006b follows the same pattern. There is no SSE infrastructure for KB analysis features yet.

2. **Analysis, not generation**: Worldbuilding analysis is a one-shot computation (scan entities → produce findings), not a stream of generated content. SSE adds complexity without UX benefit for the MVP.

3. **RULE-13 compliance**: The `WorldbuildingProtocol.analyze()` method signature accepts a `stream` parameter in the request options. When SSE infrastructure is added for KB analysis features, the same method can return `AsyncIterator[str]` without breaking existing callers.

4. **Incremental path**: If SSE is added later, `WorldbuildingAnalysisResponse` is returned as the final message in the stream, with progress events showing "Phase 1 complete", "Phase 2 in progress" etc. The frontend `WorldbuildingAnalysisPanel` is built with a progressive-disclosure state machine that can accept streaming events.

---

> **Specification approved by**: Architecture Specialist
> **Date**: 2026-05-26
> **Next review**: After core agent implementation (Phase C6)
