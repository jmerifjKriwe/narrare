# FIND-009 — Timeline/graph consistency context remains incomplete

Priority: 🟡 Medium
Status: partially resolved / scope refreshed
Source: CR-04 §1, §2, §4 (refreshed 2026-06-12)

## Current Finding

The original version of this finding said the consistency checker did not consume timeline events at all. That is now stale: confirmed `TimelineEvent` records are fetched by `fetch_timeline_events()`, placed into `ConsistencyDeps.timeline_events`, formatted by `_format_timeline_events()`, and passed to the `analysis/en/consistency` prompt through `timeline_position`.

The remaining finding is narrower: timeline and graph context reach prompts as compact text, but they do not yet preserve enough provenance, graph-edge metadata, deletion/change behavior, or temporal-order evidence to fully satisfy RULE-22 cross-feature coherence.

## Evidence

- `apps/api/narrare/consistency/timeline_fetch.py:23-77` fetches confirmed timeline events and reduces them to `event_name`, `timestamp`, `character`, and `location`.
- `apps/api/narrare/consistency/prompt_builder.py:40-45` maps those events into `timeline_position`, and `prompt_builder.py:110-145` formats compact lines such as `- [Day 5] "Event" — Character; Location`.
- `apps/api/narrare/planning/models.py::TimelineEvent` stores richer fields: `timestamp_normalized`, `temporal_order`, `chapter_id`, `character_refs`, `location_ref`, `causes`, `consequences`, `source`, `confidence`, and `is_confirmed`.
- The prompt-facing compact format omits normalized order, source chapter, causality, confidence, confirmation source, and stale/deleted KB-reference state.
- KB relationship prompts use `source → [label] → target` lines, but omit edge provenance/confidence/change semantics.

## Root Cause

The previous implementation step added a useful timeline bridge, but it did not define a cross-feature integration contract for timeline/graph context. As a result, each consumer chooses its own compact text format, and important coherence metadata is lost before the model or typed consistency result can reason about it.

## User Impact

- Temporal contradictions that depend on source confidence, normalized order, causes/consequences, or deleted/renamed KB references can be missed or under-explained.
- Storyboard, Timeline, KB, and Consistency can drift because no contract defines what happens when referenced entities are renamed, deprecated, or deleted.
- Graph relationships remain useful context text, not a fully auditable reasoning substrate.
- Users may receive a consistency report that says a timeline is coherent even though the underlying stored events contain low-confidence, stale, or contradicted references that were omitted before prompt composition.

## Sustainable Recommendation

Define a Storyboard ↔ KB ↔ Timeline integration contract and a timeline/graph prompt-context envelope. The contract should specify:

1. Which timeline/graph fields must reach consistency prompts.
2. How stale, deleted, deprecated, or renamed KB references are represented.
3. Which conflicts must become typed `ConsistencyIssue` results.
4. How graph edges preserve direction, provenance, and relevance reason.
5. Which compact fields may be omitted for token budget, and how omission is recorded.

## Related CR Tasks

- `CR-AUFG-03-05`
- `CR-AUFG-04-01`
- `CR-AUFG-04-06`
- `CR-AUFG-04-07`
