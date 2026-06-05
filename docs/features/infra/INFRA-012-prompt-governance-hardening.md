# INFRA-012 — Prompt Governance Hardening

---
id: INFRA-012
title: "Prompt Governance Hardening"
status: in-progress
area: infra
mvp: false

ui_tooltip: "Closes prompt-governance and prompt-quality gaps from content review."
ui_help_short: |
  Hardens Narrare's prompt system so every production LLM intent has an explicit
  prompt-surface contract, every routeable template has governed variables, and
  every user-authored context value is separated from instructions.
ui_help_long: |
  INFRA-012 started as the CR-02 remediation for ADR-026 governance and now also
  covers the user-approved CR-01 prompt-quality findings. The feature turns prompt
  quality rules into contracts: routeable intents must map to bundled templates,
  variables must declare provenance/security, production inline prompt fallbacks
  are forbidden, context producers and consumers are matched, and prompt checks
  classify blockers separately from ratcheted warnings.
ui_available_in: []

service: scripts/architecture/_checkers/prompt_integrity.py
contract: docs/architecture/decisions/ADR-037-prompt-surface-contract-manifest.md
router: null
prompt: packages/core/narrare_core/prompts/_bundled/
requires: [INFRA-002, INFRA-003, INFRA-011, PROMPT-001, PROMPT-002]
---

## Status and Decision Summary

- **CR-02 hardening:** implemented on 2026-06-05 and retained as part of this
  feature's governance baseline.
- **CR-01 hardening:** specified here for implementation after Architecture
  handoff. Core/Backend/Platform/Docs must not start production-code work before
  this spec is accepted by the coordinator/user.
- **ADR decision:** ADR-037 is required because the Prompt Surface Contract
  manifest is a new cross-module contract affecting Core routes, bundled prompts,
  Platform CI, and docs. ADR-025's schema-driven adoption pattern remains valid;
  ADR-037 specializes it for route-level prompt governance.

## Scope

### In Scope — CR-01 P0 Blockers

1. Prompt Surface Contract manifest: routeable `LLMIntent` ↔ category/mode/template,
   required/optional variables, variable source, content type, XML requirement,
   output-language field, and fallback policy.
2. Intent-to-template completeness gate.
3. No production inline prompt fallback policy and gate.
4. Template variable registry/taxonomy gate.
5. User-content XML wrapping gate and strict prompt preflight.

### In Scope — CR-01 P1 Quality Fixes

6. Context Producer/Consumer Matrix for `world_context`, `kb_suggested`,
   `writing_language`, `style_profile`, `genre`, `tone`, and future profile fields.
7. `world_context` for KB extraction and worldbuilding phase 2 templates.
8. `kb_suggested` in writing templates where safe and explicitly lower-priority.
9. Inline Suggest preference/context labeling improvements.
10. Consistency false-positive control, with schema-contract handling if output
    fields change.

### Strategic Items — Architecture-Deferred, Not Half-Implemented

11. **Project Writing Profile:** deferred to a follow-up feature spec
    (`SET-006 Project Writing Profile`, to be created before implementation). This
    cycle may only use existing `PromptContext` fields and manifest provenance
    labels; it must not add hidden DB/settings/profile storage.
12. **Multi-step strategy:** deferred to follow-up specs per workflow:
    consistency (`CONS-003 Multi-step Consistency Analysis`), long KB extraction
    (`KB-011 Long-form Extraction Strategy`), and major rewrite
    (`WRITE-013 Major Rewrite Workflow`). No service may introduce an unreviewed
    partial multi-step pipeline in this CR-01 implementation.

### P2 Items — Ratcheted Unless Schema-Compatible

13. Evidence/confidence for extraction and output-language/cultural consistency.
    Prompt/manifest improvements are in scope. If evidence/confidence requires
    output schema changes, Backend/API/Frontend contract updates are required in
    the same implementation slice; otherwise the item stays architecture-deferred,
    not half-implemented.

### Out of Scope

- Creating new user-facing AI features.
- Changing ADR-026's prompt content categories or feature-prompt EN-only policy.
- Adding external dependencies.
- Production code changes by the Architecture Specialist.
- Hidden storage/API/UI work for Project Writing Profile or multi-step workflows.

## Root Cause / Motivation

**Symptom:** CR-01 found strong default prompt content overall, but also missing
template routes, incomplete variable classification, uneven context adoption
(`world_context`, `kb_suggested`, writing-language/style fields), user-content XML
coverage risk, production inline fallback risk, and strategic context gaps.

**Why #1:** Prompt quality is governed by multiple partial surfaces: route tables,
bundled templates, `PromptContext`, context assemblers, variable registries,
adoption registry entries, content standards, and platform checkers. A template can
look good locally while the route/context/security contract remains incomplete.

**Why #2:** The current system validates categories and some variables, but it does
not declare the complete production prompt surface per intent. Without a route-level
manifest, Core cannot know which context is contractually required and Platform
cannot reliably distinguish blockers from ratcheted quality warnings.

**Root cause:** Prompt quality and prompt governance are still split. The correct
fix is not isolated prompt wording edits; it is a Prompt Surface Contract that makes
intent routeability, variables, provenance, XML safety, fallback behavior, and
context precedence machine-checkable.

## Alternatives Considered

| Option | Description | Pros | Cons | Decision |
|--------|-------------|------|------|----------|
| A | Patch only the CR-01 templates and current registries | Improves today's prompt text | Repeats root cause; future intents/variables/fallbacks can drift again | Rejected |
| B | Extend INFRA-012 with ADR-037 Prompt Surface Contract manifest plus CI gates | Addresses root cause; aligns Core/Platform/Docs; no prompt-surface drift | Requires coordinated manifest, checker, template, and docs work | **Chosen** |
| C | Implement Project Writing Profile and multi-step workflows immediately inside this cycle | Could address strategic findings directly | Too broad; would mix prompt governance with new storage/API/workflow architecture and risk half-implementation | Rejected for this cycle; deferred to follow-up specs |
| D | Encode all policy in checker heuristics without a manifest | No new manifest file | Policy becomes implicit and hard to review; non-routeable rationale and optional variables are unclear | Rejected |

### Sustainability Rationale for Chosen Approach

- Correct in 3 months: new intents/templates must enter the same manifest contract.
- Coupling: Core remains runtime owner; Platform inspects via manifest and does not
  become a runtime dependency.
- Simplest correct solution: a manifest plus focused checkers is simpler than
  expanding prose standards or embedding semantic policy in heuristics.
- Design intent: reviewers can see why a route is routeable/non-routeable and which
  variables are required before code changes land.

## Prompt Surface Contract / Manifest Design

### Location and Ownership

- **Manifest path:** `scripts/architecture/prompt-surface-manifest.yaml`
- **Runtime conformance:** `packages/core/narrare_core/prompts/routes.py`,
  `packages/core/narrare_core/prompts/composer.py`, bundled templates.
- **CI enforcement:** `scripts/architecture/_checkers/_check_prompt_surface.py`
  integrated through `prompt_integrity.py` / `check_prompt_structure.py`.
- **Architecture authority:** ADR-037 and this spec.

The manifest is a governance contract, not a runtime prompt builder. Core must not
import from `scripts/architecture/`; Platform may inspect Core files.

### Manifest Schema

```yaml
version: "1.0.0"
routes:
  - intent: EXTEND
    routeable: true
    category: writing
    mode: extend_chapter
    template: packages/core/narrare_core/prompts/_bundled/writing/en/extend_chapter/system.md
    content_type: customizable_feature_prompt
    output_language_variable: writing_language
    required_variables:
      - existing_content
      - user_preferences
      - avoidance_patterns
    optional_variables:
      - kb_suggested
      - style_profile
      - world_context
    variable_sources:
      existing_content: current_author_instruction
      user_preferences: learned_memory
      avoidance_patterns: learned_memory
      kb_suggested: generated_suggestion
      style_profile: project_writing_profile
    security:
      xml_required:
        - existing_content
      mixed_content_label_required:
        - user_preferences
        - avoidance_patterns
      generated_suggestions_must_be_labelled:
        - kb_suggested
    fallback_policy: fail_loudly_if_bundled_missing

  - intent: VOICE
    routeable: false
    rationale: "No dedicated bundled PromptComposer template yet."
```

### Required Route Semantics

- `routeable: true` means `PromptComposer.build(intent, context)` can resolve a
  bundled EN target without inline production fallback.
- `routeable: false` means the intent is model-routing-only, deterministic, not yet
  a prompt surface, or requires a context mode; it must include rationale.
- Context-mode-required intents must declare allowed modes or rationale so
  aggregate intents (for example, KB creation flows) do not pretend to have one
  canonical template.
- Every new `LLMIntent` addition requires a manifest entry in the same change.

### Content Types

| Content type | Meaning | Allowed mechanism |
|--------------|---------|-------------------|
| `customizable_feature_prompt` | User-overridable role/task/output/mode instructions | PromptComposer cascade |
| `guaranteed_capability` | Meta/universal content guaranteed by ADR-026 | `NarrareAgent` capabilities, not manifest-routeable feature templates |
| `runtime_dynamic_data` | Per-run context values | `PromptContext`, Deps, context assemblers |
| `generated_candidate_context` | Unaccepted suggestions/extractions | Runtime data, labelled lower priority |

The manifest governs the first and the variables used by the third/fourth. It does
not move guaranteed capability content back into templates.

## Variable Taxonomy and Security Classification

### Provenance Classes

| Provenance | Examples | Default precedence | Security requirement |
|------------|----------|--------------------|----------------------|
| `current_author_instruction` | `author_instructions`, selected text, current chapter text | 1 | XML required |
| `project_writing_profile` | `writing_language`, `genre`, `audience`, `pov`, `tense`, `tone`, `style_profile` | 2 | Label required; XML required when free-text |
| `scene_story_plan` | storyboard/timeline/current scene data, `timeline_position`, `story_structure` | 3 | Label required; XML required when user-authored text |
| `curated_kb` | accepted KB characters/locations/factions/relationships/world context | 4 | XML section wrapper required because KB text is author-authored but curated |
| `learned_memory` | `user_preferences`, `avoidance_patterns`, learned style constraints | 5 | Label required; XML/mixed-content wrapper when raw preference text is injected |
| `generated_suggestion` | `kb_suggested`, extraction candidates, candidate pairs | 6 | Must be labelled unaccepted/lower-priority |
| `system_generated` | counts, language codes, output format switches | n/a | No XML by default |
| `feature_dynamic` | per-feature computed values such as `variant_count`, `explanation_language` | feature-specific | Classified in manifest/registry |

### Registry Requirements

Implementation may keep the current three top-level registries
(`USER_CONTENT_VARS`, `SYSTEM_VARS`, `FEATURE_DYNAMIC_VARS`) only if the manifest
adds the missing provenance/security dimension. A variable is valid only when it is:

1. present in the registry/taxonomy,
2. assigned exactly one provenance class in the manifest or registry metadata,
3. assigned a security class (`xml_required`, `label_required`, `generated_label`,
   or `system_only`), and
4. consumed by templates according to that security class.

Any variable that can carry user-authored prose, KB content, profile prose, or
memory-derived prose must be wrapped in an explicit XML section or rejected by
strict preflight. Generated suggestions must be visibly labelled as unaccepted and
lower-priority.

## Fallback Policy

Production prompt fallback policy:

- Routeable manifest entries require a bundled EN template. Missing target = typed
  prompt route/template error.
- Prompt cascade may fall back from user/project DB override to bundled template.
  It may not fall back from missing bundled template to inline production prompt
  bodies.
- Broad `except Exception` prompt fallback behavior is forbidden.
- Test-only fallback bodies are allowed only if they are registered, unreachable
  from production dependency injection, and covered by tests proving production
  cannot call them.
- Non-routeable intents must raise a typed route-not-configured error when used
  through `PromptComposer` without an approved context mode.

## Context Producer/Consumer Matrix

| Context variable / group | Producer | Required consumers in this cycle | Security/precedence note |
|--------------------------|----------|----------------------------------|--------------------------|
| `world_context` | KB/context assembly from curated KB/world state | `packages/core/narrare_core/prompts/_bundled/kb/en/extract/system.md`; `.../kb/en/worldbuilding/phase2/system.md` | Curated KB; XML section wrapper required; conflicts surfaced, not silently resolved |
| `kb_suggested` | `WritingContextAssembler` Tier 4 suggested entities | Safe writing templates: `writing/en/new_chapter`, `writing/en/extend_chapter`, `writing/en/co_author`, and `writing/en/inline_suggest` if kept lightweight | Generated suggestion; label as optional/lower-priority; never force into prose |
| `writing_language` / `language` / `explanation_language` | project/user settings, request context, feature deps | All user-facing generation and explanation templates referenced by manifest | Output-language control; required for EN-only feature prompts |
| `style_profile` | Existing `PromptContext` field; future Project Writing Profile | Writing templates where style continuity matters; analysis/chat/planning only after SET-006 | Free-text profile prose requires label/XML; strategic durable producer deferred |
| `genre`, `tone`, `story_structure`, `timeline_position` | Existing request/context assembly; future Project Writing Profile / planning features | Writing/planning templates that already route through PromptComposer | Scene/story plan outranks curated KB only for current-scene execution; conflicts surfaced |
| `user_preferences`, `avoidance_patterns` | mem0/preference provider | All context-aware prompts per prompt standards | Learned memory is lower than explicit/profile/KB; label or XML/mixed-content wrapper |
| `candidate_pairs`, `entity_events`, extraction candidates | Feature services/assemblers | KB worldbuilding/extraction prompts | Generated suggestions; must remain candidate-labelled until accepted |

### P1 Template Requirements

- Add `world_context` sections to KB extraction and worldbuilding phase 2.
- Add `kb_suggested` only where it improves quality without harming latency or
  task focus. Inline Suggest must use a concise labelled section; Rewrite Selection
  may omit `kb_suggested` unless the manifest marks it optional for a specific mode.
- Improve Inline Suggest labels for preferences, avoidance patterns, and suggested
  context.
- Add consistency false-positive control wording. If this changes output schema
  (for example adding `classification`), update backend schemas, frontend types,
  and contract tests in the same implementation slice.

## Project Writing Profile Handling

Project Writing Profile is **architecture-deferred**, not partially implemented in
this cycle.

Follow-up feature spec to create before code: `docs/features/settings/SET-006-project-writing-profile.md`.

Contract outline for the follow-up:

- Fields: `writing_language`, `genre`, `audience`, `pov`, `tense`, `tone`,
  `style_profile`, `cultural_context`, `avoidance_patterns`, optional
  `custom_style_rules`.
- Producer: project settings/profile service, not ad-hoc request dictionaries.
- Consumers: writing, analysis, chat, planning, KB extraction/worldbuilding where
  output language/style matters.
- Precedence: current author instruction > Project Writing Profile/manual override
  > current scene/storyboard/timeline > curated KB > learned memory > generated
  suggestions.
- Required architecture artifacts: feature spec, API/backend contract, frontend
  settings UX contract, prompt manifest updates, tests.

CR-01 implementation may register existing `PromptContext` fields as profile-like
sources, but must not add hidden profile persistence or UI without SET-006.

## Multi-step Strategy Handling

Multi-step workflows are **architecture-deferred** to avoid half-implementation.

Follow-up specs required before code:

- `CONS-003 Multi-step Consistency Analysis`: extract facts/events first, compare
  second, return typed issue classifications and evidence.
- `KB-011 Long-form Extraction Strategy`: chunk/evidence extraction with confidence
  and merge/dedup stages.
- `WRITE-013 Major Rewrite Workflow`: analyze selected text and rewrite goals first,
  then produce final variants with style/voice continuity.

Current CR-01 implementation may improve single-step prompts and manifest labels.
It must not introduce partial orchestration, hidden background jobs, or unreviewed
multi-agent chains.

## CI / Checker / Test Plan

### Blocker Gates

| Gate | Owner | Blocking condition |
|------|-------|--------------------|
| Prompt Surface Manifest | Platform | Missing manifest entry for any production `LLMIntent`; routeable target missing; route table drift |
| Intent-to-template completeness | Platform/Core | Routeable manifest route cannot resolve bundled EN template |
| Variable taxonomy | Platform/Core | New template variable not registered/classified; duplicate/conflicting provenance |
| XML/security preflight | Platform/Core | `xml_required` variable appears outside explicit XML wrapper; generated suggestions not labelled |
| Fallback prohibition | Platform/Backend/Core | Production inline fallback body for routeable manifest target; broad prompt fallback catch |
| Strict prompt preflight | Core/Platform | Required manifest variables absent from `PromptContext`/extra for production path tests |
| Contract-change parity | Backend/Frontend/Platform | Consistency/extraction output schema changes without matching API/TS/tests |
| Regression tests | Core/Platform | No tests for manifest conformance, variable security, and no-fallback behavior |

### Ratcheted Warnings

| Warning | Ratchet rule |
|---------|--------------|
| Optional context variable missing (`kb_suggested`, `style_profile`, profile-like fields) | Baseline may not grow; touched route must either adopt or explicitly justify omission in manifest |
| P2 evidence/confidence wording without schema support | Warning until a follow-up schema-contract spec is approved; no hidden schema drift |
| Cultural/output-language specificity | Warning for prompts that are not user-facing; blocker for user-facing EN-only feature prompts without output-language variable |
| Legacy docs wording | Warning only if not normative; blocker if derived docs contradict ADR-026/ADR-037/CONSTRAINTS |

### Test Surfaces

- `tests/unit/core/prompts/test_composer.py`: routeability and typed route errors.
- `tests/unit/core/prompts/test_variable_engine.py`: strict preflight and variable
  classification interactions.
- `tests/unit/core/prompts/test_prompt_surface_manifest.py` (new): manifest schema,
  route/template/variable conformance.
- `tests/unit/architecture/test_prompt_surface_checker.py` (new or equivalent):
  checker blocker vs warning behavior.
- `tests/unit/api/consistency/test_checker_service.py`: no inline fallback and schema
  parity if consistency output changes.
- `tests/unit/api/kb/test_extraction_service.py`: evidence/confidence only if typed
  output contract supports it.

## Module Boundaries and Required Implementation Surfaces

### Core Handoff

Likely files affected:

- `packages/core/narrare_core/prompts/routes.py` — align routeable/non-routeable
  decisions with manifest.
- `packages/core/narrare_core/prompts/composer.py` — strict preflight behavior for
  manifest-required variables if implemented in Core.
- `packages/core/narrare_core/prompts/context.py` — expose existing fields cleanly;
  no hidden Project Writing Profile persistence.
- `packages/core/narrare_core/prompts/variable_registry.py` — expand taxonomy or add
  provenance/security metadata consumed by Platform.
- `packages/core/narrare_core/prompts/variable_engine.py` — preserve template-level
  XML model; strict checks must not auto-wrap silently.
- Bundled templates:
  - `packages/core/narrare_core/prompts/_bundled/kb/en/extract/system.md`
  - `packages/core/narrare_core/prompts/_bundled/kb/en/worldbuilding/phase2/system.md`
  - `packages/core/narrare_core/prompts/_bundled/writing/en/new_chapter/system.md`
  - `packages/core/narrare_core/prompts/_bundled/writing/en/extend_chapter/system.md`
  - `packages/core/narrare_core/prompts/_bundled/writing/en/co_author/system.md`
  - `packages/core/narrare_core/prompts/_bundled/writing/en/inline_suggest/system.md`
  - `packages/core/narrare_core/prompts/_bundled/analysis/en/consistency/system.md`
- `packages/core/narrare_core/writing/context_assembler.py` and
  `packages/core/narrare_core/writing/models.py` only if existing `kb_suggested` /
  profile fields need pass-through verification.

Core Definition of Done:

- Route table and manifest agree.
- Prompt variables used by touched templates are classified with provenance and
  security requirements.
- Touched templates include required XML/labels and output-language variables.
- No automatic XML wrapping workaround is introduced.
- Tests cover route errors, variable classification, and strict preflight behavior.

### Backend Handoff

Backend has no required storage/router work for P0 manifest governance. Backend work
is required only where current services still expose fallback or output-schema drift:

- `apps/api/narrare/consistency/checker_service.py`
- `apps/api/narrare/consistency/dependencies.py`
- `apps/api/narrare/consistency/router.py` / schemas if consistency issue output
  changes.
- `apps/api/narrare/kb/**extraction**` service/schema files if extraction
  evidence/confidence fields become typed output.

Backend Definition of Done:

- No production inline prompt fallback for routeable manifest targets.
- Typed errors are propagated/converted intentionally; no broad silent fallback.
- Any output schema change updates API contract and client-facing tests in the same
  implementation slice.

### Platform Handoff

Likely files affected:

- `scripts/architecture/prompt-surface-manifest.yaml` (new)
- `scripts/architecture/_checkers/_check_prompt_surface.py` (new)
- `scripts/architecture/_checkers/_check_intents.py`
- `scripts/architecture/_checkers/_check_variables.py`
- `scripts/architecture/_checkers/prompt_integrity.py`
- `scripts/check_prompt_structure.py`
- `scripts/architecture/adoption-registry.yaml`
- `scripts/architecture/ai-gate-baseline.json`
- `.github/workflows/ci.yml` only if a new checker command must be wired into CI.

Platform Definition of Done:

- Blocker vs ratcheted warning classification implemented exactly as this spec.
- Missing routeable templates, unregistered variables, unsafe XML omissions, and
  production fallback bodies fail CI.
- Legacy baselines do not grow silently.
- Checker tests cover positive and negative examples.

### Docs Handoff

Likely files affected:

- `docs/development/prompt-standards.md`
- `docs/development/prompt-content-standards.md`
- `.opencode/context/narrare-dev/standards/prompt-standards.md`
- `.opencode/context/narrare-dev/processes/feature-pipeline.md`
- `.opencode/context/narrare-dev/processes/quality-gates.md`
- Feature docs for any prompt whose output schema/UX semantics change.

Docs Definition of Done:

- Derived prompt guidance references ADR-037 and does not contradict
  CONSTRAINTS.md, ADR-026, or this spec.
- Project Writing Profile and multi-step workflows are documented as deferred until
  their own specs exist.
- Prompt review checklist includes manifest routeability, variable provenance,
  XML/security, output-language, and fallback checks.

## RULE-XX Compliance Matrix

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-01b | ✅ | No LLM call path changes; agents/model routing remain governed by existing ADRs. |
| RULE-02/02a | ✅ | Manifest governs customizable feature templates and runtime data; ADR-026 capabilities remain guaranteed content. |
| RULE-03 | ✅ | ADR-037 and this spec define the cross-module contract before implementation. |
| RULE-04 | ✅ | Manifest, route logic, variable registry, and checkers remain separate responsibilities. |
| RULE-05 | ✅ | Core prompt ownership and Platform checker ownership are explicit. |
| RULE-06 | ✅ | No service/router/checker receives mixed responsibilities in the handoff. |
| RULE-07 | ✅ | Core does not import `apps/` or `scripts/`; Platform inspects Core. |
| RULE-08 | ✅ | No new external integration or dependency is introduced. |
| RULE-09 | ✅ | New public checker/helper APIs require full type annotations. |
| RULE-10 | ✅ | Unit and checker tests are required before implementation is done. |
| RULE-11 | ✅ | Missing routeable templates fail loudly; silent fallback is forbidden. |
| RULE-12 | ✅ | Service layer remains the public API; no client-specific logic is added. |
| RULE-13 | ✅ | No streaming interface changes; SSE rules remain unaffected. |
| RULE-14 | ✅ | No DB/model changes in current scope; Project Writing Profile storage is deferred. |
| RULE-15 | ✅ | No frontend route middleware work. |
| RULE-16 | ✅ | UI i18n unaffected; prompt EN-only policy remains ADR-026-governed. |
| RULE-17 | ✅ | Any output schema change must update API/frontend contracts in the same slice. |
| RULE-18 | ✅ | No hardcoded runtime config is introduced. |
| RULE-19 | ✅ | No DB session dependency changes in current scope. |
| RULE-20 | ✅ | Strategic items are explicitly deferred; no partial Project Writing Profile or multi-step workflow. |
| RULE-21 | ✅ | Material deviations from this spec require architecture re-review. |
| RULE-22 | ✅ | Variable provenance, context precedence, injection defense, routeability, and CI impact are explicit. |

## Architecture Validation Checklist

- [x] Root cause documented with 2x Why.
- [x] Minimum two alternatives evaluated.
- [x] ADR requirement evaluated; ADR-037 created because this is a new cross-module
      contract.
- [x] Prompt Surface Contract design specified.
- [x] Variable taxonomy and security classification specified.
- [x] Fallback policy specified.
- [x] Context Producer/Consumer Matrix specified.
- [x] CI/checker/test plan classifies blockers vs ratcheted warnings.
- [x] Layer handoff includes exact Core/Backend/Platform/Docs surfaces and DoD.
- [x] Project Writing Profile and multi-step strategy explicitly deferred to
      follow-up specs to avoid half-implementation.
- [x] Sustainability check passed.

## Handoff Order

1. **Core** — manifest-conformant route/template/variable/context changes and prompt
   tests.
2. **Backend** — remove/verify fallback absence and apply schema-contract changes
   only if prompt output changes require them.
3. **Platform** — implement manifest/checker gates and CI/baseline behavior.
4. **Docs** — update derived prompt standards and mark strategic follow-ups as
   deferred until their specs are created.

## Status & History

- 2026-06-05 — CR-02 prompt governance remediation implemented.
- 2026-06-05 — CR-01 prompt-quality architecture specified; ADR-037 added for the
  Prompt Surface Contract manifest; feature status set to `in-progress` until
  Core/Backend/Platform/Docs implementation and validation complete.
