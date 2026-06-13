# FIND-009 — Timeline/graph consistency context remains incomplete

Priority: 🟡 Medium
Status: ✅ Resolved (ADR-044 implemented)
Source: CR-04 §1, §2, §4 (refreshed 2026-06-12)

## Current Finding

The original version of this finding said the consistency checker did not consume timeline events at all. That is now stale: confirmed `TimelineEvent` records are fetched by `fetch_timeline_events()`, placed into `ConsistencyDeps.timeline_events`, formatted by `_format_timeline_events()`, and passed to the `analysis/en/consistency` prompt through `timeline_position`.

The remaining finding was narrower: timeline and graph context reach prompts as compact text, but they do not yet preserve enough provenance, graph-edge metadata, deletion/change behavior, or temporal-order evidence to fully satisfy RULE-22 cross-feature coherence.

## Resolution

**Resolved by ADR-044: Staged Multi-Agent Consistency Pipeline.** ADR-044 is now implemented through the core fact extraction stage, backend staged orchestrator, SSE stage endpoint, and Pydantic Evals coverage.

ADR-044 introduces:

1. **`TimelineEventEnvelope`** — A rich envelope type that preserves full timeline
   provenance through the consistency pipeline:
   - `timestamp_normalized`, `temporal_order` for reliable ordering
   - `source_chapter_id` for chapter provenance
   - `character_refs` / `location_ref` with `status` field for deletion/change semantics
   - `causes` / `consequences` for causality chains
   - `source`, `confidence`, `is_confirmed` for evidence quality

2. **`ExtractedFact`** — A structured intermediate representation with fact_type,
   subject, predicate, object_value, chapter_id, evidence_text, confidence, and
   temporal_marker. Facts extracted from timeline events preserve reviewable
   provenance through typed evidence quotes and enriched envelopes.

3. **Integration Contract: Timeline → Consistency** — Explicit RULE-22 contract:
   - On data change: Consistency receives `TimelineEventEnvelope` with current provenance
   - On deletion or missing KB refs: envelopes preserve known provenance and mark unresolved refs as `unknown`
   - Budget-aware serialization truncates metadata values, not structural fields

4. **`FactExtractorAgent`** (Stage 1) — General-purpose agent that processes
   `TimelineEventEnvelope[]` into `ExtractedFact[]`, preserving all provenance
   through structured types instead of compact text formatting.

## Evidence (Historical)

- `apps/api/narrare/consistency/timeline_fetch.py:23-77` fetches confirmed timeline events and reduces them to `event_name`, `timestamp`, `character`, and `location`.
- `apps/api/narrare/consistency/prompt_builder.py:40-45` maps those events into `timeline_position`, and `prompt_builder.py:110-145` formats compact lines such as `- [Day 5] "Event" — Character; Location`.
- `apps/api/narrare/planning/models.py::TimelineEvent` stores richer fields: `timestamp_normalized`, `temporal_order`, `chapter_id`, `character_refs`, `location_ref`, `causes`, `consequences`, `source`, `confidence`, and `is_confirmed`.
- The prompt-facing compact format omits normalized order, source chapter, causality, confidence, confirmation source, and stale/deleted KB-reference state.
- KB relationship prompts use `source → [label] → target` lines, but omit edge provenance/confidence/change semantics.

## Root Cause (Historical)

The previous implementation step added a useful timeline bridge, but it did not define a cross-feature integration contract for timeline/graph context. As a result, each consumer chooses its own compact text format, and important coherence metadata is lost before the model or typed consistency result can reason about it.

## User Impact (Historical)

- Temporal contradictions that depend on source confidence, normalized order, causes/consequences, or deleted/renamed KB references can be missed or under-explained.
- Storyboard, Timeline, KB, and Consistency can drift because no contract defines what happens when referenced entities are renamed, deprecated, or deleted.
- Graph relationships remain useful context text, not a fully auditable reasoning substrate.
- Users may receive a consistency report that says a timeline is coherent even though the underlying stored events contain low-confidence, stale, or contradicted references that were omitted before prompt composition.

## Implementation Artifacts

- **ADR**: `docs/architecture/decisions/ADR-044-staged-consistency.md`
- **Feature spec**: `docs/features/consistency/CONS-001-checker.md` (updated with staged flow + FIND-009 contract)
- **New types**: `TimelineEventEnvelope`, `ExtractedFact` implemented in `packages/core/narrare_core/agents/fact_extractor_types.py`
- **Backend integration**: `apps/api/narrare/consistency/timeline_envelope.py`, `consistency_orchestrator.py`, `stage_schemas.py`, and `/consistency/check/stream`
- **Evals**: `evals/datasets/consistency_staged.py`, `evals/evaluators/consistency.py`, `evals/tasks/consistency_smoke.py`, `evals/tasks/consistency_runtime.py`
- **Integration contract**: Documented in ADR-044 §Implementation Notes and CONS-001 spec

## Related CR Tasks

- `CR-AUFG-03-05`
- `CR-AUFG-04-01`
- `CR-AUFG-04-06`
- `CR-AUFG-04-07`
