# ADR-040 — KG Consistency / Voice Profile SSOT / Audit Lifecycle

> **Status:** ✅ Accepted
> **Date:** 2026-06-06
> **Deciders:** Architecture Specialist
> **Supersedes:** —
> **Related:** ADR-038, INFRA-013, CONSTRAINTS.md RULE-03/RULE-04/RULE-06/RULE-07/RULE-20/RULE-22

---

## Context

This ADR completes the **P2 architecture specification** for the CR-03 AI Invocation Adoption Contract (INFRA-013 §P2). Four decision drivers require resolution before durable implementation begins:

1. **Project Writing Profile SSOT**: Voice profiles (`character_voice_profiles`) are currently extracted on-the-fly from KB character entities in `writing/_voice_profiles.py`. A `project_writing_profile` provenance exists in `variable_taxonomy.py` but has no concrete model. Tone, style, writing_language, and genre preferences are scattered across KB entities, project settings, and pipeline code without a unified SSOT.

2. **KG/KB consistency evidence**: `context_validators.py` provides `check_orphan_references()` and `check_voice_profile_freshness()`, but there is **no** systematic check that all required KB entity types are present, that KG nodes have matching adoption registry entries, or that graph traversal produces valid adoption evidence for claims.

3. **Audit lifecycle reporting**: `AuditState` enum exists with 7 states, and `FeatureInvocationEvidence` has an `audit_state` field. But there is no aggregate, machine-readable lifecycle report. Debt items in `ai-gate-baseline.json` are hand-maintained. There is no deterministic mapping from evidence to lifecycle state per mode.

4. **Mode runtime proof expansion**: Only P0 representative modes (`new_chapter`, `extend_chapter`, `inline_suggest`) have runtime evidence paths via `WritingPipeline._invocation_adapter.py`. ~24 modes across 5 categories have no runtime evidence infrastructure.

### Current State Summary

| Concern | Exists? | Location | Gap |
|---------|---------|----------|-----|
| Voice profile extraction | ✅ | `writing/_voice_profiles.py` | No SSOT model; KB-derived only |
| Freshness checking | ✅ | `writing/context_validators.py` | Only voice profiles; no entity-type coverage |
| Orphan reference check | ✅ | `writing/context_validators.py` | Checks frontmatter refs only |
| `project_writing_profile` provenance | ✅ | `prompts/variable_taxonomy.py` | Enum entry only; no model or assembly |
| `character_voice_profiles` variable | ✅ | `prompts/variable_registry.py`, route_table | Should variable; no adoption binding |
| AuditState enum | ✅ | `ai_invocation/_enums.py` | 7 states defined |
| FeatureInvocationEvidence.audit_state | ✅ | `ai_invocation/models.py` | Per-invocation only |
| AdoptionReport | ✅ | `scripts/adoption/scorer.py` | No lifecycle reporting |
| ModeScore runtime_verified | ✅ | `scripts/adoption/scorer_modes.py` | Defaults to missing; no probe integration |
| Writing pipeline invocation adapter | ✅ | `writing/_invocation_adapter.py` | Covers new_chapter, extend_chapter, inline_suggest |
| ai-gate-baseline.json | ✅ | `scripts/architecture/` | Hand-maintained debt list |
| ProjectWritingProfile model | ❌ | — | No SSOT |
| KG consistency enricher | ❌ | — | No runtime evidence |
| AuditReport model | ❌ | — | No lifecycle reporting |
| Mode registry `requires_runtime_evidence` | ❌ | — | No forward flag |

---

## Decision Drivers

- **RULE-03**: Contracts and specifications must exist before implementation.
- **RULE-04**: File size limits demand modularization, not compression.
- **RULE-06**: Single responsibility per file — voice profiles, KG consistency, and audit reporting are separate concerns.
- **RULE-07**: Core must not import Backend or Platform; Platform consumes evidence externally.
- **RULE-20**: Static-only adoption is incomplete — runtime evidence is required.
- **RULE-22**: Cross-feature coherence requires that voice profiles, KG data, and audit state share one vocabulary.
- **INFRA-013 §P2 exit criteria**: No hidden profile/voice/KG source outside approved spec; audit lifecycle machine-readable; runtime proof for every mode claiming adopted.
- **Privacy guarantee (ADR-038)**: Evidence never contains raw prompt text or user prose.

---

## Decision 1 — Project Writing Profile SSOT

### Options Considered

#### Option A — Standalone `core/profiles/` module with consolidated `ProjectWritingProfile` model

Create a new Core module `narrare_core/profiles/` with a `ProjectWritingProfile` dataclass/Pydantic model that consolidates:
- `writing_language`, `genre`, `tone`, `style_profile` (project-level settings — sourced from settings layer)
- `character_voice_profiles` (KB-derived — sourced from `extract_voice_profiles()`)
- Freshness metadata per character

The model would be **in-memory only in P2** — assembled on-demand from KB entities + project settings, with no dedicated storage. Adoption evidence records whether profile data was present and fresh when the invocation ran.

**Pros:**
- Creates a single place where "writing profile" is defined — eliminates scattered field definitions.
- Variable `project_writing_profile` (already in `variable_taxonomy.py`) gets a concrete backing type.
- Can produce adoption evidence with a single check: "was the profile assembled and fresh?"
- KB voice extraction becomes a provider/strategy behind the model, not the caller's responsibility.
- Clean RULE-06 ownership: one module owns profile definition and assembly strategy.

**Cons:**
- New module adds surface area and tests in P2.
- Voice extraction logic moves from `writing/` to `profiles/` — requires relocation or adapter.
- P2 is in-memory only; storage requires P3 ADR.

#### Option B — KB-derived only, add `ProjectWritingProfile` model inside `writing/`

Keep voice extraction where it is (`writing/_voice_profiles.py`), but add a `ProjectWritingProfile` data class in `writing/models.py` that prescribes the shape of profile data.

**Pros:**
- Minimal code movement — stays in existing `writing/` module.
- Backward compatible for all existing pipeline callers.
- Less disruption to existing test surface.

**Cons:**
- Mixes profile definition (cross-cutting concern) with writing-specific pipeline logic.
- Makes it harder for non-writing features (analysis, planning) to access profile data without importing writing internals.
- `project_writing_profile` provenance in `variable_taxonomy.py` suggests this is a top-level concept, not a writing sub-concept.
- Risk of RULE-06 drift: `writing/models.py` grows beyond single responsibility.

#### Option C — Backend profile repository with DB storage

Add a new `project_writing_profiles` table in the Backend API layer, with a service and repository. Define profile as a DB-backed entity.

**Pros:**
- Durable storage from day one.
- Clear API for profile CRUD.
- Settings layer integration natural.

**Cons:**
- **Premature for P2**: INFRA-013 explicitly says "before adding durable profile storage or UI."
- Exposes profile data to RULE-07 violation risk if Core needs it.
- Violates constraint: P2 is spec-first, not implementation-first.
- DB migrations add integration test burden before profile shape is validated.

---

**Decision: Option A — Standalone `core/profiles/` module with consolidated `ProjectWritingProfile` model.**

The model is in-memory only in P2. It defines the SSOT shape; storage is deferred to P3.

### Rationale

Voice profiles, tone, style, and writing language share a semantic grouping: they constitute "how this project writes." Currently they are scattered across:
- `writing/_voice_profiles.py` (voice extraction)
- `prompts/variable_taxonomy.py` (provenance classification)
- `prompts/variable_registry.py` (variable registration)
- `writing/models.py` (character_voice_profiles field)
- Project settings (genre, writing_language, tone)

Consolidation into `core/profiles/` ensures:
- One import path for any feature that needs profile data (`from narrare_core.profiles import ProjectWritingProfile`).
- KB voice extraction becomes an internal detail of the profile assembly — interfaces are stable.
- Adoption evidence has a single check: "profile assembled? freshness OK?" instead of multiple scattered checks.
- The `project_writing_profile` provenance in `variable_taxonomy.py` finally has a concrete type.

P2 is in-memory — the profile is assembled at invocation time from existing data sources (KB entities for character voices, settings for genre/tone/language). No storage migration, no API endpoint. This satisfies INFRA-013's requirement to specify before durable implementation.

### Consequences

**Positive:**
- Single import path for profile data across all features (writing, analysis, planning, etc.).
- Adoption evidence surface shrinks from multiple scattered variables to one profile check.
- KB voice extraction becomes a strategy implementation behind the profile contract, making replacement or extension possible without changing callers.

**Negative / Tradeoffs:**
- Existing `writing/_voice_profiles.py` extraction logic must be relocated or adapted into the new module — breaking change for current internal imports.
- P2 is in-memory only; P3 ADR required for storage.
- All 6 WritingPipeline variants that reference `character_voice_profiles` need updates to use the new model.

**Constraints introduced:**
- `core/profiles/` must NOT import from `core/writing/` (RULE-07).
- Profile assembly must be stateless — no hidden in-memory cache in P2 (would become implicit storage).

---

## Decision 2 — KG Consistency Evidence

### Options Considered

#### Option A — `KBConsistencyEnricher` (runtime only)

Add a new enricher in the invocation pipeline that runs after `PreferenceContextEnricher` and before budget resolution. It checks:
1. Required entity types are present in the invocation context (characters, locations, factions).
2. No orphan references to entity IDs missing from the KB.
3. Voice profile freshness (delegates to profile module).
4. KG node → adoption registry mapping (each KG context variable used has a registry entry).

Produces `FeatureInvocationEvidence` with enrichment source `kb_consistency`.

**Pros:**
- Runtime evidence for "KG was consistent when this invocation ran."
- Reuses existing pipeline infrastructure (no new orchestration).
- Graceful degradation: if provider unavailable, records `not_applicable`.

**Cons:**
- Static CI gates still need separate checker — enricher only fires during invocations.
- Heavy for every invocation if KG is large — token/latency concerns.
- KG-to-registry mapping check is complex and may be better as a CI gate.

#### Option B — Platform-level checker (static CI only)

Add a new checker target to `scripts/check_adoption.py` (or a new `scripts/check_kg_consistency.py`) that:
1. Reads the adoption registry for entity/variable requirements per mode.
2. Scans bundled prompt files for actual KG variable usage.
3. Reports mismatches: "mode X requires kb_characters but doesn't use them."
4. Validates that all registered modes have corresponding entity-type expectations.

**Pros:**
- Fast, deterministic, CI-friendly.
- No runtime overhead.
- Catches registry/prompt drift before deployment.

**Cons:**
- Does not prove runtime consistency — static only.
- Cannot detect runtime conditions (orphan entities, stale profiles, empty KB).
- Repeats the CR-03 root cause pattern of static-only gates.

#### Option C — Both (Enricher + Checker) — **Chosen**

**Pros:**
- Runtime evidence for adoption claims ("KG was consistent per invocation").
- Static CI gates prevent registry/mode drift ("mode X expects entities but they're missing from the registry").
- Enricher and checker share a common vocabulary (`KBConsistencyResult` type).
- Checker validates what the enricher cannot (registry ↔ template alignment).

**Cons:**
- Two implementations instead of one.
- Shared type must live in Core (imported by Platform checker, NOT vice versa).

---

**Decision: Option C — Both `KBConsistencyEnricher` (runtime) and Platform-level consistency checker (static CI).**

### Rationale

KG consistency has two dimensions that require different enforcement:
- **Runtime**: "Did this invocation have the entities it needed? Were they fresh?" → Enricher in the pipeline.
- **Static**: "Does the registry still match the prompts? Are all required entity types declared?" → CI checker.

Neither alone is sufficient. The enricher cannot detect registry drift; the checker cannot prove runtime delivery. The `KBConsistencyResult` type that both use is defined in Core (`core/ai_invocation/consistency.py`) and consumed in Platform via structured evidence, not direct import.

### Consequences

**Positive:**
- Adoption evidence for KG consistency becomes a first-class pipeline concern.
- Static CI can block registry/prompt drift before it reaches production.
- Runtime enricher gracefully degrades (no provider → `not_applicable` evidence).

**Negative / Tradeoffs:**
- Adding KG consistency checks to every invocation has token/latency cost — mitigated by making checks optional based on adoption policy (`kb_consistency: required | optional | not_applicable`).
- Two implementations require coordinated tests.

**Constraints introduced:**
- `KBConsistencyResult` type in `core/ai_invocation/consistency.py` — Platform checker consumes evidence, does NOT import Core directly.
- Enricher runs before budget resolution (consistent with KBSuggestedContextEnricher ordering).

---

## Decision 3 — Audit Lifecycle Reporting

### Options Considered

#### Option A — Extend `AdoptionReport` with audit trail

Add `state_history: dict[str, list[StateTransition]]` to `AdoptionReport`, where each mode maps to a list of `(state, timestamp, reason)` tuples. The existing `AdoptionReport` stays the single source of truth.

**Pros:**
- No new report type — single output artifact.
- Existing CI pipeline (check_adoption.py) already produces it.

**Cons:**
- `AdoptionReport` already has 6 fields for scoring — adding lifecycle state mixes concerns.
- `state_history` needs state transitions, which scoring does not track.
- State transitions originate from runtime evidence, not static scoring — data source mismatch.

#### Option B — New `AuditReport` model in Platform **(Chosen)**

Create `scripts/adoption/audit_report.py` with:
```python
@dataclass
class AuditTransition:
    state: str          # AuditState value
    timestamp: str      # ISO-8601
    evidence_id: str | None  # Link to FeatureInvocationEvidence or test probe
    reason: str         # Human-readable trigger

@dataclass
class ModeAuditState:
    mode: str
    current_state: str  # Latest AuditState
    transitions: list[AuditTransition]
    debt_items: list[str]  # Links to baseline debt entries

@dataclass
class AuditReport:
    generated_at: str
    modes: list[ModeAuditState]
    debt_summary: dict[str, int]  # state → count
```
Output as JSON for CI consumption and human-readable markdown for review.

**Pros:**
- Single responsibility — lifecycle tracking is separated from scoring.
- Machine-readable JSON + human-readable text output.
- Each transition links to an evidence record or test probe (provenance).
- Debt items map directly to audit findings — no hand-maintained list.
- Platform can regenerate from evidence sink without touching Core.

**Cons:**
- New script and report type.
- Requires evidence sink to produce queryable state (P2 uses structured log output parsed by CI).
- State transitions currently implicit (audit_state on evidence) — need explicit transition model.

#### Option C — Extend `FeatureInvocationEvidence` with state transition data

Add `previous_audit_state: AuditState | None` and `transition_reason: str` to `FeatureInvocationEvidence`. Evidence records carry the full transition history.

**Pros:**
- Each evidence record is self-contained — audit trail is embedded.
- No separate aggregation step needed.

**Cons:**
- `FeatureInvocationEvidence` grows with lifecycle data that is irrelevant to most consumers.
- Each record would duplicate previous state for every invocation — wasteful.
- Cross-mode aggregation still requires a report builder.
- Violates RULE-06: evidence recording and lifecycle reporting are separate concerns.

---

**Decision: Option B — New `AuditReport` model in Platform.**

### Rationale

`AdoptionReport` is about scoring. `FeatureInvocationEvidence` is about per-invocation proof. `AuditReport` is about lifecycle state across all modes. These are three distinct concerns that should live in three distinct models. Option B ensures:

- `check_adoption.py` generates the AuditReport as a CI artifact (JSON for machines, summary for humans).
- Evidence sink output (structured logs in P2) is parsed to derive state transitions.
- Debt items from `ai-gate-baseline.json` are linked to specific `ModeAuditState` entries, not hand-maintained.
- P3 can upgrade to persistent storage without changing the report schema.

### Consequences

**Positive:**
- Lifecycle state becomes deterministically reportable — the exit criterion "audit lifecycle state is machine-readable" is met.
- Debt items are traceable to specific transitions.
- No changes to Core evidence models — report is pure Platform.

**Negative / Tradeoffs:**
- P2 report is CI-generated (post-hoc from evidence logs) rather than real-time queryable.
- Structured log parsing is lossy — transitions may be missed if logs are rotated.

**Constraints introduced:**
- AuditReport output JSON must be validatable against a schema for CI gates.
- Evidence sink structured log format must include `audit_state`, `feature_id`, `mode`, and `timestamp` for report generation.

---

## Decision 4 — Mode Runtime Proof Expansion

### Options Considered

#### Option A — Enumerate every mode with P2 evidence requirement

For each of the ~27 modes across 5 categories (writing 9, analysis 7, kb 8, planning 1, generation 1, chat 1), define exact runtime evidence requirements and implement pipeline integration.

**Pros:**
- Complete coverage — no mode can claim adopted without runtime proof.
- Forward-looking: all modes are planned explicitly.

**Cons:**
- Too aggressive for P2: ~27 modes × multiple enrichers/validators each is multiple implementation increments.
- generation/chat modes have fundamentally different invocation patterns (no WritingPipeline).
- Risk of incomplete/stub implementations violating architectural discipline.

#### Option B — Priority modes first (writing/analysis/kb with existing infrastructure)

Focus P2 on:
- **Writing** (9 modes): All modes already use `WritingPipeline` — wire `_invocation_adapter.py` pipeline across all, not just new_chapter/extend_chapter/inline_suggest.
- **Analysis** (7 modes): Wire invocation pipeline for the existing analysis routers.
- **KB** (8 modes): Wire invocation pipeline for KB agent modes.

Generation (names), planning (outline), and chat remain P3 targets.

**Pros:**
- 24 of 27 modes get runtime evidence in P2.
- Existing infrastructure (WritingPipeline, analysis/KB routers) minimizes new code.
- Most-used modes (writing, analysis) are covered first.

**Cons:**
- 3 modes (generation/names, planning/outline, chat) stay static-only until P3.
- Writing pipeline adapter currently only wired in `pipeline.py` — needs extension to co_author, scene_by_scene, interview, etc.

#### Option C — Add `requires_runtime_evidence` registry flag

Add an optional field to the adoption registry:
```yaml
writing/new_chapter:
  runtime_requirements:
    requires_runtime_evidence: true
```
The checker uses this flag to gate adopted status: a mode with `requires_runtime_evidence: true` cannot reach `adopted` without runtime evidence.

**Pros:**
- Registry-level mechanism for future modes.
- No code change to pipeline — just registry metadata.
- Clear signal to implementers: "this mode needs runtime proof."

**Cons:**
- Does not produce runtime evidence — just gates on it.
- Without implementation, the flag is a promise, not proof.
- Alone, violates INFRA-013's "runtime proof coverage includes every mode claiming adopted status."

---

**Decision: Option B + C combined. P2 focus on writing/analysis/kb modes + registry flag for all modes.**

### Rationale

Option B alone covers the majority of modes (24/27) using existing infrastructure. Option C adds the forward-looking mechanism so future modes declare intent from day one. Together they satisfy the exit criterion "runtime proof coverage includes every mode claiming adopted status" for the P2 scope, with an explicit list of remaining modes for P3.

**Priority order for P2:**
1. **Writing modes (9)**: Wire `_invocation_adapter.py` across ALL sub-pipelines (co_author, scene_by_scene, interview, session, rewrite, suggest, story_suggest, chat).
2. **Analysis modes (7)**: Add invocation pipeline to analysis routers (`router.py`, `router_readability.py`, `router_pov.py`).
3. **KB modes (8)**: Add invocation pipeline to KB agent routers (`router_extraction.py`, `router_consistency.py`, `router_suggestions.py`, `router.py` KB interview/improve).
4. **Registry flag**: Add `requires_runtime_evidence` to all 27 modes in `adoption-registry.yaml`.

**Deferred to P3:** generation/names, planning/outline, chat (free-form).

### Consequences

**Positive:**
- 24 of 27 modes gain runtime evidence paths in P2.
- Registry flag ensures any future mode declares intent.
- Writing pipeline extension is incremental — each sub-pipeline gets the same `_invocation_adapter.py` treatment.

**Negative / Tradeoffs:**
- ~3 months for generation/planning/chat modes to remain static-only.
- Writing pipeline sub-pipelines need individual attention — some (co_author) already have `character_voice_profiles` wiring, others (scene_by_scene) may need more.

**Constraints introduced:**
- `requires_runtime_evidence: true` in registry must be the default for all NEW modes going forward.
- Mode-specific adoption policy must include `kb_consistency` requirement where KG data is used.

---

## Implementation Plan (P2 Layer-by-Layer)

### Layer 1 — Core: `core/profiles/` module

| File | Responsibility |
|------|----------------|
| `packages/core/narrare_core/profiles/__init__.py` | Public API exports |
| `packages/core/narrare_core/profiles/models.py` | `ProjectWritingProfile` dataclass with `character_voice_profiles`, `writing_language`, `genre`, `tone`, `style_profile` |
| `packages/core/narrare_core/profiles/contracts.py` | `VoiceProfileProvider` Protocol (replaces direct `extract_voice_profiles()` calls in assemblers) |
| `packages/core/narrare_core/profiles/assembly.py` | `ProfileAssembler` — assembles `ProjectWritingProfile` from KB entities + project settings |
| `packages/core/narrare_core/profiles/_voice_extraction.py` | Relocated from `writing/_voice_profiles.py` (pure transformation, no `writing/` imports) |
| `packages/core/narrare_core/profiles/_freshness.py` | Relocated freshness helpers from `writing/_voice_profiles.py` and `writing/context_validators.py` |

**Dependencies:** None on `writing/` (RULE-07). Settings types imported from `narrare_core.llm.settings` or similar.

### Layer 2 — Core: `core/ai_invocation/consistency.py`

| File | Responsibility |
|------|----------------|
| `packages/core/narrare_core/ai_invocation/consistency.py` | `KBConsistencyResult` type, `KBConsistencyCheck` Protocol |
| `packages/core/narrare_core/ai_invocation/enrichers/consistency.py` | `KBConsistencyEnricher` — runs in pipeline, checks entity types, freshness, orphan refs |
| Update `packages/core/narrare_core/ai_invocation/enrichers/__init__.py` | Export `KBConsistencyEnricher` |

### Layer 3 — Core: Update existing enrichers

| File | Responsibility |
|------|----------------|
| `packages/core/narrare_core/ai_invocation/_enums.py` | Add `VoiceProfileStatus` enum (`provided`, `not_applicable`, `missing`) |
| `packages/core/narrare_core/ai_invocation/models.py` | Add optional `voice_profile_status: VoiceProfileStatus | None` to `FeatureInvocationEvidence` |
| `packages/core/narrare_core/ai_invocation/_evidence.py` | Update `build_invocation_evidence()` to include voice profile status from context |
| `packages/core/narrare_core/ai_invocation/contracts.py` | Add `ProfileProvider` Protocol (returns `ProjectWritingProfile | None`) |

### Layer 4 — Core: Wire WritingPipeline sub-pipelines

| File | Responsibility |
|------|----------------|
| `packages/core/narrare_core/writing/pipeline_coauthor.py` | Wire `_invocation_adapter.py` pipeline in `generate_co_author()` |
| `packages/core/narrare_core/writing/pipeline_scene.py` | Wire pipeline in `generate_scene()` |
| `packages/core/narrare_core/writing/pipeline_interview.py` | Wire pipeline in `generate_interview()` |
| `packages/core/narrare_core/writing/pipeline_rewrite.py` | Wire pipeline in `rewrite_content()` |
| `packages/core/narrare_core/writing/pipeline_extend.py` | Wire pipeline in `extend_content()` |
| `packages/core/narrare_core/writing/pipeline.py` | Ensure `generate()`, `suggest()`, `chat()` also wired |
| `packages/core/narrare_core/writing/_invocation_adapter.py` | Add profile assembly to context creation |

### Layer 5 — Backend: Wire analysis/KB routers

| File | Responsibility |
|------|----------------|
| `apps/api/narrare/analysis/dependencies.py` | Provide `InvocationPipeline` for analysis modes |
| `apps/api/narrare/analysis/router.py` | Pass pipeline + context through analysis service calls |
| `apps/api/narrare/kb/dependencies.py` | Provide `InvocationPipeline` for KB agent modes |
| `apps/api/narrare/kb/router_extraction.py` | Wire pipeline for extract/interview modes |
| `apps/api/narrare/kb/router_consistency.py` | Wire pipeline for consistency checks |
| `apps/api/narrare/kb/router_suggestions.py` | Wire pipeline for KB suggestion modes |

### Layer 6 — Platform: Audit lifecycle reporting

| File | Responsibility |
|------|----------------|
| `scripts/adoption/audit_report.py` | `AuditReport`, `ModeAuditState`, `AuditTransition` models + report builder |
| `scripts/adoption/kg_consistency_checker.py` | Static CI checker for KG registry alignment |
| `scripts/check_adoption.py` | Integrate `AuditReport` generation and KG checker |
| `scripts/architecture/ai-gate-baseline.json` | Regenerated from `AuditReport` debt items (no longer hand-maintained) |

### Layer 7 — Platform: Registry updates

| File | Responsibility |
|------|----------------|
| `scripts/architecture/adoption-registry.yaml` | Add `requires_runtime_evidence` flag to all modes; add `kb_consistency` to runtime_requirements where applicable |
| `scripts/adoption/scorer_modes.py` | Add `requires_runtime_evidence` to `compute_mode_score()`; adopt new flag for `adopted` gating |
| `scripts/adoption/scorer.py` | Update `AdoptionReport` to include `requires_runtime_evidence_count` and `runtime_evidence_gap_count` |

### Layer 8 — Docs

| File | Responsibility |
|------|----------------|
| `docs/features/infra/INFRA-013-ai-invocation-adoption-contract.md` | Update status to reflect P2 spec complete, P2 implementation in progress |
| `docs/architecture/decisions/ADR-040-kg-ssot-audit-lifecycle.md` | This ADR — accepted |
| `docs/architecture/decisions/INDEX.md` | Add ADR-040 entry |

### Dependency Order

```
Layer 1 (profiles) → Layer 2 (consistency types) → Layer 3 (evidence enrichers)
                                                         ↓
                                                    Layer 4 (writing pipelines)
                                                         ↓
                                                    Layer 5 (backend wiring)
                                                         ↓
                                          Layer 6+7 (platform reporting + registry)
                                                         ↓
                                                    Layer 8 (docs)
```

Layer 1-3 are prerequisites for Layers 4-5. Layers 6-7 can start after Layer 2 (types needed for audit model) but depend on Layer 3 for evidence enrichment.

### Testing Strategy

| Layer | Test Type | Coverage Target |
|-------|-----------|-----------------|
| 1 (profiles) | Unit: model construction, assembly from KB entities, freshness detection, empty/null cases | ≥95% |
| 2 (consistency types) | Unit: consistency result construction, validation | 100% |
| 3 (enrichers) | Unit: enricher with fake providers, edge cases (no KB, stale profiles, missing entity types) | ≥95% |
| 4 (writing pipelines) | Integration: each sub-pipeline produces valid evidence when wired; falls back gracefully when unwired | ≥90% |
| 5 (backend wiring) | Integration: DI wiring produces correct InvocationContext for each analysis/KB router | ≥85% |
| 6 (audit report) | Unit: report generation from evidence logs, state transitions, debt mapping | ≥95% |
| 7 (registry) | Unit: checker validates registry against prompts; flag gates adopted correctly | 100% |

---

## INFRA-013 Status Update (Draft)

Insert the following into `INFRA-013-ai-invocation-adoption-contract.md` under § Status and Decision Summary:

```
- 2026-06-06 — P2 Architecture Spec complete: ADR-040 defines Project Writing Profile
  SSOT (core/profiles/), KG consistency evidence (KBConsistencyEnricher + CI checker),
  audit lifecycle reporting (AuditReport model), and mode runtime proof expansion
  (writing/analysis/kb modes). P2 exit criteria specified. P2 implementation begins.
  P1 (mode-specific adoption registry, checker update, kb_suggested) is fully implemented.
  P2 implementation and P3 remain outstanding.
```

---

## Sustainability Check

1. **Correct in 3 months?** Yes. The `ProjectWritingProfile` model in Core, `KBConsistencyEnricher` in the pipeline, and `AuditReport` in Platform will still be the correct boundaries when new modes or features are added. Storage for profiles (P3) will be additive, not breaking.

2. **Hard-to-undo coupling?** Reduced. Voice extraction moves out of `writing/` into `profiles/`, eliminating the only cross-module dependency for profile data. Platform reports consume evidence output logs — no Core import.

3. **Simplest correct solution?** Yes. Each decision picks the option that addresses the root cause without over-building: in-memory profile model (not DB), both enricher and checker (not one), separate audit report (not coupled to scoring), priority mode expansion (not all-or-nothing).

4. **Design intent clear?** Yes. Four decisions, each with a clear boundary, alternatives, and rationale. Reviewers can trace from the P2 exit criteria to the specific artifacts.

---

## Review Trigger

- [ ] When P3 storage design for `ProjectWritingProfile` is needed (new ADR required).
- [ ] When a non-writing feature (analysis, planning) needs profile data and the `core/profiles/` contract does not cover it.
- [ ] When the number of runtime modes exceeds 30 and the registry flag approach needs scaling.
- [ ] When `AuditReport` transitions from CI-generated to live-query (persistent storage).
- [ ] When a new entity type is added to the KB that requires KG consistency check updates.

---

## RULE-XX Compliance

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-03 | ✅ | ADR-040 defines contracts before implementation; each new file has a spec section. |
| RULE-04 | ✅ | Profile model, enricher, extraction, freshness, and report are separate modules. |
| RULE-05 | ✅ | Core owns profiles/ and ai_invocation/consistency; Backend owns wiring; Platform owns reporting. |
| RULE-06 | ✅ | Voice extraction moved to profiles/; enricher and checker are separate responsibilities. |
| RULE-07 | ✅ | Core/profiles/ does not import writing/; Platform consumes evidence logs, not Core types. |
| RULE-09 | ✅ | All new Protocols and models require full type annotations. |
| RULE-10 | ✅ | Testing strategy defined per layer with coverage targets. |
| RULE-11 | ✅ | KBConsistencyEnricher records `not_applicable` when provider is missing — no silent failures. |
| RULE-20 | ✅ | `requires_runtime_evidence` flag prevents static-only adopted claims. |
| RULE-22 | ✅ | Profile, KG, and audit vocabulary is shared across Core/Platform without conflicting definitions. |
