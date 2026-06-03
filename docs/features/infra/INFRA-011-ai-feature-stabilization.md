# INFRA-011 — AI Feature Stabilization Program

---
id: INFRA-011
title: "AI Feature Stabilization Program"
status: in-progress
area: infra
mvp: false

ui_tooltip: "Stabilizes prompts, AI streaming, privacy, and architecture gates."
ui_help_short: |
  Stabilizes Narrare's existing AI features before new AI capabilities are added.
ui_help_long: |
  This infrastructure program closes prompt-quality gaps, centralizes frontend SSE
  handling, makes local AI-session persistence privacy-safe, harmonizes agent
  documentation, and turns warning-only checks into explicit quality gates.
ui_available_in: []

service: scripts/architecture/check_adoption.py
contract: docs/architecture/decisions/ADR-027-ai-feature-stabilization-gates.md
router: null
prompt: packages/core/narrare_core/prompts/_bundled/
requires: [INFRA-002, INFRA-003, INFRA-005, PROMPT-001, PROMPT-002, KB-002, WRITE-002, WRITE-003, WRITE-004, WRITE-005, WRITE-007]
---

## Scope

### In Scope

- AUFG-03-01: classify and reduce prompt-structure warnings and prompt-integrity failures.
- AUFG-03-02: raise KB adoption score from WARN to PASS (`>= 0.85`).
- AUFG-03-03: make KB Interview Resume privacy-safe with TTL, transparency, and opt-out.
- AUFG-03-04: document MCP/A2A as planned adapters only; no review claims for unimplemented adapters.
- AUFG-03-05: harmonize agent and documentation sources so RULE-02/RULE-02a are not contradicted by path-scoped docs.
- AUFG-03-06: convert prompt/adoption WARNs into ratcheted or hard gates where appropriate.
- AUFG-03-07: centralize frontend SSE around a transport abstraction that supports GET and POST, shared parsing, abort/error handling, and partial-output preservation.
- AUFG-03-08: modularize frontend hubs and sharpen TypeScript RULE-04 enforcement.
- AUFG-03-09: add a no-growth gate for approved architecture exceptions.
- AUFG-03-10: freeze new AI-feature implementation until this stabilization program reaches its Definition of Done.

### Out of Scope

- New AI capabilities such as character-consistency tracking, multi-draft comparison, reader simulation, or emotional-intensity curves.
- Implementing MCP or A2A adapters. This program only clarifies their roadmap scope and adapter constraints.
- Changing the tech stack or adding new dependencies.
- Production implementation by the Architecture Specialist. Implementation is handed off by layer below.

## Root Cause / Motivation

**Symptom:** Review 03 found strong AI infrastructure but inconsistent adoption: prompt warnings, inline fallbacks, duplicated frontend SSE parsers, persistent local resume state, large frontend hubs, and drift between agent instruction sources.

**Why #1:** New AI features were integrated faster than the stabilization gates matured. Existing gates catch many violations but still allow WARN-only prompt/adoption gaps, manual streaming review, and documentation drift.

**Why #2:** Several architectural contracts exist as prose or local conventions instead of a single operational source: prompt category requirements are split across ADRs, standards, registry, checkers, and AGENTS files; SSE is implemented both centrally and ad hoc because `connectSSE` is too narrow for all current AI streaming use cases.

**Root cause:** The project has correct core primitives, but not enough machine-checkable, cross-layer stabilization contracts for AI features. The correct response is not quick prompt edits or parser copy-paste removal; it is a bounded stabilization program with ratcheted gates, a stronger frontend streaming abstraction, and explicit documentation-source governance.

## Architectural Decisions

The governing architecture decision is [ADR-027 — AI Feature Stabilization Gates](../../architecture/decisions/ADR-027-ai-feature-stabilization-gates.md).

### Decision Summary

1. **AI Feature Freeze:** no new AI feature implementation starts until this spec's stabilization gates pass. Bug fixes and stabilization work remain allowed.
2. **Prompt Gate Ratchet:** current WARN gaps are classified, baselined, then reduced monotonically. New WARNs are failures; classified legacy WARNs must have owners and target gates.
3. **SSE Transport Contract:** frontend AI streaming uses one shared transport/parser abstraction; feature-specific modules only define request/response accumulation.
4. **Documentation Source Governance:** `docs/_shared/CONSTRAINTS.md` and ADRs are authoritative. AGENTS/context files may summarize but must not weaken RULE-02/RULE-02a.
5. **No-Growth Exceptions:** approved architecture exceptions may shrink or stay explicitly justified; they may not grow without ADR/user approval.

## Alternatives Considered

### Gate Strategy

| Option | Description | Pros | Cons | Decision |
|--------|-------------|------|------|----------|
| A | Immediately fail all existing WARNs | Simple and strict | Blocks stabilization on already-known legacy gaps without classification | Rejected |
| B | Ratcheted baseline: current legacy WARNs classified; new WARNs fail; legacy count must decrease | Enforces no regression while allowing ordered cleanup | Requires baseline artifact and CI comparison | **Chosen** |
| C | Keep WARN-only gates and rely on review | Low disruption | Repeats the root cause: passive governance | Rejected |

### Streaming Strategy

| Option | Description | Pros | Cons | Decision |
|--------|-------------|------|------|----------|
| A | Keep feature-specific SSE parsers | No immediate refactor | Violates RULE-20/RULE-22 risk: inconsistent abort/error/partial behavior | Rejected |
| B | Expand `connectSSE` into a shared GET/POST transport and parser; feature modules provide typed accumulators | One operational contract, preserves feature-specific event semantics | Requires careful migration tests | **Chosen** |
| C | Introduce EventSource-only SSE | Browser-native API | EventSource cannot POST request bodies; does not fit existing AI endpoints | Rejected |

### Documentation-Drift Strategy

| Option | Description | Pros | Cons | Decision |
|--------|-------------|------|------|----------|
| A | Manually edit the known conflicting AGENTS files only | Fast | Drift can return silently | Rejected |
| B | Define source hierarchy and add a doc-drift/no-weaker-rule gate | Sustainable, machine-checkable direction | Requires platform checker work | **Chosen** |
| C | Collapse all instructions into one file | Removes duplication | Loses path-scoped operational context | Rejected |

## Layer Breakdown and Handoffs

### Core — NarrareCoreSpecialist

**Scope**

- Fix prompt-integrity regressions for Meta, Universal, and Lite prompts.
- Remove or migrate inline prompt fallbacks in KB/writing according to RULE-02/RULE-02a.
- Ensure prompt variables match `prompt-standards.md`: `{{user_preferences}}`, `{{avoidance_patterns}}`, category-specific variables, XML wrapping for user content, and 3-locale version parity.
- Classify any remaining EN-only prompt as either non-user-facing transitional content with explicit rationale or convert to de/fr.

**Module boundaries**

- Prompt content: `packages/core/narrare_core/prompts/_bundled/**`.
- Prompt variable registration: `packages/core/narrare_core/prompts/variable_engine.py`.
- Agent/capability loading: `packages/core/narrare_core/agents/**` only where ADR-026 allows guaranteed/dynamic content.
- No prompt assembly outside `core/prompts/` except ADR-026 guaranteed/dynamic mechanisms.

**Acceptance criteria**

- `check_prompt_structure.py` has no unclassified WARNs for touched categories.
- Meta/Universal/Lite prompt regression tests pass.
- KB adoption score is `>= 0.85`.
- No new inline prompt fallback appears outside approved, shrinking exception list.

### Frontend — NarrareFrontendSpecialist

**Scope**

- Replace ad hoc Generation/Rewrite/Extend/CoAuthor SSE parsing with a shared streaming transport contract.
- Support both GET and POST SSE requests, AbortSignal, typed events, error normalization, retry affordance, and partial-output preservation.
- Keep feature-specific accumulation in small wrappers; the parser/transport belongs in shared API infrastructure.
- Add privacy-safe KB Interview Resume handling: TTL, explicit user notice, opt-out, and minimized persisted payload.
- Modularize frontend hubs identified by graph/line-count analysis: `generation.ts`, `client.ts`, `EditorView.tsx`, `TipTapEditor.tsx`, `GhostText.ts`, `CoAuthorPanel.tsx`, and mocks/types where touched.

**Module boundaries**

- Shared transport/parser: `packages/web/lib/api/streaming.ts` plus focused sibling modules if needed, e.g. `streaming-events.ts`, `streaming-errors.ts`, `streaming-types.ts`.
- Feature wrappers: `packages/web/lib/api/generation*.ts`, `kb-sessions.ts`, `suggest.ts`, `timeline.ts`.
- Interview resume state: `packages/web/lib/hooks/use-kb-interview-resume.ts` and UI disclosure in the KB session components.
- Editor modularization: extract cohesive hooks/components under `packages/web/components/studio/editor/**` without changing backend contracts.

**Acceptance criteria**

- No AI feature with a backend SSE endpoint uses REST-only frontend behavior.
- All migrated streams preserve partial output on abort/loss and expose retry where UX expects it.
- Vitest covers success, event parse error, network error, abort, and partial-output preservation.
- Touched frontend files are below the TypeScript RULE-04 limit or have a split completed in the same implementation slice.

### Docs — NarrareDocsSpecialist

**Scope**

- Harmonize `AGENTS.md`, `apps/api/AGENTS.md`, `packages/core/AGENTS.md`, and extracted context so none weaken RULE-02/RULE-02a.
- Update review language for MCP/A2A: they are planned adapters, not implemented surfaces.
- Document the AI feature freeze and stabilization ordering in feature/roadmap docs.

**Acceptance criteria**

- No documentation weakens ADR-026 by allowing broad agent inline-prompt exceptions.
- MCP/A2A are described as planned adapters that call the Service Layer (RULE-12), with Q-001/Q-002 still open.
- Documentation gate has no unresolved placeholder language.

### Platform — NarrarePlatformSpecialist

**Scope**

- Implement ratcheted prompt/adoption gate behavior.
- Add no-growth gate for approved architecture exceptions, including RULE-01b and prompt/inline-fallback exceptions.
- Add frontend file-size enforcement or reporting calibrated to TypeScript/TSX limits.
- Add static or semi-static checks that all registered AI streaming endpoints have frontend SSE coverage.

**Acceptance criteria**

- New prompt/adoption WARNs fail CI.
- Legacy WARN baseline can only decrease unless an ADR-approved exception is added.
- Exception list growth fails without explicit ADR/user approval.
- CI reports TypeScript/TSX files above agreed thresholds and fails newly touched hard-limit violations.

## Stage 2.5 Semantic Review / RULE-22 Compliance

| Item | Status | Evidence / Required Action |
|------|--------|----------------------------|
| Cross-feature data flows | ✅ | Prompt registry, KB data, memory/preferences, settings, frontend streaming, and docs all identified. |
| Integration contracts | ✅ | Prompt/adoption registry and ADR-027 define cross-feature contracts; frontend SSE contract required before parser migration. |
| Intent semantics | ✅ | No new LLMIntent is introduced by this stabilization program. Existing intent collisions must be checked when prompt files are touched. |
| i18n parity | ✅ | All user-facing bundled prompts touched by this work require en/de/fr parity or explicit architecture-approved rationale. |
| Injection defense | ✅ | User-content variables must remain registered in `_USER_CONTENT_VARS` and XML-wrapped. |
| Template variables | ✅ | New variables must be registered in `_SYSTEM_VARS` or `_USER_CONTENT_VARS` before prompt use. |
| KB status filtering | ✅ | Any KB context fixes must preserve deprecated/archived filtering semantics. |
| Token budget | ✅ | Prompt/content migrations must preserve ContextAssembler/TokenBudgetManager usage. |
| RULE-22 | ✅ | Stabilization explicitly governs shared prompt, KB, memory, and streaming contracts. |

## RULE-XX Compliance Matrix

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-01b | ✅ | No new model/agent provider path. No-growth gate prevents exception expansion. |
| RULE-02/02a | ✅ | Prompt fixes must use `core/prompts/`, PromptComposer, and ADR-026 mechanisms only. |
| RULE-03 | ✅ | ADR-027 is the stabilization contract before implementation; frontend SSE contract required before migration. |
| RULE-04 | ✅ | Frontend hub modularization is explicit scope; no compression allowed. |
| RULE-05 | ✅ | Module boundaries are defined per layer. |
| RULE-06 | ✅ | Shared SSE transport, feature accumulators, docs governance, and checkers have separate responsibilities. |
| RULE-07 | ✅ | No core imports from apps/web; docs/platform changes do not alter dependency direction. |
| RULE-09 | ✅ | Platform/frontend handoffs require typed public interfaces. |
| RULE-10 | ✅ | Unit, integration, and frontend tests specified per layer. |
| RULE-11 | ✅ | Shared streaming errors must normalize/report failures; no silent parser failures. |
| RULE-12 | ✅ | MCP/A2A remain planned adapters that call Service Layer only. |
| RULE-13 | ✅ | SSE-capable AI backends require SSE frontend use; stream/non-stream semantics remain one interface. |
| RULE-16 | ✅ | UI notices and labels require 3-locale parity. |
| RULE-17 | ✅ | No backend schema change is planned; if introduced, frontend types update in same task. |
| RULE-20 | ✅ | AI feature freeze prevents new half-implementations; no deferred streaming. |
| RULE-21 | ✅ | Material deviations from this stabilization plan require architecture re-review. |
| RULE-22 | ✅ | Stage 2.5 matrix above covers shared prompt/KB/memory/settings contracts. |

## Definition of Done

### Current Implementation Evidence (2026-06-03)

- **Platform:** Ratchet/no-growth/frontend-size/streaming-compliance gates implemented; focused validation passed (37 tests).
- **Core:** Meta/Universal/Lite prompt regressions fixed; KB adoption is PASS (`0.85`), overall adoption `0.90`; `check_prompt_structure.py` passes with classified legacy WARN debt and ratchet evidence (`0` new / `21` resolved).
- **Frontend:** Shared `connectSSE` supports GET/POST with normalized errors; Generation/Rewrite/Extend/CoAuthor streams use shared transport; `generation.ts` split via `generation-streams.ts`; KB Interview Resume has 24h TTL, opt-out, privacy notice, and en/de/fr parity; focused Vitest passed (57 tests).
- **Docs/Governance:** Current slice harmonizes AGENTS/context docs, MCP/A2A planned-scope wording, roadmap freeze language, and gate-command documentation before freeze-lift review.

### Program Gate

- [x] ADR-027 accepted or explicitly approved by the user/coordinator for implementation.
- [x] No new AI feature implementation is started before Core + Frontend + Platform stabilization gates pass.
- [x] Review 03 tasks AUFG-03-01 through AUFG-03-10 have implementation-owner handoffs and validation evidence.

### Core Gate

- [x] Prompt integrity regressions are fixed.
- [x] KB adoption score is `>= 0.85`.
- [x] Inline prompt fallback list shrinks or remains only with ADR-approved, target-dated exceptions.
- [x] Prompt i18n parity is restored or each remaining EN-only prompt has architecture-approved rationale/classified legacy WARN status.

### Frontend Gate

- [x] Shared SSE abstraction supports GET/POST, AbortSignal, error normalization, typed events, and partial-output preservation.
- [x] Generation/Rewrite/Extend/CoAuthor use the shared streaming abstraction where backend SSE exists.
- [x] KB Interview Resume has TTL, opt-out, transparency, and minimized persisted data.
- [x] Touched frontend hubs are modularized rather than compressed.

### Docs Gate

- [ ] Agent instruction sources do not contradict RULE-02/RULE-02a.
- [ ] MCP/A2A scope is documented as planned and blocked by Q-001/Q-002 decisions.
- [ ] Feature/roadmap docs reflect AI feature freeze until stabilization passes.

### Platform Gate

- [x] Prompt/adoption gates are ratcheted: no new WARNs, decreasing legacy baseline.
- [x] No-growth exception gate is active.
- [x] Frontend file-size gate/report catches touched hard-limit violations.
- [x] Streaming compliance is represented in CI or an explicit architecture-review checklist with evidence.

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Legacy prompt warnings hide different severities | Cleanup order may be wrong | Classify warnings into MUST-fail, SHOULD-ratchet, and documented exception before content edits. |
| SSE migration changes event semantics | User-facing AI streams regress | Migrate by feature wrapper with tests for event ordering, abort, errors, and partial output. |
| Docs drift returns after one-time cleanup | Future agents receive weaker rules | Add doc-drift/no-weaker-rule gate and source hierarchy. |
| AI feature freeze blocks planned roadmap items | ANAL-005 and new AI ideas wait | This is intentional RULE-20 compliance; stabilization is the prerequisite for sustainable AI expansion. |

## Handoff Order

1. **Platform** establishes baselines and ratchet/no-growth gates in report-only mode for current legacy gaps, failing only new regressions.
2. **Core** fixes prompt regressions and KB adoption gaps against the baseline.
3. **Frontend** centralizes SSE and privacy-safe resume behavior, using the stabilized gates for validation.
4. **Docs** harmonizes source hierarchy and MCP/A2A roadmap wording after implementation details are stable.
5. **Platform + Testing** turn report-only legacy baselines into hard gates once the Core/Frontend cleanup has reduced them to zero or to ADR-approved exceptions.
