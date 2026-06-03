# KB-004: KB Consistency Check — Architecture Specification (Option C: Hybrid)

> **Status**: Draft
> **Area**: KB / Consistency Analysis
> **Depends on**: KB-006b Phase 2 (WorldbuildingAnalyzer._run_phase2), KB-003 (improve pattern)
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
7. [Prompt Strategy](#7-prompt-strategy)
8. [Frontend Integration](#8-frontend-integration)
9. [RULE-XX Compliance Matrix](#9-rule-xx-compliance-matrix)
10. [Work Plan](#10-work-plan)

---

## 1. Executive Summary & Decision

### Decision: Option C — Hybrid

KB-004 is a **thin orchestration layer** that combines three analysis sources into a unified "Check Consistency" operation. Two sources are new (entry-internal, relationship asymmetry), one is reused from KB-006b (cross-entity).

| Aspect | Approach |
|--------|----------|
| **Scope** | Per-project: runs across all KB entries in a novel |
| **New code** | ~430 lines total (analyzer ~150, asymmetry helper ~60, service ~100, router ~60) |
| **Reused code** | `WorldbuildingAnalyzer._run_phase2()` for cross-entity consistency; `ConsistencyIssue` + `ConsistencyCategory` + `WorldbuildingSeverity` types |
| **New prompt** | 1 prompt: `kb/en/consistency/system.md` for entry-internal analysis |
| **No new agent** | Reuses `KBImproveAgent` pattern — direct PromptComposer + model, no new pydantic-ai agent class needed |
| **Streaming** | No SSE for MVP — follows existing KB analysis pattern (POST → full response) |

### Key Architectural Insight

KB-006b already handles **cross-entity** consistency via `WorldbuildingAnalyzer._run_phase2()`. KB-004's unique scope is:

1. **Entry-internal** — contradictions within a single entry's own fields (age=25 but birth_year=1990 and story_set_in=2024)
2. **Relationship asymmetry** — A→B="friend" but B→A="enemy" (algorithmic, no LLM)

KB-004 does NOT duplicate KB-006b's cross-entity work — it **calls** it. The service orchestrates all three sources and merges results into a single `ConsistencyCheckResponse`.

---

## 2. Root Cause & Motivation

### Symptom

Writers have no way to detect internal contradictions within a single KB entry's fields, or to spot asymmetric relationships between entity pairs. These are the two most common consistency problems that KB-006b's cross-entity Phase 2 does not cover.

### Root Cause

1. **Entry-internal contradictions**: `KBImproveAnalyzer` detects missing/weak fields but is not designed to find *logical contradictions between a single entry's own fields*. The improve prompt asks "what's missing?" — not "do these values contradict each other?"

2. **Relationship asymmetry**: `RelationshipService` creates/deletes individual relationships but never validates whether reciprocal relationships are semantically consistent. `INVERSE_SUGGESTIONS` exists for *suggesting* inverses during creation, but there is no retroactive check.

3. **Fragmented UX**: Currently a writer must run two separate features (Improve + Worldbuilding) to get a complete consistency picture. Neither covers all angles.

### Design Principle

> Consistency checking should be one button, one report. The user doesn't care *which* subsystem found the issue — they care about the issue.

---

## 3. Alternatives Considered

### Option A — Extend WorldbuildingAnalyzer (REJECTED)

Add entry-internal and asymmetry checks directly to `WorldbuildingAnalyzer`.

| Pro | Con |
|-----|-----|
| No new files | **Violates RULE-06**: `worldbuilding_analyzer.py` already at 295 lines — adding entry-internal logic pushes it past the 300-line soft limit |
| Same cache infrastructure | **Wrong scope**: WorldbuildingAnalyzer is *project-level, LLM orchestration*. Entry-internal analysis is *per-entry, LLM analysis*. Asymmetry is *pure algorithmic*. Three fundamentally different scopes in one class |
| - | **Coupling**: KB-004 would become tightly coupled to KB-006b's internals, making both fragile |

**Verdict**: REJECTED — violates single responsibility. KB-006b is already doing its job well; don't bloat it.

### Option B — Extend KBImproveAnalyzer (REJECTED)

Add a consistency mode to the existing improve analyzer.

| Pro | Con |
|-----|-----|
| Already has per-entry LLM analysis infrastructure | **Violates RULE-06**: `KBImproveAnalyzer` is about *improvement suggestions*, not *consistency checking*. Different output types, different prompt, different semantics |
| Cache per entry exists | **Would need cross-entity access**: Asymmetry check needs relationship data for all entities, not one. Improve is entry-scoped |
| - | **Conditional complexity**: every method needs "am I in improve mode or consistency mode?" branching |

**Verdict**: REJECTED — wrong abstraction layer. Improve and consistency have different scopes, outputs, and prompts.

### Option C — Hybrid with New Thin Orchestration (SELECTED)

New `KBConsistencyService` + `KBConsistencyAnalyzer` + `RelationshipAsymmetryChecker`, with KB-006b Phase 2 reused.

| Pro | Con |
|-----|-----|
| Clean separation of concerns — each component has one job | New files (4 new, minimal) |
| Reuses `ConsistencyIssue` type — no type duplication | Must extend `ConsistencyCategory` enum with `ENTRY_INTERNAL` and `RELATIONSHIP_ASYMMETRY` |
| Reuses `WorldbuildingAnalyzer._run_phase2()` — no LLM duplication | Service must orchestrate 3 sources — but that IS its single responsibility |
| Reuses `KBImproveCache` pattern (new key prefix `kb:consistency:`) | |
| Algorithmic check is free (no LLM cost) and fast | |
| Follows proven patterns — easy for future specialists to understand | |

**Verdict**: SELECTED — correct architectural separation with maximum reuse of proven infrastructure.

---

## 4. Contracts

### 4.1 Extending Existing Types

**Location**: `apps/api/narrare/kb/worldbuilding_contracts.py` (modify)

Add two new categories to the existing `ConsistencyCategory` enum:

```python
class ConsistencyCategory(enum.StrEnum):
    """Categories of consistency issues."""
    GEOGRAPHY = "geography"
    POLITICS = "politics"
    ECONOMICS = "economics"
    SYSTEM_RULES = "system_rules"
    TIMELINE = "timeline"
    CHARACTER = "character"
    # ── New for KB-004 ──
    ENTRY_INTERNAL = "entry_internal"          # Contradictions within a single entry's fields
    RELATIONSHIP_ASYMMETRY = "relationship_asymmetry"  # Asymmetric reciprocal relationships
```

**Rationale**: `ConsistencyIssue` already has `category`, `entity_ids`, `entity_names`, `description`, `contradiction`, `suggested_resolution`, `severity`, `confidence`. Entry-internal issues map naturally: `entity_ids=[single_id]`, `description` explains the contradiction, `contradiction` quotes the conflicting field values.

Asymmetry issues map naturally: `entity_ids=[a_id, b_id]`, `contradiction` shows "A→B='friend' vs B→A='enemy'".

No new response type needed — `ConsistencyIssue` is sufficient for all three sources.

### 4.2 New Request/Response Schemas

**Location**: `apps/api/narrare/kb/consistency_contracts.py` (new)

```python
"""KB Consistency Check service contract — Protocol definitions.

Contracts are written before implementation (RULE-03).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from .worldbuilding_contracts import ConsistencyIssue, WorldbuildingSeverity

if TYPE_CHECKING:
    from uuid import UUID


class ConsistencyCheckRequest(BaseModel):
    """Request to run a consistency check.

    Attributes:
        entity_types: Optional filter — check only specific entity types.
            When None, checks all types present in the project.
        include_entry_internal: Whether to check entry-internal consistency (LLM).
        include_asymmetry: Whether to check relationship asymmetry (algorithmic).
        include_cross_entity: Whether to check cross-entity consistency (LLM via KB-006b).
        refresh: If True, bypass cache and force fresh analysis.
    """

    entity_types: list[str] | None = None
    include_entry_internal: bool = True
    include_asymmetry: bool = True
    include_cross_entity: bool = True
    refresh: bool = False


class ConsistencyCheckResponse(BaseModel):
    """Response from a consistency check.

    Attributes:
        novel_id: The project that was checked.
        entity_count: How many entities were analyzed.
        issues: All consistency issues found, sorted by severity (critical first).
        summary: Breakdown counts by category.
        checked_at: When the check was performed.
    """

    novel_id: str
    entity_count: int
    issues: list[ConsistencyIssue]
    summary: dict[str, int]  # {"entry_internal": 3, "asymmetry": 2, "cross_entity": 1}
    checked_at: str  # ISO datetime string


@runtime_checkable
class KBConsistencyProtocol(Protocol):
    """Protocol for KB consistency checking.

    Combines three analysis sources into a single consistency report:
    - Entry-internal: LLM-based per-entry field contradiction detection
    - Relationship asymmetry: algorithmic reciprocal relationship validation
    - Cross-entity: LLM-based entity-pair contradiction detection (reuses KB-006b)
    """

    async def check(
        self,
        *,
        novel_id: UUID,
        request: ConsistencyCheckRequest,
    ) -> ConsistencyCheckResponse:
        """Run a consistency check on the project's KB.

        Args:
            novel_id: The project to check.
            request: Check options and filters.

        Returns:
            Complete consistency report with all requested issue types.
        """
        ...
```

### 4.3 Asymmetry Result Type

**Location**: `apps/api/narrare/kb/consistency_contracts.py` (same file)

```python
class RelationshipAsymmetry(BaseModel):
    """A single detected relationship asymmetry.

    Attributes:
        source_id: Entity ID of the source in the original relationship.
        source_name: Name of the source entity.
        target_id: Entity ID of the target in the original relationship.
        target_name: Name of the target entity.
        forward_rel_type: The relationship type from source → target.
        reverse_rel_type: The relationship type from target → source (if any).
        expected_inverse: What the inverse should be based on INVERSE_SUGGESTIONS.
        severity: How concerning this asymmetry is.
    """

    source_id: str
    source_name: str
    target_id: str
    target_name: str
    forward_rel_type: str
    reverse_rel_type: str | None
    expected_inverse: str | None
    severity: WorldbuildingSeverity = WorldbuildingSeverity.MINOR
```

---

## 5. Module Map

### 5.1 New Files

Files are listed in implementation order (Layer Ordering).

| # | Layer | File | Purpose | Est. Lines |
|---|-------|------|---------|-----------|
| 1 | Core | `packages/core/narrare_core/prompts/_bundled/kb/en/consistency/system.md` | Entry-internal consistency prompt | ~90 |
| 2 | Backend | `apps/api/narrare/kb/consistency_contracts.py` | Protocol + request/response schemas + asymmetry type | ~100 |
| 3 | Backend | `apps/api/narrare/kb/consistency_analyzer.py` | KBConsistencyAnalyzer — entry-internal LLM analysis (per-entry) | ~150 |
| 4 | Backend | `apps/api/narrare/kb/relationship_asymmetry.py` | RelationshipAsymmetryChecker — pure algorithmic asymmetry detection | ~60 |
| 5 | Backend | `apps/api/narrare/kb/consistency_service.py` | KBConsistencyService — orchestrates all 3 sources + cache | ~100 |
| 6 | Backend | `apps/api/narrare/kb/router_consistency.py` | FastAPI routes (thin delegation) | ~60 |
| 7 | Backend | `apps/api/narrare/kb/consistency_cache.py` | Redis-backed cache wrapper (follows WorldbuildingCache pattern) | ~70 |
| 8 | Frontend | `packages/web/lib/api/consistency.ts` | API types + client function | ~40 |

### 5.2 Modified Files

| # | File | Change | Reason |
|---|------|--------|--------|
| M1 | `apps/api/narrare/kb/worldbuilding_contracts.py` | Add `ENTRY_INTERNAL` + `RELATIONSHIP_ASYMMETRY` to `ConsistencyCategory` enum | New categories for KB-004 issue types |
| M2 | `apps/api/narrare/kb/dependencies.py` | Add `get_consistency_service()` factory | Dependency injection |
| M3 | `apps/api/narrare/kb/__init__.py` | Export consistency module | Package public API |
| M4 | `packages/core/narrare_core/llm/intents.py` | Add `KB_CONSISTENCY = "kb_consistency"` to `LLMIntent` | Needed for PromptComposer routing |
| M5 | `packages/core/narrare_core/prompts/composer.py` | Add `LLMIntent.KB_CONSISTENCY` to `_INTENT_TO_CATEGORY` and `_INTENT_TO_MODE` | Maps intent → prompt directory |
| M6 | `packages/web/components/studio/WorldBuilding.tsx` | Add "Check Consistency" button + panel state | Frontend integration |
| M7 | `tests/unit/api/narrare/kb/test_consistency_service.py` | Service unit tests | RULE-10 |
| M8 | `tests/unit/api/narrare/kb/test_relationship_asymmetry.py` | Asymmetry checker unit tests | RULE-10 |
| M9 | `tests/integration/api/narrare/kb/test_router_consistency.py` | Router integration tests | RULE-10 |

### 5.3 Module Boundary Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                      apps/api/narrare/kb/                           │
│                                                                      │
│  router_consistency.py ──→ consistency_service.py                    │
│                                │                                     │
│                                ├──→ consistency_analyzer.py          │
│                                │       │                             │
│                                │       ├──→ consistency_cache.py     │
│                                │       │                             │
│                                │       ├──→ ModelRegistry            │
│                                │       │    PromptComposer (RULE-02) │
│                                │       │                             │
│                                │       └──→ KBRepository (entry data)│
│                                │                                     │
│                                ├──→ relationship_asymmetry.py        │
│                                │       │                             │
│                                │       └──→ RelationshipRepository  │
│                                │            INVERSE_SUGGESTIONS      │
│                                │                                     │
│                                └──→ worldbuilding_analyzer.py        │
│                                     ._run_phase2()                   │
│                                     (REUSED — no changes)            │
│                                                                      │
│  consistency_contracts.py ← Protocol definition                      │
│  worldbuilding_contracts.py ← ConsistencyCategory (extended)        │
└─────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    packages/core/narrare_core/                       │
│                                                                      │
│  prompts/_bundled/kb/en/consistency/                                 │
│    system.md              ← Entry-internal consistency prompt        │
│                                                                      │
│  llm/                                                                │
│    intents.py              ← KB_CONSISTENCY added                    │
│                                                                      │
│  kb/                                                                 │
│    relationships.py        ← INVERSE_SUGGESTIONS (reused, unchanged)│
└─────────────────────────────────────────────────────────────────────┘
```

### 5.4 Key Principle: Thin Orchestration

```
KBConsistencyService.check()
    │
    ├── Phase 1 (ALWAYS first — free, fast, no LLM)
    │   └── RelationshipAsymmetryChecker.check(novel_id)
    │       → list[RelationshipAsymmetry]
    │       → map to list[ConsistencyIssue]
    │
    ├── Phase 2 (Optional — per-entry LLM)
    │   └── KBConsistencyAnalyzer.analyze_entries(novel_id, entity_types)
    │       → For each entry: build deps → PromptComposer → model → parse
    │       → list[ConsistencyIssue]
    │
    └── Phase 3 (Optional — cross-entity LLM via KB-006b)
        └── WorldbuildingAnalyzer._run_phase2(deps, candidate_pairs)
            → list[ConsistencyIssue]  (existing, unchanged)
```

---

## 6. Data Flow

### 6.1 Full Consistency Check Flow

```
User clicks "Check Consistency"
        │
        ▼
┌────────────────────────────────┐
│  WorldBuilding.tsx              │
│  calls consistencyApi.check()  │
└──────────┬─────────────────────┘
           │ POST /novels/{id}/kb/consistency-check
           ▼
┌────────────────────────────────┐
│  router_consistency.py         │  (thin — RULE-06)
│  service.check(novel_id, req) │
└──────────┬─────────────────────┘
           ▼
┌──────────────────────────────────────────────────────────┐
│  consistency_service.py: check()                          │
│                                                           │
│  1. Check cache (if not refresh)                          │
│     → Cache hit? Return cached ConsistencyCheckResponse   │
│                                                           │
│  2. Phase 1: Asymmetry (always runs first — free)         │
│     → asymmetry_checker.check(novel_id, entity_types)     │
│     → list[ConsistencyIssue]                              │
│                                                           │
│  3. Phase 2: Entry-internal (if requested)                │
│     → consistency_analyzer.analyze_entries(novel_id, ...) │
│     → list[ConsistencyIssue]                              │
│                                                           │
│  4. Phase 3: Cross-entity (if requested)                  │
│     → worldbuilding_analyzer._run_phase2(deps, pairs)     │
│     → list[ConsistencyIssue]                              │
│                                                           │
│  5. Merge + sort by severity (critical → major → minor)   │
│  6. Store in cache (10min TTL)                            │
│  7. Return ConsistencyCheckResponse                       │
└──────────────────────────────────────────────────────────┘
```

### 6.2 Phase 1: Relationship Asymmetry (Algorithmic)

```
relationship_asymmetry.py: check()

  1. Fetch all relationships for the novel:
     rel_repo.get_adjacency_map(novel_id)
     → adjacency: dict[str, set[str]]  (entity_id → connected entity_ids)

  2. For each entity_id in adjacency:
     rels = rel_repo.list_for_entry(entity_id)
     For each outgoing relationship (source=entity_id):
       a. Look up expected inverse from INVERSE_SUGGESTIONS[rel.rel_type]
       b. Check if target has any relationship back to source
          - If no reverse relationship exists → flag as "missing inverse"
          - If reverse exists but rel_type doesn't match expected inverse → flag as "asymmetric"

  3. Build RelationshipAsymmetry objects:
     - source_id, target_id, forward_rel_type, reverse_rel_type, expected_inverse
     - Deduplicate: only flag each (A, B) pair once (not both (A,B) and (B,A))

  4. Map to ConsistencyIssue:
     - category = RELATIONSHIP_ASYMMETRY
     - entity_ids = [source_id, target_id]
     - contradiction = "A→B='{forward}' vs B→A='{reverse}' (expected '{expected}')"
     - severity = MINOR (asymmetry is not a critical error)

  5. Return list[ConsistencyIssue]
```

**Key Design Decision**: Asymmetry uses `MINOR` severity by default because asymmetric relationships are often intentional (e.g., "A mentors B" without "B is mentored by A" is valid if B doesn't know yet). The user decides whether to act on it.

### 6.3 Phase 2: Entry-Internal Consistency (LLM)

```
consistency_analyzer.py: analyze_entries()

  1. List all entities (reusing worldbuilding_entity_assembly.list_entities):
     entities = list_entities(kb_repo, novel_id, entity_types)

  2. For each entity:
     a. Build entry_content dict:
        - name, entity_type, metadata (all field values), body, tags
     b. Build template_structure (field keys → labels) using get_schema()
      c. Build prompts via PromptComposer:
         - PromptContext(language="en", mode=KB_CONSISTENCY, entity_name=entity.name, entity_type=entity.entity_type)
         - composed = composer.build(KB_CONSISTENCY, ctx)
      d. Resolve model: model = registry.get_model(config)
      e. Run single LLM call:
         - prompt = composed.user
         - Parse structured JSON response → list of entry-internal issues
     f. Map to ConsistencyIssue:
        - category = ENTRY_INTERNAL
        - entity_ids = [entity_id]
        - entity_names = [entity.name]
        - contradiction = "age='25' contradicts birth_year='1990' given story_set_in='2024'"

  3. Return all issues across all entries
```

**Performance Note**: Per-entry LLM calls can be batched. For N entities, this makes N sequential LLM calls. Optimization: run in parallel with `asyncio.gather(..., limit=MAX_CONCURRENT)` with a concurrency limit of 5 to avoid rate limiting. This is a future optimization — the MVP runs sequentially.

### 6.4 Phase 3: Cross-Entity (Reuse KB-006b)

```
consistency_service.py delegates to WorldbuildingAnalyzer._run_phase2()

  1. Build WorldbuildingDeps for the novel:
     - Reuse worldbuilding_entity_assembly helpers
     - entities, adjacency, summaries, relationships, template structures

  2. Get candidate pairs from Phase 1 of worldbuilding:
     - For KB-004, we need entity pairs to check
     - Option A: Re-run Phase 1 to get candidate_pairs (expensive — 2 LLM calls)
     - Option B: Generate pairs from adjacency map (free, covers connected entities)
     - SELECTED: Option B — use adjacency map to generate pairs from connected entities
       → Only check entities that actually have relationships (most likely to have cross-entity issues)

  3. Call WorldbuildingAnalyzer._run_phase2(deps, pairs):
     - This is the EXISTING method — no changes needed
     - Returns list[ConsistencyIssue] with existing categories (GEOGRAPHY, POLITICS, etc.)

  4. Return issues as-is (already in ConsistencyIssue format)
```

### 6.5 Merge and Sort

```python
# In consistency_service.py

all_issues: list[ConsistencyIssue] = []
all_issues.extend(asymmetry_issues)       # Phase 1
all_issues.extend(entry_internal_issues)  # Phase 2
all_issues.extend(cross_entity_issues)    # Phase 3

# Sort by severity (critical first, then major, then minor, then info)
severity_order = {"critical": 0, "major": 1, "minor": 2, "info": 3}
all_issues.sort(key=lambda i: severity_order.get(i.severity.value, 1))

# Build summary
summary = {
    "entry_internal": sum(1 for i in all_issues if i.category == ConsistencyCategory.ENTRY_INTERNAL),
    "asymmetry": sum(1 for i in all_issues if i.category == ConsistencyCategory.RELATIONSHIP_ASYMMETRY),
    "cross_entity": sum(1 for i in all_issues if i.category not in (
        ConsistencyCategory.ENTRY_INTERNAL,
        ConsistencyCategory.RELATIONSHIP_ASYMMETRY,
    )),
}
```

---

## 7. Prompt Strategy

### 7.1 New Prompt: Entry-Internal Consistency

**Location**: `packages/core/narrare_core/prompts/_bundled/kb/en/consistency/system.md`

```
---
prompt_type: kb
prompt_language: en
prompt_version: "1.0.0"
---

## System Prompt

You are a Knowledge Base consistency analyst. Your job is to examine a single KB entry's fields and identify **internal contradictions** — values that logically conflict with each other within the same entry.

### Context

#### Entity Type
{{entity_type}}

#### Template Structure
The fields this entity should have:

{{template_structure}}

#### Current Entry Content
{{entry_content}}

### Analysis Instructions

1. **Cross-Field Contradictions**: Compare values across fields:
   - Do numeric values create impossible combinations? (e.g., age=25 + birth_year=1990 + story_set_in=2024 → age should be 34)
   - Do text descriptions contradict each other? (e.g., personality="cautious" + typical_action="rushes into danger")
   - Do relationships between fields break logical rules? (e.g., rank="private" + commands=["army", "navy"])

2. **Temporal Consistency**: If dates, ages, or durations appear:
   - Are timelines internally consistent?
   - Do career/event sequences make chronological sense?

3. **Constraint Violations**: Do field values violate their own stated rules?
   - If a system entry defines "costs 10 mana" and a character entry using that system has "max_mana=5"

### Output Format

Return a JSON object:
{
  "issues": [
    {
      "field_keys": ["<field1>", "<field2>"],
      "description": "<what the contradiction is>",
      "contradiction": "<field1_value> contradicts <field2_value> because...>",
      "suggested_resolution": "<how to fix>",
      "severity": "critical" | "major" | "minor",
      "confidence": 0.0-1.0
    }
  ],
  "assessment": "<1 sentence overall internal consistency assessment>"
}

### Quality Rules

- Maximum 5 issues per entry — be selective.
- Minimum confidence threshold: 0.7. Only flag genuine contradictions.
- severity "critical" = the entry is unusable as-is (e.g., contradictory core identity)
- severity "major" = significant contradiction that could confuse readers
- severity "minor" = subtle inconsistency that might be intentional
- Never flag intentionally vague or mysterious fields — writers leave things ambiguous on purpose.
- Do NOT suggest improvements — only flag contradictions.

### Do NOT

- Do NOT check for missing fields (that's the improve analyzer's job)
- Do NOT suggest new content — only flag contradictions
- Do NOT compare against other entries (that's cross-entity consistency)
- Do NOT flag fields that are simply empty — only flag conflicting non-empty values
```

### 7.2 Prompt Variables

| Variable | Source | Example |
|----------|--------|---------|
| `{{entity_type}}` | `entry.entity_type` | `"character"` |
| `{{template_structure}}` | `get_schema(entity_type).model_fields` → dict of field_key → label | `{"name": "Name", "age": "Age", "birth_year": "Birth Year", ...}` |
| `{{entry_content}}` | `entry.metadata_` + `entry.body` + `entry.tags` | `{"name": "Elara", "age": 25, "birth_year": 1990, ...}` |

### 7.3 LLM Intent Registration

Add to `packages/core/narrare_core/llm/intents.py`:

```python
class LLMIntent(StrEnum):
    # ... existing intents ...
    KB_CONSISTENCY = "kb_consistency"
```

Add to intent mappings:
```python
LLMIntent.KB_CONSISTENCY: IntentCategory.KB,
```

Add to `packages/core/narrare_core/prompts/composer.py`:

```python
_INTENT_TO_CATEGORY[LLMIntent.KB_CONSISTENCY] = "kb"
_INTENT_TO_MODE[LLMIntent.KB_CONSISTENCY] = "consistency"
```

---

## 8. Frontend Integration

### 8.1 Entry Point

The consistency check is accessible from the WorldBuilding page toolbar:

| Entry Point | Component | Trigger |
|-------------|-----------|---------|
| **Toolbar in WorldBuilding** | "Check Consistency" button next to "Analyze Worldbuilding" | Always visible |

### 8.2 Reuse Strategy

**Do NOT build a new panel.** Reuse the existing `WorldbuildingAnalysisPanel`'s **Consistency tab**. The consistency check response (`ConsistencyCheckResponse`) maps directly to the same `ConsistencyIssue` type that the worldbuilding panel already renders.

Integration approach:
1. Add a "Check Consistency" button in the WorldBuilding toolbar (next to "Analyze")
2. On click, call the consistency check API
3. Open the existing `WorldbuildingAnalysisPanel` in a "consistency-only" mode:
   - Hide the Gaps and Connections tabs
   - Show only the Consistency tab
   - Display all issues grouped by category (entry-internal, asymmetry, cross-entity)

This avoids duplicating the consistency issue rendering UI.

### 8.3 State Management

```typescript
// In WorldBuilding.tsx
const [consistencyResult, setConsistencyResult] =
    useState<ConsistencyCheckResponse | null>(null);

// "Check Consistency" button handler
const handleConsistencyCheck = async () => {
    const result = await consistencyApi.check(novelId, {
        include_entry_internal: true,
        include_asymmetry: true,
        include_cross_entity: true,
    });
    setConsistencyResult(result);
    // Open analysis panel in consistency mode
    setShowWorldbuildingPanel(true);
    setPanelMode("consistency"); // new mode: "analysis" | "consistency"
};
```

### 8.4 API Layer

**Location**: `packages/web/lib/api/consistency.ts`

```typescript
interface ConsistencyCheckRequest {
    entity_types?: string[] | null;
    include_entry_internal?: boolean;
    include_asymmetry?: boolean;
    include_cross_entity?: boolean;
    refresh?: boolean;
}

interface ConsistencyCheckResponse {
    novel_id: string;
    entity_count: number;
    issues: ConsistencyIssue[];  // Reuse existing type from worldbuilding.ts
    summary: Record<string, number>;
    checked_at: string;
}

export const consistencyApi = {
    check: (novelId: string, options?: ConsistencyCheckRequest) =>
        fetchApi<ConsistencyCheckResponse>(
            `/novels/${novelId}/kb/consistency-check`,
            { method: "POST", body: JSON.stringify(options ?? {}) }
        ),
};
```

---

## 9. RULE-XX Compliance Matrix

| Rule | Status | How KB-004 Satisfies It |
|------|--------|-------------------------|
| **RULE-01b** | ✅ | No direct LLM imports. `KBConsistencyAnalyzer` resolves model from `ModelRegistry` and uses PromptComposer. No pydantic-ai Agent needed — single-shot LLM call via `model.generate()` pattern (same as improve_analyzer). |
| **RULE-02** | ✅ | All prompts via `PromptComposer.build(LLMIntent.KB_CONSISTENCY, ctx)` in `consistency_analyzer.py`. Prompt content in `prompts/_bundled/kb/en/consistency/system.md`. No f-strings. |
| **RULE-03** | ✅ | `KBConsistencyProtocol` in `consistency_contracts.py` is written before any implementation. |
| **RULE-04** | ✅ | File sizes respected: analyzer ~150 lines, asymmetry ~60 lines, service ~100 lines, router ~60 lines, contracts ~100 lines, cache ~70 lines. |
| **RULE-05** | ✅ | Module boundaries: new files in `apps/api/narrare/kb/` (backend), `packages/core/narrare_core/prompts/` (prompt). No cross-boundary violations. |
| **RULE-06** | ✅ | One responsibility per file: router (delegates), service (orchestrates 3 sources), analyzer (LLM per-entry), asymmetry (algorithmic check), cache (TTL), contracts (protocols + schemas). |
| **RULE-07** | ✅ | Dependency direction: router → service → (analyzer, asymmetry_checker, worldbuilding_analyzer). No imports from apps/ to core/. |
| **RULE-08** | ✅ | Redis via `SessionCacheProtocol` (same adapter as worldbuilding). No new external services. |
| **RULE-09** | ✅ | All public functions fully typed. No `Any` in contracts. Reuses `ConsistencyIssue` (Pydantic model). |
| **RULE-10** | ✅ | Tests planned: service unit tests, asymmetry unit tests, router integration tests. Coverage thresholds: core 90%, api 80%. |
| **RULE-11** | ✅ | All exception paths: log with structlog, re-raise as typed errors. No bare `except: pass`. |
| **RULE-12** | ✅ | Service layer is the only public API. `KBConsistencyProtocol` callable from WebUI, MCP, A2A, CLI. |
| **RULE-13** | ✅ | Future streaming: `KBConsistencyProtocol.check()` can accept `stream: bool` without breaking callers. Currently non-streaming (matches KB-003/KB-006b pattern). |
| **RULE-14** | ✅ | No DB model changes — consistency check is read-only. |
| **RULE-16** | ✅ | Frontend i18n: new translations for consistency check UI text. |
| **RULE-17** | ✅ | API-Frontend contract: TypeScript types in `consistency.ts` match Pydantic schemas. |
| **RULE-18** | ✅ | No hardcoded model/provider. Config via `ResolvedModelConfig` from DI. |
| **RULE-19** | ✅ | `SessionDep` used in `dependencies.py` factory. |
| **RULE-20** | ✅ | Complete implementation: no stubs, no TODOs, no half-implementations. |

---

## 10. Work Plan

### 10.1 Layer Ordering

Implementation follows the dependency chain: **Core → Backend → Frontend**.

| Phase | Step | Task | Files | Depends On | Est. Complexity |
|-------|------|------|-------|------------|-----------------|
| **Core** | C1 | Add `KB_CONSISTENCY` intent to `LLMIntent` | `intents.py` | — | ★☆☆ (trivial) |
| **Core** | C2 | Add intent→category/mode mappings to `composer.py` | `composer.py` | C1 | ★☆☆ (trivial) |
| **Core** | C3 | Write entry-internal consistency prompt | `prompts/_bundled/kb/en/consistency/system.md` | — | ★★★ (prompt engineering) |
| **Backend** | B1 | Extend `ConsistencyCategory` enum | `worldbuilding_contracts.py` | — | ★☆☆ (trivial) |
| **Backend** | B2 | Define `KBConsistencyProtocol` + schemas | `consistency_contracts.py` | B1 | ★★☆ (definitional) |
| **Backend** | B3 | Implement `ConsistencyCache` | `consistency_cache.py` | — | ★☆☆ (cache wrapper — copy WorldbuildingCache) |
| **Backend** | B4 | Implement `RelationshipAsymmetryChecker` | `relationship_asymmetry.py` | B1 | ★★☆ (algorithmic) |
| **Backend** | B5 | Implement `KBConsistencyAnalyzer` | `consistency_analyzer.py` | C3, B1 | ★★★ (LLM orchestration) |
| **Backend** | B6 | Implement `KBConsistencyService` | `consistency_service.py` | B2, B3, B4, B5 | ★★☆ (orchestration) |
| **Backend** | B7 | Add DI factory | `dependencies.py` | B6 | ★☆☆ (wiring) |
| **Backend** | B8 | Implement router | `router_consistency.py` | B6, B7 | ★☆☆ (thin router) |
| **Backend** | B9 | Write asymmetry unit tests | `test_relationship_asymmetry.py` | B4 | ★★☆ (testing) |
| **Backend** | B10 | Write service unit tests | `test_consistency_service.py` | B6 | ★★★ (testing) |
| **Backend** | B11 | Write router integration tests | `test_router_consistency.py` | B8 | ★★☆ (testing) |
| **Frontend** | F1 | Define TypeScript types + API client | `consistency.ts` | B2 | ★★☆ (definitional) |
| **Frontend** | F2 | Integrate into WorldBuilding.tsx | `WorldBuilding.tsx` | F1 | ★★☆ (integration) |
| **Frontend** | F3 | Add i18n translations | `messages/en/studio.json` | F2 | ★☆☆ (text) |

### 10.2 Dependency Graph

```
C1 ──→ C2
             ↘
C3 ──────────→ B5 ──→ B6 ──→ B7 ──→ B8
              │       │              │
B1 ──→ B2 ──→│       │              │
              │       │              │
B3 ──────────────────→│              │
              │       │              │
B4 ──────────────────→│              │
                      │              │
                      B9             B10
                                     │
                                     B11

B2 ──→ F1 ──→ F2 ──→ F3
```

### 10.3 Parallelization Opportunities

| Parallel Group | Tasks | Specialist |
|----------------|-------|------------|
| **Batch 1** | C1, C2, C3, B1 | Core + Backend (independent) |
| **Batch 2** | B2, B3, B4 | Backend (after B1) |
| **Batch 3** | B5, B9 (partial) | Backend (after C3, B1) + Testing |
| **Batch 4** | B6, B7, B8 | Backend (after B2-B5) |
| **Batch 5** | B9, B10, B11 | Testing (after B4, B6, B8) |
| **Batch 6** | F1, F2, F3 | Frontend (after B2) |

### 10.4 Estimated Total Complexity

| Layer | Files | Est. Lines | Complexity |
|-------|-------|-----------|------------|
| Core | 1 new, 2 mod | ~90 lines prompt + ~10 lines intent | ★★☆ |
| Backend | 7 new, 3 mod | ~540 lines + ~300 lines tests | ★★★ |
| Frontend | 1 new, 1 mod | ~40 lines API + ~50 lines integration | ★★☆ |
| **Total** | **9 new, 6 mod** | **~1030 lines** | |

### 10.5 Definition of Done

- [ ] All contracts (`KBConsistencyProtocol` + schemas) defined and reviewed
- [ ] Entry-internal consistency prompt written and reviewed for quality
- [ ] `RelationshipAsymmetryChecker` detects asymmetric relationships correctly
- [ ] `KBConsistencyAnalyzer` produces entry-internal issues per entry
- [ ] `KBConsistencyService` orchestrates all 3 sources, merges results
- [ ] Cache works with 10min TTL, invalidation on `refresh=True`
- [ ] Router endpoint returns `ConsistencyCheckResponse`
- [ ] `ConsistencyCategory` enum extended with `ENTRY_INTERNAL` + `RELATIONSHIP_ASYMMETRY`
- [ ] Frontend "Check Consistency" button works and reuses analysis panel
- [ ] All RULE-XX constraints satisfied (see compliance matrix)
- [ ] No workarounds, no TODOs, no half-implementations

---

## Appendix A: ConsistencyCache Design

Follows the exact pattern of `WorldbuildingCache` in `worldbuilding_cache.py`:

```python
class ConsistencyCache:
    """Redis-backed cache for consistency check results."""

    def __init__(self, cache: SessionCacheProtocol) -> None:
        self._cache = cache

    def _key(self, novel_id: str, entity_types_hash: str = "") -> str:
        return f"kb:consistency:{novel_id}{entity_types_hash}"

    async def get(self, novel_id: str, entity_types_hash: str = "") -> str | None: ...
    async def set(self, novel_id: str, value: str, entity_types_hash: str = "") -> None: ...
    async def delete(self, novel_id: str, entity_types_hash: str = "") -> None: ...
    async def delete_all(self, novel_id: str) -> None: ...
```

Key prefix: `kb:consistency:` — isolated from `kb:worldbuild:` and `kb:improve:`.

## Appendix B: Candidate Pair Generation for Phase 3

For Phase 3 (cross-entity reuse), the service generates candidate pairs from the relationship adjacency map instead of re-running Worldbuilding Phase 1:

```python
async def _generate_candidate_pairs(
    novel_id: UUID,
    rel_repo: RelationshipRepositoryProtocol,
    max_pairs: int = 15,
) -> list[tuple[str, str]]:
    """Generate entity pairs from existing relationships for cross-entity check."""
    adjacency = await rel_repo.get_adjacency_map(novel_id)
    pairs: list[tuple[str, str]] = []
    seen: set[frozenset[str]] = set()

    for entity_id, connected in adjacency.items():
        for other_id in connected:
            pair = frozenset({entity_id, other_id})
            if pair not in seen:
                seen.add(pair)
                pairs.append((entity_id, other_id))
                if len(pairs) >= max_pairs:
                    return pairs
    return pairs
```

This ensures we only check entity pairs that have actual relationships — the most likely source of cross-entity consistency issues.

## Appendix C: SSE Streaming — Deferral Rationale

KB-004 does NOT use SSE streaming for MVP, matching KB-003 and KB-006b. Rationale:

1. **Existing pattern**: All KB analysis features use REST POST → full response.
2. **Analysis, not generation**: Consistency checking is a one-shot computation.
3. **RULE-13 compliance**: `KBConsistencyProtocol.check()` can accept `stream: bool` in future without breaking callers.
4. **Progress reporting**: If SSE is added later, the service can emit progress events: "Checking asymmetry (5 pairs)...", "Analyzing entry 3/12...", "Running cross-entity check..."

---

> **Specification approved by**: Architecture Specialist
> **Date**: 2026-05-26
> **Next review**: After asymmetry checker + analyzer implementation (Steps B4, B5)
