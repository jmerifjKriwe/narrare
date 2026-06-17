---
id: KB-009
title: "KB Entity Merge / Deduplication"
status: stable
area: kb
mvp: false

ui_tooltip: "Find and merge duplicate entities in your Knowledge Base."
ui_help_short: |
  Two-phase deduplication: embedding similarity finds candidate duplicates,
  then AI analysis decides whether to merge, keep distinct, or flag for review.
ui_help_long: |
  ## KB Entity Merge / Deduplication

  Knowledge Bases grow organically as you write and extract entities. Sometimes
  the same character ends up as two entries, or overlapping locations get created
  separately. KB Entity Merge finds these duplicates and helps you resolve them
  intelligently.

  **Two-phase approach:**
  1. **Service-side**: Embedding similarity search identifies candidate pairs
     with a high chance of duplication
  2. **LLM-driven**: Each candidate pair is analysed by the AI, which recommends
     a decision with confidence score and reasoning

  **Decision types per pair:**
  - **merge**: The entities refer to the same thing — merge them into one
  - **distinct**: Different entities — keep separate
  - **uncertain**: Cannot determine — flag for human review

  **Merge strategies** (when decision is `merge`):
  - Keep the best name from either entity
  - Merge field values intelligently (which description to keep, etc.)
  - Preserve alternative names as aliases
  - Merge relationship lists

  **How to use it:**
  1. Open KB panel for your novel
  2. Click "Find Duplicates" or trigger via menu
  3. Select the entity type to check (characters, locations, etc.)
  4. Review AI recommendations for each candidate pair
  5. Accept merges, mark as distinct, or review uncertain cases manually
  6. The merge is irreversible once executed — review carefully

  **Best practices:**
  - Run deduplication after extraction sessions (KB-007) to catch new overlaps
  - Review uncertain decisions manually before bulk-accepting
  - Use specific entity types to reduce false positives
  - Check relationships after merging — they may need reconciliation

  **Use cases:**
  - "Sir Aldric" and "Aldric of Thornwall" are the same character
  - "The Dark Forest" and "Gloomwood" are separate locations
  - "Velvet Rose Tavern" appears as both "Velvet Rose" and "The Rose"

  Merge results are non-reversible — consider reviewing in a copy first.
ui_available_in: [kb]

service: kb/merge_service.py
contract: kb/merge_contracts.py#KBMergeServiceProtocol
router: kb/router_merge.py → POST /novels/{novel_id}/kb/merge
prompt: ADR-048 Mode 2 (agent-internal — no bundled cascade prompt)
requires: [KB-001, INFRA-001, INFRA-002]
---

# KB-009 — KB Entity Merge / Deduplication

## What it does

Intelligent Knowledge Base deduplication: finds candidate duplicate entity
pairs using embedding similarity, then analyses each pair via AI to recommend
merge, keep-distinct, or flag-for-review decisions with structured merge
strategies.

## Why it exists

As Knowledge Bases grow, duplicates inevitably appear — same entity entered
under different names, overlapping extractions, or variant spellings. Manual
deduplication is tedious and error-prone. This feature automates the detection
and decision-making process while keeping the author in control.

## How it works (User perspective)

1. Open KB → select entity type (characters, locations, etc.)
2. Click "Find Duplicates"
3. System finds candidate pairs via embedding similarity
4. AI analyses each pair and produces decisions
5. Review results:
   - ✅ merge — accept merge with suggested strategy
   - ❌ distinct — mark as different entities
   - ⚠️ uncertain — review manually
6. Execute merges (irreversible)

## How it works (Technical)

**Entry point:** `kb/router_merge.py` → `POST /novels/{novel_id}/kb/merge`

**Flow:**
1. Router validates novel existence via `NovelRepository`
2. Resolves model config via `ModelRoutingResolver` using `LLMIntent.KB_CONSISTENCY`
3. Instantiates `KBMergeService` (in `kb/merge_service.py`)
4. Service builds `KBMergeDeps` with entity type + novel metadata
5. Runs `KBMergeAgent` (in `core/agents/merge_agent.py`)
6. Agent returns `MergeOutput` with structured decisions
7. Service maps output to `MergeResponse` schema

**Core Agent:** `KBMergeAgent` — `NarrareAgent[KBMergeDeps, MergeOutput]`
- Deps: `KBMergeDeps` — `entity_type`, `genre`, `language`, optional `context_assembler`
- Output: `MergeOutput` — list of `MergeDecision`, `overall_notes`
- Decision: `MergeDecision` — `pair_id`, `decision` (merge|distinct|uncertain), `confidence`, `reasoning`, optional `merge_strategy`
- Strategy: `MergeStrategy` — `keep_name`, `merge_fields`, `preserve_aliases`, `merge_relationships`
- Uses Output Function pattern (`_process_output`) for structured generation

**Prompts:** ADR-048 Mode 2 — `KBMergeAgent` composes its prompt internally from `KBMergeDeps`. No bundled cascade prompt; user cannot override via PromptComposer.

**Variables:**
- `{{world_context}}` — Related KB entities for context
- `{{entity_type}}` — Type of entities being analysed
- `{{candidate_pairs}}` — The pairs to evaluate
- `{{language}}` — Output language

**Service:** `KBMergeService` in `apps/api/narrare/kb/merge_service.py`
- `analyze_merge_candidates(novel_id, user_id, request) → MergeResponse`
- Uses `NovelRepository` for novel metadata
- Uses `ModelRegistry.get_model()` for LLM model

## Constraints & Edge Cases

- Requires at least 2 candidate pairs for meaningful analysis
- Embedding similarity is a pre-filter — the AI makes the final decision
- Decision `uncertain` requires human review — the system cannot resolve it
- Merge is irreversible — no undo operation
- Merge strategy is a suggestion — the user can override field decisions
- Relationship merging may create orphaned references — review post-merge
- Entity type must match between candidates in a pair

## Related Features

- [KB-001](KB-001-entity-management.md) — KB entity CRUD (entities being merged)
- [KB-007](KB-007-extraction.md) — Entity extraction (source of new duplicates)
- [KB-008](KB-008-knowledge-graph.md) — Knowledge Graph (relationship impact)
- [CONS-001](../consistency/CONS-001-checker.md) — Consistency checking (post-merge)
- [INFRA-002](../infra/INFRA-002-prompt-system.md) — Prompt system for merge prompts
- [INFRA-004](../infra/INFRA-004-embedding-store.md) — Embedding store for similarity search

## Status & History

- `2026-05-31` — Created as part of Phase 6 (new core agent + service + router)
- `2026-05-31` — Status set to stable (backend-only, no UI yet)
