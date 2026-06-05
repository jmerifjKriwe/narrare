# INFRA-012 — Prompt Governance Hardening

---
id: INFRA-012
title: "Prompt Governance Hardening"
status: stable
area: infra
mvp: false

ui_tooltip: "Closes remaining prompt-governance gaps from the content review."
ui_help_short: |
  Hardens Narrare's prompt system so every agent path inherits the same persona,
  every PromptComposer route has a governed template target, and every prompt
  variable has a declared provenance.
ui_help_long: |
  This infrastructure spec completes the CR-02 remediation approved by the user:
  ADR-026 Capability guarantees are validated separately, inline production
  fallbacks are removed or explicitly scoped to tests, PromptComposer mappings
  cannot drift from bundled targets, prompt variables are classified, and
  cross-feature context precedence is documented before new AI feature work.
ui_available_in: []

service: scripts/architecture/_checkers/prompt_integrity.py
contract: docs/architecture/decisions/ADR-026-capability-prompt-injection.md
router: null
prompt: packages/core/narrare_core/prompts/_bundled/
requires: [INFRA-002, INFRA-011, PROMPT-001, PROMPT-002]
---

## Scope

### In Scope

- Complete the CR-02 hardening items around ADR-026, PromptComposer routing,
  inline fallback removal, and production agent capability inheritance.
- Classify every prompt template variable as user-authored content,
  system-generated data, or feature-dynamic data.
- Convert new unregistered prompt variables from warnings to CI failures.
- Define cross-feature context precedence for author instructions, project
  writing profile, storyboard/timeline, curated KB, learned memory, and generated
  suggestions.
- Add process-prevention checklists: ADR CI Impact, Migration Completion / Legacy
  Cleanup, and AI Content Review Gate integration.

### Out of Scope

- Creating new AI features.
- Changing the prompt language policy from ADR-026 Phase 5.
- Adding external dependencies.
- Production code implementation by the Architecture Specialist.

## Root Cause / Motivation

**Symptom:** CR-02 found that ADR-026's mechanism is correct, but prompt governance
still has gaps: stale checkers, missing PromptComposer targets, stale inline
fallback references, incomplete variable classification, and underspecified
cross-feature precedence.

**Why #1:** ADR-026 fixed the runtime mechanism first. The supporting governance
surface — checkers, registry coverage, adoption records, and migration closure
criteria — lagged behind the architectural change.

**Why #2:** Prompt-related contracts are split across PromptComposer mappings,
bundled templates, variable registries, adoption YAML, content review findings,
and process docs. Because not every surface is a blocking gate, new templates or
intents can drift without failing immediately.

**Root cause:** Prompt architecture and prompt governance are not yet one
operational contract. The correct response is not a local prompt edit; it is a
contracted hardening program that turns remaining drift surfaces into explicit,
machine-checkable gates.

## Alternatives Considered

| Option | Description | Pros | Cons | Decision |
|--------|-------------|------|------|----------|
| A | Patch only the reported files and leave existing checks mostly unchanged | Fast local cleanup | Repeats root cause: future drift can re-enter through unmapped intents, unclassified variables, or broad fallbacks | Rejected |
| B | Hardening spec plus CI contracts for PromptComposer routes, capability inheritance, variable provenance, and migration closure | Addresses root cause; sustainable; compatible with ADR-026/RULE-22 | Requires coordinated Core/Backend/Platform/Docs work | **Chosen** |
| C | Revert to localized feature prompts and monolithic meta validation | Simpler for old checkers | Contradicts ADR-026 Phase 5 and reintroduces the maintenance failure ADR-026 solved | Rejected |

## Architectural Decisions

### 1. ADR-026 Hardening / Completion Contract

ADR-026 remains the governing architecture. This spec completes its governance
surface with the following rules:

1. **Meta and Universal validation are separate.**
   - `NarrareMeta` validates identity, role flexibility, and conversation
     guardrails.
   - `NarrareUniversalRules` validates fiction-content rules, conflict
     resolution, and injection defense.
   - Checkers must not require monolithic ADR-019-era meta content in one file.

2. **Feature templates may be EN-only.**
   - Bundled feature system prompts remain EN-only by default per ADR-026 Phase 5.
   - This is valid only when output language is supplied through variables,
     Context, Deps, or preferences such as `{{writing_language}}` /
     `{{language}}` / `{{explanation_language}}` as appropriate.
   - Meta and Universal localized families keep their declared locale parity.

3. **Every PromptComposer mapping must be route-governed.**
   - Each `_INTENT_TO_CATEGORY` + `_INTENT_TO_MODE` entry must resolve to a
     bundled EN target, be remapped/removed if unused, or be explicitly marked
     non-routeable with rationale.
   - Missing bundled EN targets are blocking failures for routeable intents.
   - Known CR-02 targets to resolve: `KB_CREATE`, `ANALYSE`, `SENTIMENT`,
     `VOICE`, `PLAN`, `GENERATE`, `TITLE_GENERATE`, `EXTRACT`, `RESEARCH`.

4. **Production inline prompt fallback bodies are forbidden when bundled targets exist.**
   - Production services must fail loudly with typed errors when a required
     bundled target is missing.
   - Test-only fallback bodies are allowed only when explicitly scoped to tests,
     documented in the adoption registry, and unreachable from production DI.
   - Broad `except Exception` prompt fallback behavior is forbidden.

5. **Every production agent path inherits ADR-026 Capabilities through `NarrareAgent`.**
   - Production agents must subclass/use `NarrareAgent`, not bare pydantic-ai
     `Agent`, unless an existing ADR-approved exception applies.
   - Regression coverage must prove production agent paths include both
     `NarrareMeta` and `NarrareUniversalRules`.

### 2. Variable Registry Governance

Prompt variables must have one provenance classification:

| Class | Meaning | Required registry | XML wrapping |
|------|---------|-------------------|--------------|
| User-authored content | Text or structured content written directly by the author/user: chapter prose, selections, author instructions, conversation history, KB entity body/name supplied by a user | `_USER_CONTENT_VARS` | Required in templates |
| System-generated data | Data assembled from trusted system state: curated KB summaries, project settings, computed counts, generated profiles persisted by services | `_SYSTEM_VARS` | Not required by default |
| Feature-dynamic data | Per-feature runtime data that is neither globally reusable nor directly user-authored: candidate pairs, entity events, timeline position, explanation language, variant count | `_FEATURE_DYNAMIC_VARS` or equivalent documented feature-variable registry | Required only if the value can include user-authored text |

Governance rules:

- New template variables that are absent from all registries fail CI.
- Existing legacy gaps may be baselined only with explicit cleanup owners and
  must not grow.
- Any variable that can contain user-authored text must be in
  `_USER_CONTENT_VARS` and must be XML-wrapped in the template.
- The checker must classify examples from FIND-005, including
  `writing_language`, `timeline_position`, `novel_synopsis`, `style_profile`,
  `candidate_pairs`, `chapter_summaries`, `entity_events`, `known_characters`,
  `entity_body`, `relationships`, `variant_count`, and `explanation_language`.

### 3. Cross-Feature Context Precedence

When prompt context sources conflict, the default precedence is:

1. **Current author instruction** — the user's explicit instruction for this run.
2. **Explicit project writing profile / manual override** — durable project-level
   style, tone, language, and rules intentionally set by the author.
3. **Current scene / storyboard / timeline plan** — the active plan for what is
   supposed to happen now.
4. **Curated KB** — accepted facts about characters, locations, factions,
   relationships, and world state.
5. **Learned memory / mem0 preferences** — inferred preferences and avoidance
   patterns from past interactions.
6. **Generated suggestions / inferred extraction** — unaccepted suggestions,
   extraction candidates, analysis outputs, and model-inferred possibilities.

**Rationale:** Current explicit author intent must win because the author owns the
work. Manual profile overrides outrank plans because they are global authorial
constraints. Current storyboard/timeline outranks curated KB for scene execution
because plans can intentionally move the story forward, but contradictions with
curated KB must be surfaced. Curated KB outranks learned memory because accepted
facts are stronger than inferred preferences. Generated suggestions are lowest
until the user accepts/curates them.

Conflict handling:

- Do not silently resolve high-impact conflicts between items 1–4.
- If author instruction conflicts with project profile, follow the current
  instruction and surface the conflict when the output can be materially affected.
- If storyboard/timeline conflicts with curated KB, surface the conflict or emit a
  typed consistency issue unless the feature is explicitly a brainstorming mode.
- If learned memory conflicts with any explicit/manual source, ignore memory for
  that run and optionally report that a learned preference was overridden.
- Generated suggestions/extractions must be labeled as unaccepted candidates until
  a service persists or accepts them.

### 4. Process Prevention

#### ADR CI Impact Checklist

Every ADR or ADR update that changes runtime architecture must include a CI impact
section:

- [ ] Which checkers must change?
- [ ] Which baselines must shrink, remain, or be invalidated?
- [ ] Which docs/context summaries must be updated to avoid stale guidance?
- [ ] Which tests prove the new architectural guarantee?
- [ ] Which existing exceptions are removed or revalidated?

#### Migration Completion / Legacy Cleanup Checklist

Any migration is incomplete until:

- [ ] Old production paths are removed or unreachable.
- [ ] Stale comments/docstrings/examples describing old behavior are removed.
- [ ] Adoption/exception registries no longer list migrated production fallbacks.
- [ ] Regression tests fail if the legacy path is reintroduced.
- [ ] Documentation reflects the new source of truth.

#### AI Content Review Gate Integration

The AI Content Review Gate must be part of Stage 2.5 and Stage 4 for every AI
feature:

- Stage 2.5: Architecture confirms PromptComposer routing, variable provenance,
  context precedence, ADR-026 capability inheritance, and output-language policy.
- Stage 4: Platform validates the machine checks and baselines.
- Stage 5: Docs verifies no derived guide weakens the rule.

## Module Boundaries and Required Implementation Surfaces

### Core

- `packages/core/narrare_core/prompts/composer.py`
  - Routeability contract for `_INTENT_TO_CATEGORY` + `_INTENT_TO_MODE`.
- `packages/core/narrare_core/prompts/variable_engine.py`
  - Variable provenance registries.
- `packages/core/narrare_core/agents/base.py`
  - `NarrareAgent` capability inheritance remains the only production base path.
- `packages/core/narrare_core/prompts/_bundled/**`
  - Bundled EN targets or explicit non-routeable rationale.

### Backend

- `apps/api/narrare/consistency/**`
  - Confirm no production inline prompt fallback body remains; remove stale comments.
- `apps/api/narrare/kb/**extraction*`
  - Confirm no production inline prompt fallback body remains; remove stale comments.
- Backend services must call agents/composer through DI and typed errors, not broad
  prompt fallback catches.

### Platform

- `scripts/architecture/_checkers/prompt_integrity.py`
- `scripts/architecture/_checkers/_check_intents.py`
- `scripts/architecture/_checkers/_check_variables.py`
- `scripts/check_prompt_structure.py`
- `scripts/architecture/adoption-registry.yaml`
- `scripts/architecture/ai-gate-baseline.json`

### Docs

- `docs/development/prompt-standards.md`
- `.opencode/context/narrare-dev/processes/quality-gates.md`
- Derived AGENTS/context docs that mention ADR-026, PromptComposer, inline
  fallbacks, or prompt locale policy.

## RULE-XX Compliance Matrix

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-01b | ✅ | Production LLM paths must use `NarrareAgent`; regression coverage prevents bare `Agent` bypass except approved exceptions. |
| RULE-02/02a | ✅ | Prompt content remains separated: Capabilities for guaranteed content, PromptComposer for customizable templates, runtime data via context. |
| RULE-03 | ✅ | This spec is the contract before implementation; no Core/Backend/Platform changes start without it. |
| RULE-04 | ✅ | Checkers and registries have separate responsibilities; no line-squeezing or monolithic checker expansion is required. |
| RULE-05 | ✅ | Module boundaries are defined by layer above. |
| RULE-06 | ✅ | Route checks, variable checks, adoption registry, and docs governance remain separate responsibilities. |
| RULE-07 | ✅ | Core remains independent of apps/api and docs; platform scripts inspect but are not imported by core runtime. |
| RULE-09 | ✅ | Public checker/helper additions require typed signatures. |
| RULE-10 | ✅ | Regression tests are required for capability inheritance, routeability, variable classification, and fallback prohibition. |
| RULE-11 | ✅ | Missing prompt targets must fail loudly with typed errors; broad fallback catches are forbidden. |
| RULE-12 | ✅ | No client-specific business logic; governance applies to service-layer AI paths. |
| RULE-13 | ✅ | No streaming interface changes; AI Content Review Gate still enforces SSE where applicable. |
| RULE-20 | ✅ | No half-implementation: migration completion requires code, registry, tests, and docs closure. |
| RULE-21 | ✅ | Material deviations from this spec require architecture re-review. |
| RULE-22 | ✅ | Cross-feature precedence and variable provenance are explicit semantic-review inputs. |

## Definition of Done

### Core Gate

- [ ] Every routeable `PromptComposer` mapping has a bundled EN target or is
      removed/remapped/non-routeable with rationale.
- [ ] `NarrareMeta` and `NarrareUniversalRules` are validated separately.
- [ ] Variable registries classify all existing template variables.
- [ ] Regression tests prove all production agents inherit both ADR-026 capabilities.

### Backend Gate

- [ ] No production inline system/task prompt fallback body remains when a bundled
      target exists.
- [ ] Test-only fallback, if any, is unreachable from production DI and explicitly
      registered.
- [ ] Broad prompt fallback catches are replaced by typed error handling.

### Platform Gate

- [ ] New unregistered prompt variables fail CI.
- [ ] Missing routeable bundled EN targets fail CI.
- [ ] New production inline fallbacks fail CI.
- [ ] Legacy baselines shrink or stay explicitly approved; no silent growth.

### Docs Gate

- [x] Prompt standards document variable provenance and context precedence. — Added to `docs/development/prompt-standards.md` §3 and `.opencode/context/narrare-dev/standards/prompt-standards.md`
- [x] AI Content Review Gate includes ADR-026 hardening checks. — Process Prevention Checklists added to `quality-gates.md` (Gates 9–10)
- [x] Stale ADR-019/monolithic-meta references are removed or marked historical. — Audit completed; no derived guide presents `with_meta()` or monolithic meta as current practice.

## Handoff Order

1. **Core** — routeability, variable classification, capability regression tests.
2. **Backend** — production fallback cleanup and typed error behavior.
3. **Platform** — enforce routeability, variable, fallback, and baseline gates.
4. **Docs** — harmonize derived guidance and feature/process docs after code
   evidence is available.

## Status & History

- 2026-06-05 — Spec created for approved CR-02 system-prompt/coherence
  remediation before implementation.
- 2026-06-05 — Implementation complete: Core routeability (routes.py), variable
  registry (variable_registry.py), Backend fallback removal (consistency + KB
  extraction), Platform checker updates, Docs audit completed.
