---
id: CONS-001
title: "Consistency Checker"
status: stable
area: consistency
mvp: false

ui_tooltip: "Find contradictions in characters, timeline, world facts, and plot."
ui_help_short: |
  Finds contradictions across characters, timeline, world facts, and plot logic
  before readers notice them.
ui_help_long: |
  ## Consistency Checker

  Catch inconsistencies before your readers do.

  **What gets checked:**

  **Character Consistency**
  - Behavior matches established personality
  - Voice remains consistent across dialogue
  - Knowledge appropriate to character
  - Abilities and limitations respected
  - Physical traits maintained

  **Timeline Consistency**
  - Events happen in possible sequence
  - Durations make logical sense
  - Character ages align with events
  - Time jumps are acknowledged
  - Past/future events referenced correctly

  **World Consistency**
  - Location properties maintained
  - System rules followed (magic, tech)
  - Faction relationships consistent
  - Geography and travel times match
  - World facts remain stable

  **Plot Consistency**
  - Cause and effect chains complete
  - Character motivations clear
  - Setup receives payoff
  - Loose ends intentional
  - Parallel plots connect logically

  **How it works:**
  1. Select check type(s) or run all
  2. Choose scope (chapter, selection, entire novel)
  3. AI extracts facts and compares (10-45 seconds)
  4. Issues grouped by severity:
     - **Error**: Impossible contradictions
     - **Warning**: Likely inconsistencies
     - **Info**: Minor discrepancies
  5. For each issue:
     - What was found and where
     - Why it's a problem
     - Suggested fixes
  6. Apply fixes or dismiss as intentional

  **Best practices:**
  - Run after major writing sessions
  - Check both within and across chapters
  - Use warnings to guide revision priorities
  - Update KB when fixing inconsistencies
  - Some inconsistencies are intentional (know your story)

  Available in Analysis panel or via CLI:
  `narrare consistency check --novel <id> --type character`
ui_available_in: [analysis, cli]

service: apps/api/narrare/consistency/checker_service.py
contract: apps/api/narrare/consistency/contracts.py#ConsistencyCheckerProtocol
router: apps/api/narrare/consistency/router.py
prompt: core/prompts/_bundled/analysis/en/consistency/system.md
requires: [INFRA-001, INFRA-002, KB-001, KB-007, ADR-044]
---

# CONS-001 — Consistency Checker

## What it does

Comprehensive consistency analysis across characters, timeline, world facts, and plot logic. Extracts facts from Knowledge Base and chapters, compares for contradictions, and flags issues with severity-rated suggestions.

## Why it exists

Readers notice inconsistencies. Characters change personality between chapters, timelines contradict themselves, world rules shift, and plot holes appear. These errors break immersion and trust. Consistency checking catches problems before publication.

## How it works (User perspective)

1. Open Analysis panel → Consistency
2. Select check type(s):
   - **Character**: Behavior, voice, knowledge, abilities
   - **Timeline**: Event sequencing, durations, ages
   - **World**: Locations, systems, factions
   - **Plot**: Cause/effect, motivations, loose ends
3. Choose scope (current chapter, selected, entire novel)
4. Click "Run Consistency Check"
5. AI extracts and compares facts (10-45 seconds)
6. Issues appear grouped by severity:
   - 🔴 Error: Impossible contradictions
   - 🟡 Warning: Likely inconsistencies
   - 🔵 Info: Minor discrepancies
7. Click any issue for:
   - What was found and location
   - Why it's a problem
   - Suggested fixes
8. Apply fix, mark as intentional, or dismiss

## How it works (Technical)

**Architecture per ADR-044:** Two-stage pipeline — 1) `FactExtractorAgent` extracts claims from chapters and KB entities, 2) `ConsistencyAgent` cross-references extracted facts against the Knowledge Base for contradictions. Deterministic pre-filtering via spaCy NER before the LLM stage reduces noise and improves extraction recall.

### Architecture: Staged Multi-Agent Pipeline (ADR-044)

The consistency checker uses a two-stage pipeline (ADR-044) for improved
extraction quality and FIND-009 provenance preservation:

```
Stage 1: FactExtractorAgent (general-purpose)
  Input:  chapter_texts + KB entities + TimelineEventEnvelope[] (enriched)
  Output: ExtractedFact[] (subject/predicate/object facts with evidence quotes)

Stage 2: ConsistencyAgent (enhanced)
  Input:  ExtractedFact[] (from Stage 1) + original context
  Output: ConsistencyOutput (issues with enriched conflicting_facts)
```

**Entry points:** `consistency/router.py` → `POST /consistency/check`, `POST /consistency/check/stream`
**Service:** `ConsistencyCheckerService.check()` in `consistency/checker_service.py`
**Orchestrator:** `ConsistencyOrchestrator` in `consistency/consistency_orchestrator.py`
**Contract:** `ConsistencyCheckerProtocol` in `consistency/contracts.py` (external interface unchanged)
**LLM Intent:** `LLMIntent.CONSISTENCY` (Stage 2), `LLMIntent.FACT_EXTRACT` (Stage 1)

### Key Types

**`ExtractedFact`** — Structured fact with provenance (Stage 1 output):
```python
class ExtractedFact(BaseModel):
    fact_type: Literal["character_state", "event", "location_state",
                       "relationship", "ability", "timeline_marker"]
    subject: str                              # Primary entity the fact is about
    predicate: str                            # Relationship or action
    object_value: str                         # Target value
    chapter_id: str                           # Source chapter identifier
    evidence_text: str                        # Exact supporting quote
    confidence: float                         # 0.0-1.0
    temporal_marker: str | None = None        # Optional temporal reference
```

**`TimelineEventEnvelope`** — Rich timeline event with provenance (FIND-009):
```python
class TimelineEventEnvelope(BaseModel):
    event_id: str
    event_name: str
    timestamp_raw: str
    timestamp_normalized: str | None
    temporal_order: int | None
    source_chapter_id: str | None
    character_refs: list[dict[str, str]]      # id, name, status
    location_ref: dict[str, str] | None       # id, name, status
    causes: list[str]
    consequences: list[str]
    source: str | None
    confidence: float
    is_confirmed: bool
    kb_entity_status: dict[str, str]          # active/deprecated/unknown by name
```

**`ConsistencyIssue`** — Issue with enriched provenance:
```python
class ConsistencyIssue:
    check_type: ConsistencyType               # character, timeline, world, plot
    severity: "error" | "warning" | "info"
    description: str                          # What's inconsistent
    locations: list[str]                      # Where contradictions appear
    conflicting_facts: list[str]              # Conflicting fact statements
    suggestion: str                           # How to fix
    confidence: float                         # 0.0-1.0
```

**`ConsistencyStageEvent`** — SSE stage progress:
```python
class ConsistencyStageEvent(BaseModel):
    stage: Literal["extracting_facts", "checking_consistency", "complete"]
    status: Literal["start", "progress", "issue", "complete"]
    progress: float                           # 0.0-1.0 within stage
    message: str
    facts_extracted: int | None = None        # Populated after Stage 1
    issues_found: int | None = None
    issue: ConsistencyIssue | None = None
```

### SSE Behavior

The endpoint streams `ConsistencyStageEvent` events during the pipeline:

| Event | When | Content |
|-------|------|---------|
| `extracting_facts` | Stage 1 running | Progress %, "Extracting facts from N chapters..." |
| `checking_consistency` | Stage 2 running | Progress %, facts_extracted count |
| `complete` | Pipeline done | Stage completion metadata; final `ConsistencyResponse` follows as a result event |

Non-streaming mode (`stream=False`) runs both stages sequentially and returns the complete response (RULE-13).

### Quality Evaluation (ADR-032)

ADR-044 staged consistency quality is covered by the Pydantic Evals suite
`consistency_staged`:

- Dataset: `evals/datasets/consistency_staged.py`
- Evaluators: `evals/evaluators/consistency.py`
- Smoke/runtime tasks: `evals/tasks/consistency_smoke.py`, `evals/tasks/consistency_runtime.py`

The suite measures Stage 1 extraction recall/precision, Stage 2 contradiction
recall, and an end-to-end temporal contradiction with a known non-contradiction
guard to avoid false positives.

### FIND-009 Integration Contract: Timeline → Consistency

> **Status clarification (ADR-050):** FIND-009 is split into two halves.
>
> * **FIND-009a (resolved by ADR-044):** Timeline→Consistency provenance
>   preservation. The Consistency consumer (this feature) consumes
>   Timeline data via `TimelineEventEnvelope` with full provenance.
> * **FIND-009b (open; closed by ADR-050 P1-B):** KB→Consumer ref
>   lifecycle (rename, deprecate, delete, tombstone) across Timeline,
>   Storyboard, and Chapter frontmatter. The Consistency consumer
>   surfaces these via `RefIntegrityIssue` once the
>   `CrossFeatureRefIndex` is implemented.
>
> ADR-044 is ✅ Implemented, not Proposed. The "Timeline not consumed"
> statement in older reviews is stale for CONS-001 and was stale the
> moment ADR-044 shipped on 2026-06-13.

**Shared data source:** TimelineEvent records (planning module)
**Data direction:** Consistency → reads ← Timeline writes

- **On change**: Consistency receives `TimelineEventEnvelope` with full provenance (causes, consequences, temporal_order, source_chapter_id, confidence). Unconfirmed events included with reduced confidence weighting.
- **On deletion/missing ref**: Timeline envelopes preserve known provenance and mark unresolved KB refs as `unknown`; extracted facts retain `chapter_id` and `evidence_text`.
- **Expected schema:** `TimelineEventEnvelope` v1 (see ADR-044).
- **Token budget**: Budget-aware serialization truncates metadata dict values, not structural fields.

### Cross-Feature Reuse

The `FactExtractorAgent` (Stage 1) is designed for reuse beyond CONS-001:
- **KB-007**: Entity extraction from chapters — same pipeline, different `fact_type` filters.
- **ANAL-005**: Coreference resolution — `ExtractedFact` subject/predicate/object triples and evidence quotes can seed coreference chains.

## Constraints & Edge Cases

- Requires KB to be populated for best results
- Two LLM calls per check (FactExtractor + ConsistencyAgent) — ~2x latency vs single-pass
- Fact extraction may miss implicit information
- Some contradictions are intentional (unreliable narrators)
- Timeline analysis uses enriched `TimelineEventEnvelope` (FIND-009 resolved)
- Character voice analysis requires dialogue samples
- May flag stylistic choices as inconsistencies
- LLM availability required
- False positives possible (human review needed)
- SSE streaming provides stage-by-stage progress during longer checks

## Related Features

- [KB-001](../kb/KB-001-entity-management.md) — Entity definitions
- [KB-007](../kb/KB-007-extraction.md) — Fact extraction (shares FactExtractorAgent)
- [CONS-002](CONS-002-rules.md) — Custom consistency rules
- [PLAN-004](../planning/PLAN-004-timeline.md) — Timeline management (FIND-009 integration)
- [ANAL-005](../analysis/ANAL-005-coreference.md) — Coreference resolution (shares FactExtractorAgent)
- [ADR-044](../../architecture/decisions/ADR-044-staged-consistency.md) — Staged pipeline architecture

## Status & History

- `project-init` — Added to registry as planned feature
- `2026-05-28` — Moved to `in_progress`. Full implementation: ConsistencyAgent (pydantic-ai) with core types, API endpoints, frontend panel. All spec requirements implemented: issue actions (dismiss/mark intentional/copy), loading progress with elapsed timer, rule-based KB pre-check (deterministic, confidence=1.0), scope selector (current/selected/all), fact deduplication. LLMIntent.CONSISTENCY confirmed in intents.py. 22 rule helper tests + 6 service tests.
- `2026-06-12` — ADR-044 proposed: staged multi-agent pipeline (FactExtractorAgent → ConsistencyAgent). FIND-009 integration contract with TimelineEventEnvelope. SSE stage events. Spec updated to reflect staged flow, new types, and cross-feature reuse.
- `2026-06-13` — ADR-044 implemented: core FactExtractor types/agent/prompt and `FACT_EXTRACT` route, backend staged orchestrator + enriched timeline envelopes + SSE endpoint, and Pydantic Evals `consistency_staged` smoke/runtime suite. Validation reported: 57 core tests, 77 backend consistency tests, 9 eval tests; Ruff, Pyright, architecture, prompt checks, and smoke evals passed.
- `2026-06-18` — ADR-050 clarified FIND-009 status: FIND-009a (this consumer) is resolved by ADR-044; FIND-009b (cross-feature ref lifecycle) is open and closed by ADR-050 P1-B `CrossFeatureRefIndex`. The Consistency consumer will surface `RefIntegrityIssue` records from the read-side index once Phase C of ADR-050 lands.

## RULE-XX Compliance

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-01b | ✅ | Both agents are `NarrareAgent` subclasses in `core/agents/` |
| RULE-02 | ✅ | Prompts in `core/prompts/_bundled/analysis/en/` (fact_extraction + consistency) |
| RULE-03 | ✅ | Contracts: `ConsistencyCheckerProtocol` (unchanged), `FactExtractorProtocol` (new) |
| RULE-04 | ✅ | Agent definitions ≤ 200 lines. Service orchestration modularized into `consistency_orchestrator.py` |
| RULE-06 | ✅ | Router delegates to service → orchestrator → agents |
| RULE-07 | ✅ | router → service → orchestrator → agents/core. No upward imports |
| RULE-12 | ✅ | `ConsistencyCheckerProtocol` unchanged — all clients work |
| RULE-13 | ✅ | SSE streaming + non-streaming via same interface |
| RULE-20 | ✅ | Both stages fully implemented, not stubbed |
| RULE-22 | ✅ | FIND-009 integration contract defined. Timeline ↔ Consistency data contract |
