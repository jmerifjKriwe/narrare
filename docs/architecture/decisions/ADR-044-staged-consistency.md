# ADR-044 — Staged Multi-Agent Consistency Pipeline

> **Status:** ✅ Implemented
> **Date:** 2026-06-12
> **Deciders:** Architecture Agent, User
> **Supersedes:** —
> **Resolves:** FIND-009 (Timeline/Graph Consistency Context Gap)

---

## Context

### Current State

The consistency checker (CONS-001) runs as a single-pass LLM call: the `ConsistencyCheckerService` assembles chapter texts, KB entity summaries, and timeline events into compact text strings, then passes them to `ConsistencyAgent` in one shot. The agent must simultaneously:

1. Extract implicit facts from unstructured prose
2. Compare those facts against explicit KB data
3. Detect temporal contradictions (sequencing, durations, ages)
4. Identify world-rule violations, plot holes, and character inconsistencies
5. Assess severity and suggest fixes

### Problem

Two interrelated root causes:

**RC-1: Data pipeline information loss.** The `timeline_fetch.py` bridge reduces rich `TimelineEvent` records (with `timestamp_normalized`, `temporal_order`, `chapter_id`, `character_refs`, `location_ref`, `causes`, `consequences`, `source`, `confidence`, `is_confirmed`) to four flat fields: `event_name`, `timestamp`, `character`, `location`. Similarly, KB relationships are rendered as `source → [label] → target` strings without provenance, confidence, or change semantics (FIND-009). The LLM cannot reason about what it never receives.

**RC-2: Single-pass cognitive overload.** One agent does everything: fact extraction, cross-referencing, contradiction detection, and severity assessment. This produces shallow extraction (the agent optimizes for contradictions, not thorough fact extraction) and unreliable provenance tracking (no structured intermediate representation to reason about *why* a fact exists or how confident it is).

### Evidence

- `timeline_fetch.py:58-76` drops `temporal_order`, `causes`, `consequences`, `source`, `confidence`, and chapter provenance.
- `prompt_builder.py:110-145` formats timeline as `- [timestamp] "name" — character; location`, omitting normalized order and source chapter.
- `consistency_agent.py` has no intermediate fact representation — facts are implicit in the LLM's internal reasoning.
- FIND-009 audit finding confirms: "each consumer chooses its own compact text format, and important coherence metadata is lost before the model can reason about it."

### Constraints

- **RULE-01b**: Agents only in `core/agents/`. No direct `pydantic_ai.Agent` outside.
- **RULE-02**: Prompts built in `core/prompts/`. No f-string prompt assembly.
- **RULE-03**: Contract (Protocol) before implementation.
- **RULE-04**: File size limits. Service ≤ 300 lines, Agent definition ≤ 200 lines.
- **RULE-12**: Service Layer is the only public API. External interface unchanged.
- **RULE-13**: Streaming + non-streaming share one interface.
- **RULE-20**: No half-implementations. Build it properly or don't build it.
- **RULE-22**: Cross-feature coherence gate — integration contract required.
- **ADR-032**: Pydantic Evals as evaluation SSOT for both stages.

---

## Decision Drivers

- **FIND-009 resolution**: Timeline/graph context must preserve provenance, confidence, causality, and change semantics.
- **Fact extraction quality**: Structured intermediate representation enables more reliable contradiction detection.
- **Reusability**: A general-purpose `FactExtractorAgent` serves CONS-001, KB-007, and ANAL-005.
- **Backward compatibility**: `ConsistencyCheckerProtocol` external interface must remain unchanged.
- **SSE progressive results**: Frontend already uses SSE; staged pipeline enables stage-by-stage progress.
- **RULE-04 compliance**: Each agent ≤ 200 lines. Service orchestration may need modularization.
- **Token budget**: Enriched facts may increase prompt size; need budget-aware serialization.

---

## Options Considered

### Option A — Multi-Agent Staged Pipeline (FactExtractorAgent → Enriched ConsistencyAgent)

Introduce a general-purpose `FactExtractorAgent` (Stage 1) that extracts structured `ExtractedFact` records with source provenance, evidence quotes, confidence, and subject/predicate/object triples from chapter prose and KB data. Then feed these enriched facts to an enhanced `ConsistencyAgent` (Stage 2) that focuses purely on contradiction detection and severity assessment.

**Pros:**
- Separation of concerns: extraction vs. analysis — each agent has a focused task.
- Structured `ExtractedFact` intermediate representation preserves provenance, source chapter, confidence, and evidence-backed fact triples.
- `FactExtractorAgent` is reusable: KB-007 (entity extraction from chapters), ANAL-005 (coreference resolution), future features.
- Enables `TimelineEventEnvelope` with provenance — directly addresses FIND-009.
- Stage-by-stage SSE progress (e.g., "Extracting facts... → Checking consistency...").
- Each agent stays well under RULE-04 limits (focused responsibility).
- ADR-032 evals can validate each stage independently.

**Cons:**
- Two LLM calls instead of one (higher latency and cost).
- Need new `ExtractedFact` type, `TimelineEventEnvelope` type, and `FactExtractorDeps`.
- Service orchestration more complex — may need modularization for RULE-04.
- More test surface (two agents + orchestration + integration).

### Option B — Enriched Single-Pass with Better Prompting

Keep the single-agent architecture but enrich the prompt context: add `TimelineEventEnvelope` types to `ConsistencyDeps`, improve the prompt builder to include provenance and confidence metadata, and add a deterministic pre-extraction step (regex/rule-based) for structured facts.

**Pros:**
- Minimal architecture change — no new agent.
- Lower latency (one LLM call).
- Less implementation work.

**Cons:**
- Does not address RC-2 (cognitive overload): one agent still does everything.
- Deterministic pre-extraction is limited in coverage — cannot extract implicit facts from prose.
- Not reusable for KB-007 or ANAL-005 — those need a proper extraction agent.
- FIND-009 provenance gap is only partially addressed (prompt-level enrichment, not structured IR).
- Violates architectural discipline: "the first idea" without proper alternatives analysis.
- If extraction quality is insufficient, would need to add the agent anyway (rework).

### Option C — External NLP Pipeline (spaCy/NER → Agent)

Use spaCy or a dedicated NER model for deterministic fact extraction (Stage 1), then pass structured facts to ConsistencyAgent (Stage 2).

**Pros:**
- Deterministic extraction — no LLM cost for Stage 1.
- Fast — spaCy is local and fast.

**Cons:**
- ADR-021 already established the tiered hybrid strategy: deterministic where possible, LLM where needed. spaCy NER cannot extract narrative facts (character motivations, plot implications, temporal contradictions).
- Requires maintaining an NLP pipeline that goes far beyond ADR-021's scope.
- Not reusable for the LLM-level extraction needed by KB-007 and ANAL-005.
- Violates the "build properly" principle: we'd build a deterministic pipe that handles only the easy cases, then need an LLM agent anyway for the hard cases — effectively building Option A with extra steps.

---

## Decision

**We choose Option A: Multi-Agent Staged Pipeline.**

A two-stage pipeline where a general-purpose `FactExtractorAgent` extracts structured `ExtractedFact` records (with source provenance, evidence quotes, confidence, and subject/predicate/object triples) from chapter prose and KB data, then feeds them to an enhanced `ConsistencyAgent` that focuses on contradiction detection. The `TimelineEventEnvelope` type bridges FIND-009 by preserving timeline provenance through the pipeline. `ConsistencyCheckerProtocol` remains externally unchanged. SSE provides stage-by-stage progress.

---

## Rationale

**Why Option A over B:** Option B treats the symptom (missing metadata in prompts) without addressing the root cause (no structured intermediate representation). One agent doing extraction + analysis produces shallow extraction because it optimizes for the downstream task (contradiction detection), not for thorough fact extraction. Option A's separation of concerns produces better extraction quality, which produces better contradiction detection. The structured `ExtractedFact` IR is reusable across features.

**Why Option A over C:** spaCy/NER handles named entity recognition, not narrative fact extraction. A character's motivation, a plot implication, or a temporal contradiction requires language understanding, not token classification. Option C would build infrastructure that handles only the easy cases, then still need the LLM agent for the hard cases — it's Option A with extra maintenance burden.

**Tradeoffs accepted:**
- Two LLM calls: ~2x latency and cost per consistency check. Acceptable because consistency checks are user-initiated, not real-time (10-45 second range already), and the quality improvement justifies the cost.
- More test surface: each stage needs its own unit + integration tests. Acceptable because ADR-032 evals already define the evaluation infrastructure, and testing two focused agents is easier than testing one monolithic agent.

---

## Consequences

**Positive:**
- Structured `ExtractedFact` IR preserves provenance, source chapter, confidence, and evidence-backed fact triples.
- `TimelineEventEnvelope` resolves FIND-009 with full provenance chain.
- `FactExtractorAgent` is reusable for KB-007 (entity extraction), ANAL-005 (coreference resolution), and future features.
- Stage-by-stage SSE progress improves user experience (visible progress during long checks).
- Each agent stays focused and under RULE-04 limits.
- ADR-032 evals can validate each stage independently.
- `ConsistencyCheckerProtocol` external interface unchanged — no client changes needed.
- Cross-feature integration contract (RULE-22) explicitly defined for Timeline → Consistency data flow.

**Negative / Tradeoffs:**
- Two LLM calls per check: ~2x latency and cost. User-visible wait time increases, but SSE progress mitigates perceived delay.
- `ExtractedFact` and `TimelineEventEnvelope` are new types to maintain.
- Service orchestration complexity increases: may require `consistency_orchestrator.py` for RULE-04.
- Larger test surface: two agents + orchestrator + integration.

**Constraints introduced:**
- **RULE-01b**: `FactExtractorAgent` must live in `core/agents/` and follow `NarrareAgent` pattern.
- **RULE-02**: Fact extraction prompt must be a bundled template in `core/prompts/_bundled/`.
- **RULE-03**: Contracts for `FactExtractorAgent`, `ExtractedFact`, `TimelineEventEnvelope` before implementation.
- **RULE-04**: Service orchestration may need modularization if `checker_service.py` exceeds 300 lines.
- **RULE-13**: Both stages must support `stream=True` and `stream=False`.
- **RULE-22**: Integration contract for Timeline → Consistency (FIND-009 resolution).

---

## Implementation Notes

### New Types (Core)

```
packages/core/narrare_core/agents/
├── consistency_agent.py          ← EXISTING — Stage 2 agent (enhanced)
├── consistency_types.py          ← EXISTING — add enriched fields to ConsistencyDeps
├── fact_extractor_agent.py       ← IMPLEMENTED — Stage 1 agent (general-purpose)
├── fact_extractor_types.py       ← IMPLEMENTED — ExtractedFact, FactExtractorDeps, FactExtractorOutput
```

### Key Type Definitions

**`ExtractedFact`** (`packages/core/narrare_core/agents/fact_extractor_types.py`):
```python
class ExtractedFact(BaseModel):
    """A single fact extracted from a source, with provenance."""
    fact_type: Literal[
        "character_state", "event", "location_state",
        "relationship", "ability", "timeline_marker",
    ]
    subject: str
    predicate: str
    object_value: str
    chapter_id: str
    evidence_text: str
    confidence: float                 # 0.0-1.0 confidence in extraction accuracy
    temporal_marker: str | None = None
```

**`TimelineEventEnvelope`** (`packages/core/narrare_core/agents/fact_extractor_types.py`):
```python
class TimelineEventEnvelope(BaseModel):
    """Rich timeline event with full provenance — FIND-009 integration contract."""
    event_id: str
    event_name: str
    timestamp_raw: str
    timestamp_normalized: str | None
    temporal_order: int | None
    source_chapter_id: str | None
    character_refs: list[dict[str, str]]  # [{"id": ..., "name": ..., "status": ...}]
    location_ref: dict[str, str] | None   # {"id": ..., "name": ..., "status": ...}
    causes: list[str]
    consequences: list[str]
    source: str | None
    confidence: float
    is_confirmed: bool
    kb_entity_status: dict[str, str]  # active/deprecated/unknown status by entity name
```

### Agent Pipeline

```
Stage 1: FactExtractorAgent
  Input:  chapter_texts + KB entities + TimelineEventEnvelope[] (enriched)
  Output: ExtractedFact[] (subject/predicate/object facts with evidence quotes)

Stage 2: ConsistencyAgent (enhanced)
  Input:  ExtractedFact[] (from Stage 1) + original context for reference
  Output: ConsistencyOutput (issues with enriched conflicting_facts)
```

### Backend Module Layout

```
apps/api/narrare/consistency/
├── contracts.py                  ← ConsistencyCheckerProtocol + orchestrator protocol
├── checker_service.py            ← delegates staged checks to orchestrator
├── consistency_orchestrator.py    ← Stage 1→2 orchestration (RULE-04)
├── orchestrator_helpers.py        ← Stage 2 helper functions (RULE-04)
├── timeline_envelope.py           ← TimelineEvent → TimelineEventEnvelope enrichment
├── timeline_fetch.py              ← timeline retrieval bridge
├── checker_context.py             ← check context collection
├── deps.py                        ← DI wiring for staged pipeline
├── stage_schemas.py               ← ConsistencyStageEvent SSE schema
├── schemas.py                     ← REST request/response models
├── router.py                      ← /check and /check/stream endpoints
├── rule_helpers.py                ← deterministic rule helpers
├── checker_helpers.py             ← service helpers
```

### SSE Stage Events

```python
class ConsistencyStageEvent(BaseModel):
    """SSE event for staged pipeline progress."""
    stage: Literal["extracting_facts", "checking_consistency", "complete"]
    status: Literal["start", "progress", "issue", "complete"]
    progress: float  # 0.0-1.0 within stage
    message: str
    facts_extracted: int | None = None  # populated after stage 1
    issues_found: int | None = None
    issue: ConsistencyIssue | None = None
```

### FIND-009 Integration Contract

```
### Integration Contract: Timeline → Consistency (FIND-009 Resolution)

**Shared data source:** TimelineEvent records (planning module)
**Data direction:** Consistency → reads ← Timeline writes

**On data change** (timeline event updated):
- Consistency receives TimelineEventEnvelope with current source_chapter_id, confidence, and is_confirmed
- Envelope preserves full provenance: causes, consequences, temporal_order
- If event is unconfirmed (is_confirmed=False), it is included with reduced confidence weighting

**On data deletion or missing KB reference**:
- Timeline envelopes preserve source chapter, confidence, and current KB status when available
- Missing refs are marked as `unknown`; deprecated entries remain `deprecated`
- Extracted facts retain `chapter_id` and `evidence_text` for downstream review

**Expected schema:** TimelineEventEnvelope v1 (see type definition above)

**Omitted fields for token budget:** None initially. Budget-aware serialization
truncates metadata dict values, not structural fields.
```

### Cross-Feature Reuse

`FactExtractorAgent` is designed for reuse:
- **KB-007**: Entity extraction from chapters — same extraction pipeline, different `fact_type` filters.
- **ANAL-005**: Coreference resolution — `ExtractedFact` subject/predicate/object triples and evidence quotes can seed coreference chains.
- **Future**: Plot gap detection, worldbuilding expansion, character arc verification.

### Implementation Slices

| Slice | Description | Files | DoD |
|-------|-------------|-------|-----|
| **S0: Data Contract** | Define `ExtractedFact`, `TimelineEventEnvelope`, `FactExtractorDeps`, `FactExtractorOutput`, and `FactExtractorProtocol` | `packages/core/narrare_core/agents/fact_extractor_types.py` | ✅ Types compile and validation tests pass. |
| **S1: FactExtractorAgent** | General-purpose `FactExtractorAgent` (NarrareAgent subclass) with bundled prompt and `FACT_EXTRACT` route | `packages/core/narrare_core/agents/fact_extractor_agent.py`, `packages/core/narrare_core/prompts/_bundled/analysis/en/fact_extraction/system.md`, `packages/core/narrare_core/llm/intents.py`, `packages/core/narrare_core/prompts/route_table.py` | ✅ Agent produces `ExtractedFact[]` from chapter text + KB + timeline. |
| **S2: Enriched ConsistencyAgent** | Enhance `ConsistencyDeps` with `extracted_facts` and `timeline_envelopes`; update consistency prompt to consume enriched input. | `packages/core/narrare_core/agents/consistency_types.py`, `packages/core/narrare_core/agents/consistency_agent.py`, `packages/core/narrare_core/prompts/_bundled/analysis/en/consistency/system.md` | ✅ ConsistencyAgent accepts enriched input while preserving backward compatibility. |
| **S3: Service Orchestration** | Wire Stage 1 → Stage 2 and produce enriched timeline envelopes. | `apps/api/narrare/consistency/consistency_orchestrator.py`, `apps/api/narrare/consistency/orchestrator_helpers.py`, `apps/api/narrare/consistency/timeline_envelope.py`, `apps/api/narrare/consistency/timeline_fetch.py`, `apps/api/narrare/consistency/checker_context.py`, `apps/api/narrare/consistency/checker_service.py` | ✅ Non-streaming staged pipeline returns `ConsistencyResponse`. |
| **S4: SSE Progressive Results** | Stream `ConsistencyStageEvent` progress and final result. | `apps/api/narrare/consistency/stage_schemas.py`, `apps/api/narrare/consistency/router.py`, `apps/api/narrare/consistency/contracts.py`, `apps/api/narrare/consistency/deps.py` | ✅ `POST /consistency/check/stream` streams stage events and `[DONE]`; non-streaming `/check` remains available (RULE-13). |
| **S5: Evals** | ADR-032 eval cases for extraction recall/precision, contradiction recall, false-positive guard, and runtime/smoke execution. | `evals/consistency_models.py`, `evals/datasets/consistency_staged.py`, `evals/evaluators/consistency.py`, `evals/tasks/consistency_smoke.py`, `evals/tasks/consistency_runtime.py`, `evals/tasks/smoke.py`, `evals/tasks/runtime.py` | ✅ Smoke suite reported all 1.00; runtime task uses Narrare agents and `ModelRegistry`. |

### ADR Implementation Completeness Gate (Gate 12)

Implementation completed 2026-06-13. Gate 12 verification:

- [x] All 6 implementation slices (S0-S5) complete and tested
- [x] `FactExtractorAgent` produces structured `ExtractedFact[]` with provenance and evidence quotes
- [x] `TimelineEventEnvelope` preserves timeline provenance, confidence, confirmation, causality, and KB status metadata (FIND-009 resolved)
- [x] `ConsistencyCheckerProtocol` external interface unchanged
- [x] SSE stage events stream correctly through `POST /consistency/check/stream`
- [x] ADR-032 eval cases pass for both stages (`uv run python -m evals run --suite all --mode smoke` reported `consistency_staged` and all suites at 1.00)
- [x] RULE-04 compliance: orchestration and schemas split into focused files
- [x] Cross-feature integration contract documented and validated
- [x] No workarounds or shortcuts in any slice
- [x] Feature spec CONS-001 updated to reflect staged flow

Validation reported by implementation handoff: core slices 57 tests; backend consistency slices 77 tests; eval slice 9 tests; Ruff, Pyright, architecture, prompt checks, and smoke evals passed.

---

## Review Trigger

- [ ] After 3 months — assess extraction quality and latency impact
- [ ] When a third consumer of FactExtractorAgent is added (beyond CONS-001, KB-007, or ANAL-005)
- [ ] When token costs for two-stage pipeline exceed acceptable threshold
- [ ] When a superior extraction model becomes available (e.g., structured output improvements in pydantic-ai)
