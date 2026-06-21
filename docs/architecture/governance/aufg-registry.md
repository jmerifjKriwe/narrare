# AUFG Registry — Architecture Governance Lifecycle

> **Status:** Active registry
> **Introduced by:** [ADR-047](../decisions/ADR-047-governance-drift-automation.md) (Proposed; registry is the active lifecycle surface while ADR acceptance remains open)
> **Maintained by:** Architecture Specialist
> **Last updated:** 2026-06-21 (CR-07 Follow-up v3 Phase A resolved — CR-AUFG-07-14 and CR-AUFG-07-15 implementation + enforcement + cross-layer evidence complete; CR-08 AUFG set resolved — ADR-051 accepted 2026-06-20; P0–P4 implementation + enforcement + cross-layer evidence complete)

This registry is the durable, tracked lifecycle surface for AUFGs, accepted risks,
accepted enhancements, and coverage pointers that originate from architecture reviews.
Review files under `_audit/` are evidence inputs, not the long-lived lifecycle SSOT.

---

## Lifecycle Contract

Every review finding that is material to architecture, release readiness, security,
observability, CI, or SSOT governance must have exactly one durable lifecycle state:

| State | Meaning |
|-------|---------|
| `open` | Actionable work exists and is not complete. |
| `in_progress` | A specialist is actively implementing the accepted scope. |
| `blocked` | Actionable, but waiting on an explicit dependency or user decision. |
| `resolved` | Acceptance criteria and Definition of Done are complete with exit evidence. |
| `accepted_risk` | Risk is knowingly accepted with owner, rationale, controls, and review date. |
| `accepted_enhancement` | Non-blocking improvement is accepted for future consideration with trigger/date. |
| `not_applicable` | Finding does not apply; rationale and reviewer are recorded. |
| `covered_by_existing_aufg` | Finding is explicitly delegated to another AUFG with no duplicate task. |

### Entry Schema

Each entry records: ID, title, source, status, priority, area, owner role,
dependencies, acceptance criteria, Definition of Done, exit evidence, and review
trigger/date where relevant.

Priorities use `P0` (release/security blocking), `P1` (high governance priority),
`P2` (planned hardening), `P3` (strategic/post-MVP exploration), and `P4`
(documentation/status-taxonomy/gate hardening that prevents future drift but does not
block the immediate runtime remediation once P0/P1 are complete).

---

## Active AUFGs

### CR-08 Configuration/Effect Drift AUFG Set

| Field | Value |
|-------|-------|
| IDs | CR-AUFG-08-01 through CR-AUFG-08-14 |
| Title | Configuration/Effect Drift Remediation |
| Source | CR-08 hardcoded-values audit and ADR-051 Configuration Effect Adoption Contract |
| Status | `resolved` (ADR-051 accepted 2026-06-20; P0–P4 implementation + enforcement + cross-layer evidence complete; SET-005 promoted to stable) |
| Priority | P0–P4 by phase |
| Area | Settings, Core LLM runtime, Writing context assembly, Provider catalogs, Frontend settings UI, Platform governance, Docs |
| Owner role | Architecture Specialist (contract), Core/Backend/Frontend/Platform/Docs Specialists by phase |
| Dependencies | ADR-045 run-limit enforcement, SET-005 token-limit cascade, `TokenLimitsService`, `ModelRoutingResolverImpl`, provider catalog/cache paths |
| Review trigger/date | Re-review if RULE-18b enforcement is weakened, if the Configuration Adoption Matrix regresses, or before any release-readiness claim that depends on configuration-effect integrity. ADR-051 acceptance review fired 2026-06-20. |

**Lifecycle decision:**

CR-08 findings are not allowed to remain as prose-only audit notes. The durable lifecycle
surface is the implementation-ready remediation specification at
`docs/features/remediation/cr-08-configuration-effect-drift.md`, governed by ADR-051
(accepted 2026-06-20). The AUFG set is resolved: ADR-051 is in effect, RULE-18b is
elevated to CONSTRAINTS.md, and every CR-AUFG-08 task has implementation + enforcement +
cross-layer evidence.

**Phase summary:**

- **P0:** CR-AUFG-08-09 Configuration Adoption Matrix; CR-AUFG-08-01 output-limit
  runtime enforcement (FIND-001); CR-AUFG-08-02 context tier runtime application
  (FIND-012).
- **P1:** CR-AUFG-08-03 token vocabulary unification; CR-AUFG-08-10 token settings
  UI/API/Core parity (FIND-013); CR-AUFG-08-07 model-limit calibration;
  CR-AUFG-08-11 model suitability policy. **Implementation + enforcement +
  cross-layer evidence recorded 2026-06-20; resolved with the CR-08 set on
  ADR-051 acceptance (2026-06-20).**
- **P2:** CR-AUFG-08-04 inline suggest cap; CR-AUFG-08-05 consistency caps layer;
  CR-AUFG-08-06 setup fallback catalogs/Ollama defaults; CR-AUFG-08-08 system model
  resolver; CR-AUFG-08-12 operator/default governance. **Implemented + enforced;
  evidence is recorded in the Configuration Adoption Matrix and remediation spec.**
- **P3:** CR-AUFG-08-13 governed defaults manifest for long-tail defaults.
  **Implemented + enforced; manifest and matrix entries are synchronized.**
- **P4:** CR-AUFG-08-14 docs/status taxonomy and audit-template/gate hardening.
  **Implemented + enforced; future structured material P0/P1 configuration/effect
  findings are matrix-gated.**

**Resolution:** P0-P4 are phase-complete with implementation and enforcement
evidence, and ADR-051 was accepted on 2026-06-20. The Definition of Done is
satisfied; the AUFG set is `resolved`.

**Acceptance criteria:**

- Every CR-08 value is classified as formal finding, implementation task, governed
  default with tests/rationale, covered existing path, not-applicable, or accepted risk
  with owner/exit criteria.
- No exposed/user-facing setting may be marked resolved without source → resolver →
  runtime consumer → enforcement regression evidence.
- SET-005 runtime-effect adoption is proven by matrix evidence (CR-AUFG-08-01/02) and UI/API/Core parity (CR-AUFG-08-03/10, FIND-013); SET-005 is promoted to stable.
- Platform governance blocks new unclassified P0/P1 configuration/effect findings once
  baseline is established.

**Definition of Done:** ✅ Met (2026-06-20).

- ADR-051 accepted 2026-06-20; RULE-18b elevated to CONSTRAINTS.md.
- `docs/features/remediation/cr-08-configuration-effect-drift.md` phase DoD complete (P0–P4).
- FIND-001, FIND-012, and FIND-013 have implementation-on-disk, enforcement, and
  cross-feature integration evidence (see Exit evidence).
- Governance registry entry updated with exit evidence and status `resolved`.

No remaining governed-debt or accepted-enhancement items were split out of this set.

**Exit evidence:** Complete (2026-06-20). ADR-051 accepted; CR-08 AUFG set resolved.

- **Architectural decision:** ADR-051 accepted 2026-06-20; RULE-18b (Configuration
  Effect Integrity) elevated to `docs/_shared/CONSTRAINTS.md` and synced to the
  extracted context rules files.
- **P0:** committed as `5769eaf2`.
- **P1 (2026-06-20):** implementation + enforcement + cross-layer evidence recorded
  for CR-AUFG-08-03, CR-AUFG-08-07, CR-AUFG-08-10/FIND-013, and CR-AUFG-08-11.
  Evidence paths are listed in
  `docs/features/remediation/cr-08-configuration-effect-drift.md` §P1 Implementation
  Evidence and in `docs/architecture/governance/configuration-adoption-matrix.yaml`.
  Reported validation: Core LLM tests, Backend/settings tests, Frontend targeted
  tests/type-check/lint/file-size check, matrix check, targeted P1 suite, and full
  `just check` PASS after security dependency updates.
- **P2:** implemented + enforced. Evidence in matrix entries `inline_suggest_cap`,
  `consistency_caps`, `setup_fallback_catalogs`, `system_background_model_defaults`,
  and `operator_default_governance`; remediation evidence references commits
  `138307c7` and `1aafad08`.
- **P3:** implemented + enforced. Evidence in
  `docs/architecture/governance/cr-08-p3-governed-defaults-manifest.md` and matrix
  entries `governed_defaults_manifest`, `embedding_threshold_search_limit`,
  `name_dedup_context_cap`, and `sse_connect_retry_defaults`; remediation evidence
  references commits `138307c7` and `1aafad08`.
- **P4:** implemented + enforced. Evidence in this registry, SET-005, CURRENT_STATE,
  testing standards, the CR-08 audit prompt template, matrix entry
  `status_doc_taxonomy`, and the current uncommitted Platform gate files:
  `scripts/check_configuration_matrix.py`, `scripts/governance/configuration_matrix.py`,
  `scripts/governance/_matrix_review_gate.py`, and
  `tests/unit/scripts/governance/test_configuration_matrix_review_gate.py`.
- **Ongoing enforcement:** `scripts/check_configuration_matrix.py` (PASS, 0
  violations) validates the matrix; `scripts/governance/_matrix_review_gate.py`
  blocks future unclassified structured material P0/P1 configuration-effect
  findings. Versioned audit-prompt markers `[P0|P1] [category: configuration-effect]`
  are required by the CR-08 content-review template.

---

### AUFG-04-01 — writing/story_suggest Orphan Template Disposition

| Field | Value |
|-------|-------|
| ID | AUFG-04-01 |
| Title | writing/story_suggest Orphan Template Disposition |
| Source | CR-04 Phase D ORPHAN-TEMPLATE gate (ADR-049 A6). The `writing/story_suggest` template has no production Python consumer; acknowledged as documented ratcheted debt in `scripts/architecture/_checkers/_check_prompt_orphan.py::_ORPHAN_EXEMPTIONS`. |
| Status | `open` |
| Priority | P2 |
| Area | Prompts, Writing features, Prompt-surface governance |
| Owner role | Architecture Specialist (disposition decision) + Implementation Specialist (rewire or delete) |
| Dependencies | WRITE-009 (Writer's Block Tools) feature planning; ADR-049 ORPHAN-TEMPLATE gate; `writing/story_suggest/system.md` (v1.3.0, 113 lines). |
| Review trigger/date | Re-review when WRITE-009 (or a dedicated story-suggestions feature) enters implementation, or by 2026-09-30 if no consumer is planned. |

**Background:**

`packages/core/narrare_core/prompts/_bundled/writing/en/story_suggest/system.md`
exists at v1.3.0 (113 lines, well-developed) but no service or agent loads it.
It is a `writing` sub-mode template that generates 3–5 distinct story
suggestions (plot developments, character moments, dialogue options, stylistic
alternatives). It appears to be a remnant of an earlier or redesigned
story-suggestions feature. Three probe scripts reference it
(`writing_probes.py`, `mode_data.py`, `validation_budget_probes.py`) but those
are test/probe harnesses, not production consumers.

**Disposition decision (Architecture, 2026-06-18):**

**Do NOT delete now.** The template is substantial, well-structured, and maps
plausibly to [WRITE-009 (Writer's Block Tools)](../../features/writing/WRITE-009-unblock.md),
which is `📋 planned`. Deleting it would discard meaningful work for a feature
that may still be implemented. The ORPHAN-TEMPLATE gate already acknowledges it
as documented ratcheted debt, so it is not silently suppressing CI.

**Acceptance criteria (one of):**

- **Rewire** — when WRITE-009 (or a dedicated story-suggestions feature) is
  implemented, route a `story_suggest` context-mode under an existing writing
  intent through PromptComposer so the template becomes runtime-loaded. Update
  the manifest and route-table; remove the `_ORPHAN_EXEMPTIONS` entry.
- **Delete** — if WRITE-009 is permanently descoped or redesigned to not use
  this prompt shape, delete the template and remove the `_ORPHAN_EXEMPTIONS`
  entry. Record the descoping rationale here.

**Definition of Done:**

- The `("writing", "story_suggest")` entry is removed from
  `_check_prompt_orphan.py::_ORPHAN_EXEMPTIONS` because it is either reachable
  by a manifest/route entry OR deleted.
- `just check-architecture` remains green with one fewer orphan exemption.
- This registry entry is updated with exit evidence and status `resolved`.

**Exit evidence:** Pending — open until WRITE-009 planning or a descoping decision.

---

### CR-AUFG-07-07 — KB Field Suggest AI-UX Lifecycle Compliance

| Field | Value |
|-------|-------|
| ID | CR-AUFG-07-07 |
| Title | KB Field Suggest AI-UX Lifecycle Compliance |
| Source | `_audit/results/content-review/cr-07-ux.md` §Aufgaben; KB Field Suggest (`useKBSessionSuggest` in `packages/web/lib/hooks/useKBSessions.ts`) uses raw TanStack mutation with unhandled errors and no visible cancel. |
| Status | `resolved` |
| Priority | P1 |
| Area | Frontend, KB assisted creation, AI UX, §16 compliance |
| Owner role | Frontend Specialist; Platform Specialist for checker/test enforcement |
| Dependencies | ADR-043; `docs/architecture/governance/ai-ux-compliance-v2.md`; `suggestField` SSE transport; KBAssistedCreationController UI. |
| Review trigger/date | Re-review when KB assisted creation AI flow changes, or before any CR-07 full-compliance claim. |

**Acceptance criteria:**

- KB Field Suggest is represented in the AI Operation Inventory.
- The flow either uses `useAIOperation` or a documented adapter with equivalent structured error mapping, visible loading state, and user-visible cancel.
- Cancellation reaches the `AbortSignal` passed to the `suggestField` transport; UI-only cancellation is not sufficient.
- Errors are mapped to structured `AIErrorResponse`/`studio.aiActions.*` messages.
- Component/hook tests prove loading, cancel, error mapping, and successful suggestion application.

**Definition of Done:**

- Frontend implementation and tests are present on disk.
- Platform AI-UX checks cover the operation inventory and signal/cancel requirements.
- Any linked `.ai_interaction_exclude` entry is removed or converted to a justified structural category.
- Registry status is updated with implementation + enforcement exit evidence.

**Exit evidence (2026-06-19):** Resolved — implementation + enforcement complete.
- **Design:** ADR-043 (`useAIOperation` primitive); `docs/architecture/governance/ai-ux-compliance-v2.md` §4 inventory.
- **Implementation:** `packages/web/lib/hooks/useKBSessions.ts` (`useKBSessionSuggest` runs via `execute: (signal) => suggestMutation.mutateAsync({ fieldKey, signal })` — the signal reaches the `suggestField` SSE transport); `packages/web/components/studio/kb/KBAssistedCreationController.ts` (visible cancel wiring); `packages/web/components/studio/kb/KBSessionFieldRow.tsx` (structured error rendering).
- **Enforcement:** Check 7 (`scripts/checks/_ai_interaction_checks/check_7_signal_propagation.py`) + Check 8 (`check_8_stale_exclude.py`); inventory entry `kb.field_suggest` (status `compliant`) in `scripts/checks/ai_operation_inventory.yaml`. Tests: `packages/web/components/studio/kb/__tests__/KBSessionFieldRow.test.tsx`, `packages/web/lib/hooks/__tests__/useKBSessions.actions.test.tsx`. `just check-ai-ux` reports 0 violations and 0 stale excludes.

---

### CR-AUFG-07-08 — KB Improve AI-UX Lifecycle Compliance

| Field | Value |
|-------|-------|
| ID | CR-AUFG-07-08 |
| Title | KB Improve AI-UX Lifecycle Compliance |
| Source | `_audit/results/content-review/cr-07-ux.md` §Aufgaben; KB Improve (`useKBImprove.ts`, `KBImprovePanel.tsx`) uses TanStack mutation/error mapping but lacks `useAIOperation` lifecycle and cancel support. |
| Status | `resolved` |
| Priority | P1 |
| Area | Frontend, KB improve, AI UX, §16 compliance |
| Owner role | Frontend Specialist; Platform Specialist for checker/test enforcement |
| Dependencies | ADR-043; `docs/architecture/governance/ai-ux-compliance-v2.md`; KB improve API contract; existing `mapSSEError`/REST error adapter. |
| Review trigger/date | Re-review when KB improve API or panel lifecycle changes, or before any CR-07 full-compliance claim. |

**Acceptance criteria:**

- KB Improve is represented in the AI Operation Inventory.
- The operation uses `useAIOperation` or an equivalent documented adapter for lifecycle, cancel, retry, and structured error state.
- A visible cancel control exists for the long-running AI operation and reaches the transport/API cancellation mechanism.
- Structured error mapping remains actionable and i18n-backed.
- Tests cover loading state, cancel behavior, error display, and apply/selection behavior after remediation.

**Definition of Done:**

- Frontend implementation and tests are present on disk.
- Platform gates can detect future missing lifecycle/cancel/error coverage for KB Improve.
- Registry status is updated with implementation + enforcement exit evidence.

**Exit evidence (2026-06-19):** Resolved — implementation + enforcement complete.
- **Design:** ADR-043; `docs/architecture/governance/ai-ux-compliance-v2.md` §4.
- **Implementation:** `packages/web/components/studio/kb/KBImprovePanel.tsx` migrated to `useAIOperation` with `execute: (signal) => analyzeMutation.mutateAsync(signal)`; `packages/web/components/studio/kb/_components/ImproveLoadingState.tsx` (cancel UI); `packages/web/lib/hooks/useKBImprove.ts` (signal support).
- **Enforcement:** Check 7 (`check_7_signal_propagation.py`) + Check 8 (`check_8_stale_exclude.py`); inventory entry `kb.improve` (status `compliant`). Tests: `packages/web/components/studio/kb/__tests__/KBImprovePanel.test.tsx`, `packages/web/lib/hooks/__tests__/useKBImprove.test.tsx`. `just check-ai-ux` reports 0 violations.

---

### CR-AUFG-07-09 — Timeline Extraction useAIOperation or Governed Adapter

| Field | Value |
|-------|-------|
| ID | CR-AUFG-07-09 |
| Title | Timeline Extraction useAIOperation or Governed Adapter |
| Source | `_audit/results/content-review/cr-07-ux.md` §Aufgaben; `useTimelineExtraction.ts` uses manual AbortController for callback-based SSE and is currently excluded in `scripts/checks/.ai_interaction_exclude`. |
| Status | `resolved` |
| Priority | P1 |
| Area | Frontend, Timeline extraction, SSE, AI UX, exclude governance |
| Owner role | Frontend Specialist; Platform Specialist for stale-exclude and signal-propagation checks |
| Dependencies | ADR-043 note on callback SSE wrappers; `extractExpressionsSSE`; `docs/architecture/governance/ai-ux-compliance-v2.md`; current exclude entry for `packages/web/lib/hooks/useTimelineExtraction.ts`. |
| Review trigger/date | Re-review when timeline extraction SSE wrapper changes, when `useAIOperation` callback adapter is introduced, or before any CR-07 full-compliance claim. |

**Acceptance criteria:**

- Timeline Extraction is represented in the AI Operation Inventory.
- Preferred path: migrate callback SSE lifecycle to `useAIOperation` by converting callback errors to Promise rejection.
- If a non-hook adapter remains necessary, the exception is justified as a governed adapter with visible cancel, structured error mapping, partial output preservation, retry behavior, and linked AUFG evidence.
- `cancelExtraction` is exposed in the visible UI where extraction can exceed 2 seconds.
- The linked `.ai_interaction_exclude` entry is removed or updated with AUFG-linked, non-stale governance metadata.

**Definition of Done:**

- Frontend implementation/tests prove cancel reaches `AbortSignal` and errors are structured.
- Platform stale-exclude and lifecycle sync gates cover this AUFG.
- Registry status is updated with implementation + enforcement exit evidence.

**Exit evidence (2026-06-19):** Resolved via governed adapter — partial migration plus justified exception.
- **Design:** ADR-043 non-react-transport exception category; `docs/architecture/governance/ai-ux-compliance-v2.md` §4.
- **Implementation:** `packages/web/components/studio/planning/timeline/TimelineExtractionReview.tsx` and `ChapterSelector.tsx` expose a visible `cancelExtraction` control that reaches the callback-SSE `AbortController`; structured error mapping via `mapSSEError` is applied. The callback-based SSE transport cannot adopt the React `useAIOperation` hook, so a justified governed exception remains (§16.2 cancel + §16.5 error migration applied).
- **Enforcement:** Inventory entry `extraction.timeline` (status `governed_exception`) carries an AUFG link; the `.ai_interaction_exclude` entry for `packages/web/lib/hooks/useTimelineExtraction.ts` is fresh (re-evaluated 2026-06-19), AUFG-linked, and structural (non-react-transport). Check 8 (`check_8_stale_exclude.py`) rejects stale/unlinked excludes; Check 9 (`check_9_lifecycle_sync.py`) keeps the AUFG ID in sync. Test: `packages/web/components/studio/planning/timeline/__tests__/TimelineExtractionReview.test.tsx`. `just check-ai-ux` reports 0 violations and 0 stale excludes.

---

### CR-AUFG-07-10 — GhostText Visible Loading/Status Indicator

| Field | Value |
|-------|-------|
| ID | CR-AUFG-07-10 |
| Title | GhostText Visible Loading/Status Indicator |
| Source | `_audit/results/content-review/cr-07-ux.md` §Aufgaben; GhostText fetches SSE suggestions from a TipTap extension without visible loading indication. |
| Status | `resolved` |
| Priority | P1 |
| Area | Frontend, TipTap GhostText, AI UX, non-React extension governance |
| Owner role | Frontend Specialist; Platform Specialist for inventory/exclude enforcement |
| Dependencies | ADR-043 structural exclude category for non-React extensions; `GhostText.ts` / ghost-text helpers; `createSseSuggestionFetcher`; `docs/architecture/governance/ai-ux-compliance-v2.md`. |
| Review trigger/date | Re-review when GhostText extension lifecycle changes, when a React controller can pass lifecycle state, or before any CR-07 full-compliance claim. |

**Acceptance criteria:**

- GhostText Suggestion Fetch is represented in the AI Operation Inventory.
- Users receive visible loading/status feedback during suggestion fetch without hardcoded visible strings.
- Any visible text is provided through localized extension options, not hardcoded in ProseMirror DOM.
- Existing non-React AbortController governance remains constrained to the extension adapter and does not leak manual lifecycle patterns into React components.
- Tests or targeted extension assertions prove loading/status state appears and clears.

**Definition of Done:**

- Frontend implementation and tests are present on disk.
- Platform inventory/stale-exclude checks keep the non-React exception governed.
- Registry status is updated with implementation + enforcement exit evidence.

**Exit evidence (2026-06-19):** Resolved via governed non-React extension + visible status indicator.
- **Design:** ADR-043 non-react-extension structural category; `docs/architecture/governance/ai-ux-compliance-v2.md` §4.
- **Implementation:** `packages/web/components/studio/editor/extensions/GhostText.ts` (+ `ghost-text-helpers.ts`, `ghost-text-types.ts`) renders a localized fetching-status ProseMirror decoration driven by `_isFetching` extension storage. The visible text comes from the React-controlled `fetchingStatusText` Extension option (`packages/web/components/studio/editor/TipTapEditorController.ts` → `t("aiActions.aiThinking")`), not from hardcoded ProseMirror DOM strings.
- **Enforcement:** Inventory entry `editor.ghost_text` (status `governed_exception`, lifecycle `non_react_extension`); the exclude entry for `ghost-text-helpers.ts` is fresh, structural, and AUFG-linked. Check 8 (`check_8_stale_exclude.py`) + Check 10 (`check_10_operation_inventory.py`) keep the non-React exception governed and the inventory complete. Test: `packages/web/components/studio/editor/extensions/__tests__/ghost-text-fetching.test.ts`. `just check-ai-ux` reports 0 violations.

---

### CR-AUFG-07-11 — KB Enhance Cancel Signal Propagation

| Field | Value |
|-------|-------|
| ID | CR-AUFG-07-11 |
| Title | KB Enhance Cancel Signal Propagation |
| Source | `_audit/results/content-review/cr-07-ux.md` §Aufgaben plus coordinator discovery; `EnhanceLoadingState` has cancel UI, but `execute: () => onRequestEnhance()` and mutation calls may not pass the `AbortSignal` to transport. |
| Status | `resolved` |
| Priority | P1 |
| Area | Frontend, KB enhance, signal propagation, AI UX |
| Owner role | Frontend Specialist; Platform Specialist for signal-propagation checker |
| Dependencies | ADR-043; `KBEnhanceReview.tsx`; `EnhanceLoadingState`; `requestEnhance` transport; `docs/architecture/governance/ai-ux-compliance-v2.md`. |
| Review trigger/date | Re-review when KB enhance request lifecycle changes, or before any CR-07 full-compliance claim. |

**Acceptance criteria:**

- KB Enhance is represented in the AI Operation Inventory.
- `useAIOperation.execute(signal)` passes the signal through every intermediate callback to the API wrapper/transport.
- The visible cancel control aborts the in-flight transport, not only local UI state.
- Tests prove cancel invokes the transport with an abort signal and stops the loading state.

**Definition of Done:**

- Frontend implementation and tests are present on disk.
- Platform signal-propagation gate can detect this class of regression.
- Registry status is updated with implementation + enforcement exit evidence.

**Exit evidence (2026-06-19):** Resolved — the cancel signal now reaches transport.
- **Design:** ADR-043; `docs/architecture/governance/ai-ux-compliance-v2.md` §4.
- **Implementation:** `packages/web/components/studio/kb/KBEnhanceReview.tsx` (`execute: (signal) => onRequestEnhance(signal)`); `packages/web/components/studio/kb/KBAssistedCreationController.ts` (`handleRequestEnhance(signal?: AbortSignal)` → `enhanceMutation.mutate(signal, …)` — the signal propagates to the `requestEnhance` SSE transport). `packages/web/components/studio/kb/_components/EnhanceLoadingState.tsx` provides the visible cancel.
- **Enforcement:** Check 7 (`scripts/checks/_ai_interaction_checks/check_7_signal_propagation.py`) flags `execute` signatures that drop the signal; inventory entry `kb.enhance` (status `compliant`). Test: `packages/web/components/studio/kb/__tests__/KBEnhanceReview.test.tsx` (signal-propagation case). `just check-ai-ux` reports 0 violations.

---

### CR-AUFG-07-12 — Deprecated AI-Action i18n Alias Prevention

| Field | Value |
|-------|-------|
| ID | CR-AUFG-07-12 |
| Title | Deprecated AI-Action i18n Alias Prevention |
| Source | `_audit/results/content-review/cr-07-ux.md` §Aufgaben; `ui-principles.md` §16.8 marks exact aliases such as `aiModal.accept`, `generation.stop`, `annotation.keep`, and `rewrite.replace` as deprecated, but prevention is incomplete. |
| Status | `resolved` |
| Priority | P1 |
| Area | Frontend i18n, AI action vocabulary, Platform lint/checker |
| Owner role | Frontend Specialist for key migration/removal; Platform Specialist for lint/checker; Docs Specialist for §16.9 sync |
| Dependencies | RULE-16; `packages/web/messages/{de,en,fr}/studio.json`; `docs/development/ui-principles.md` §16.8; `docs/architecture/governance/ai-ux-compliance-v2.md`. |
| Review trigger/date | Re-review when studio i18n namespaces change, or before any CR-07 full-compliance claim. |

**Acceptance criteria:**

- The exact deprecated §16.8 AI-action aliases are absent from TS/TSX usage or blocked by a CI-visible checker.
- Broader namespaces (`generation.*`, `rewrite.*`, etc.) are not blanket-banned when used for non-action copy; the gate targets exact deprecated AI-action aliases.
- If stale key definitions remain in locale JSON files for compatibility, the checker still forbids usage and the inventory records the compatibility rationale.
- 3-locale parity for canonical `studio.aiActions.*` remains green.

**Definition of Done:**

- Frontend removes or stops using deprecated aliases and updates tests as needed.
- Platform checker/lint rule prevents reintroduction of exact deprecated aliases.
- Docs update §16.9 to reflect the implemented gate.
- Registry status is updated with implementation + enforcement exit evidence.

**Exit evidence (2026-06-19):** Resolved — deprecated aliases removed and CI-gated.
- **Design:** RULE-16; ADR-043; `docs/development/ui-principles.md` §16.8/§16.9; `docs/architecture/governance/ai-ux-compliance-v2.md` §4.
- **Implementation:** `packages/web/components/studio/editor/RewriteSuggestionModal.tsx` migrated `aiModal.original` → `t("aiActions.original")`; the 16 exact §16.8 deprecated AI-action aliases are absent from TS/TSX usage; locale files (`packages/web/messages/{de,en,fr}/studio.json`) cleaned.
- **Enforcement:** Check 6 (`scripts/checks/_ai_interaction_checks/check_6_deprecated_alias.py`) blocks the exact deprecated aliases (whole namespaces are NOT blanket-banned); inventory entry `vocabulary.ai_actions` (status `compliant`). Platform tests: `tests/unit/scripts/checks/test_check_6_deprecated_alias.py`. §16.9 documents the implemented gate. `just check-ai-ux` reports 0 violations.

---

### CR-AUFG-07-13 — Consistent Keyboard Shortcuts for AI Output Actions

| Field | Value |
|-------|-------|
| ID | CR-AUFG-07-13 |
| Title | Consistent Keyboard Shortcuts for AI Output Actions |
| Source | `_audit/results/content-review/cr-07-ux.md` §Aufgaben; rewrite modal, generation review, KB enhance review, and co-author panel have inconsistent or incomplete keyboard shortcuts for accept/reject/retry actions. |
| Status | `resolved` |
| Priority | P1 |
| Area | Frontend, accessibility, keyboard UX, AI action consistency |
| Owner role | Frontend Specialist; Docs Specialist for shortcut documentation; Platform Specialist for tests/gate evidence |
| Dependencies | KEYBOARD-001 precedent; `docs/development/ui-principles.md` §16; `docs/architecture/governance/ai-ux-compliance-v2.md`; affected AI output action components. |
| Review trigger/date | Re-review when AI output action patterns change, or before any CR-07 full-compliance claim. |

**Acceptance criteria:**

- The AI Operation Inventory records keyboard behavior for rewrite, generation review, KB enhance review, and co-author actions.
- A consistent shortcut scheme is implemented and documented for applicable accept/reject/retry/cancel actions.
- Shortcuts do not conflict with text-entry contexts or existing TipTap shortcuts; focus handling remains accessible.
- Tests prove shortcuts trigger the same handlers as visible buttons.

**Definition of Done:**

- Frontend implementation and tests are present on disk.
- Docs reflect the final shortcut scheme in user-facing/developer guidance where applicable.
- Platform test/check evidence prevents silent regression for the covered components.
- Registry status is updated with implementation + enforcement exit evidence.

**Exit evidence (2026-06-19):** Resolved — consistent shortcut scheme + per-operation inventory.
- **Design:** KEYBOARD-001 precedent; ADR-043; `docs/architecture/governance/ai-ux-compliance-v2.md` §4.
- **Implementation:** shared `packages/web/lib/ai-action-shortcuts.ts` (`Ctrl/Cmd+Enter` → accept/apply) consumed by `packages/web/components/studio/editor/GenerationPanel.tsx`, `packages/web/components/studio/kb/KBEnhanceReview.tsx`, `packages/web/components/studio/editor/_components/CoAuthorReviewPhase.tsx`, and `packages/web/components/studio/editor/RewriteSuggestionModal.tsx`.
- **Enforcement:** Inventory entries (`writing.rewrite`, `writing.generation`, `writing.co_author`, `kb.enhance`, `vocabulary.keyboard_shortcuts`) record per-operation keyboard behaviour (status `compliant`); Check 10 (`check_10_operation_inventory.py`) validates the inventory fields. Tests: `packages/web/components/studio/editor/__tests__/GenerationPanel.keyboard.test.tsx`, `CoAuthorReviewPhase.keyboard.test.tsx`, `packages/web/components/studio/kb/__tests__/KBEnhanceReview.test.tsx`, `packages/web/components/studio/editor/__tests__/RewriteSuggestionModal.test.tsx`. `just check-ai-ux` reports 0 violations.

---

### CR-07 Follow-up v3 AUFG Set — Residual AI UX Compliance and Modernization

| Field | Value |
|-------|-------|
| IDs | CR-AUFG-07-14 through CR-AUFG-07-24 |
| Title | CR-07 Follow-up v3: residual §16 compliance, PROMPT-003/ONBOARD-001 gaps, and §8 modern AI-UX enhancements |
| Source | `docs/architecture/governance/cr-07-followup-v3.md`; CR-07 UX audit residuals after CR-AUFG-07-07 through CR-AUFG-07-13 closure. |
| Status | `open` |
| Priority | P1 for Phase A/B hardening; P2/P3 for Phase C enhancements by work item |
| Area | Frontend AI UX, i18n, prompts, onboarding, writing sessions, KB, analysis, learning/feedback, Platform governance |
| Owner role | Architecture Specialist (spec/re-review), Frontend/Core/Backend/Platform/Docs Specialists by phase |
| Dependencies | ADR-043, `ai-ux-compliance-v2.md`, PROMPT-003, ONBOARD-001, LEARN-001, WRITE-005/006/007, KB-002/003, ANAL-001, existing AI Operation Inventory |
| Review trigger/date | Re-review before any item is marked `resolved`; on material phase boundary or contract changes; by 2026-09-30 if Phase A has not shipped. |

**Lifecycle decision:**

The follow-up set is intentionally `open`. The governing architecture specification is
`docs/architecture/governance/cr-07-followup-v3.md`. No item in this set may be marked
`resolved` from documentation alone; each requires implementation + enforcement evidence
per `docs/development/finding-lifecycle.md`.

**Work items:**

| ID | Phase | Title | Status | Priority | Acceptance summary |
|----|-------|-------|--------|----------|--------------------|
| CR-AUFG-07-14 | A | §16 Consistency/i18n fallback hardening | `resolved` | P1 | Remove hardcoded visible fallbacks such as `t(...) || "..."`; fix Consistency error fallback; add checker preventing reintroduction. |
| CR-AUFG-07-15 | A | GhostText visible error affordance | `resolved` | P1 | Decide and implement non-blocking localized GhostText error affordance; inventory and tests cover error/retry semantics. |
| CR-AUFG-07-16 | B | PROMPT-003 contract-first implementation | `open` | P1 | Provider-free resolved preview, variable metadata/provenance, diagnostics, reset semantics, optional SSE live test, and contract tests across Core/Backend/Frontend. |
| CR-AUFG-07-17 | B | ONBOARD-001 KB + Storyboard + AI aha moment | `resolved` | P2 | Implemented: 3 new conceptual tour steps (KB→AI, Storyboard→AI, before/after demo) in `feature-tour-steps.ts`; DE/EN/FR `studio.json` keys; replay path intact. Enforcement: `feature-tour-concept-steps.test.tsx`, `tour-no-overclaim.test.ts` (RULE-22 over-claim guard), `just check-ai-ux`, i18n parity gate. ONBOARD-001’s stable base scope is unchanged. |
| CR-AUFG-07-18 | C | Standardized diff view across AI outputs | `open` | P2 | Shared diff vocabulary/component contract for Rewrite, Co-Author, KB Enhance, and Beta Reader. |
| CR-AUFG-07-19 | C | Prompt history | `open` | P2 | Prompt override history/restore/compare semantics after PROMPT-003 contracts exist. |
| CR-AUFG-07-20 | C | Slash commands for AI actions | `open` | P3 | Command grammar, i18n discoverability, TipTap conflict handling, and routed AI action tests. |
| CR-AUFG-07-21 | C | SessionPanel server-side stop and WebSocket recovery | `open` | P2 | Stop reaches server-side session state; connection-loss recovery preserves partial state and is tested. |
| CR-AUFG-07-22 | C | Regenerate with style variants | `open` | P2 | Consistent regenerate/variant UI and request contract across eligible AI output surfaces. |
| CR-AUFG-07-23 | C | Emotional intensity curve | `open` | P3 | Dedicated spec decides deterministic/LLM/hybrid approach, chart contract, and tests. |
| CR-AUFG-07-24 | C | AI feedback rating expansion | `open` | P2 | Extend rating to Co-Author, KB flows, and Chat through LEARN-001-compatible persistence/memory contract. |

**Definition of Done for the set:**

- Phase A checker and frontend cleanup are implemented and CI-visible. ✅ Met (2026-06-21): CR-AUFG-07-14 and CR-AUFG-07-15 have implementation + enforcement + test evidence.
- PROMPT-003 remains `planned` until its Core/Backend/Frontend contracts and enforcement are complete.
- ONBOARD-001 remains `stable`; the conceptual follow-up has its own AUFG exit evidence.
- Every Phase C item has a dedicated feature/spec slice before implementation.
- This registry entry is updated with per-ID exit evidence only after implementation and enforcement exist.

**Exit evidence:**

Phase A (CR-AUFG-07-14, CR-AUFG-07-15) — Resolved (2026-06-21). Phase B onboarding follow-up (CR-AUFG-07-17) — Resolved (2026-06-21). CR-AUFG-07-16 and Phase C items remain pending.

#### CR-AUFG-07-14 — §16 Consistency/i18n fallback hardening

**Exit evidence (2026-06-21):** Resolved — implementation + enforcement + tests complete.
- **Design:** RULE-16 (no visible English fallback strings); ADR-043; `docs/architecture/governance/ai-ux-compliance-v2.md` §4; CR-07 Follow-up v3 Phase A Task 1–5 plan.
- **Implementation:**
  - `packages/web/components/studio/kb/ConsistencyCheckPanel.tsx` — removed `t(...) || "Check failed"` and three other visible `|| "..."` fallbacks; error rendering now uses structured i18n-key fallback (`error?.userMessage || t(error?.i18nKey ?? "aiActions.errorDefault")`).
  - `packages/web/components/studio/kb/WorldbuildingAnalysisPanel.tsx`, `WorldbuildingAnalysisCards.tsx`, `KBAssistedCreationFooter.tsx`, `KBAssistedCreationHeader.tsx`, `KBSessionFieldList.tsx`, `KBTagInput.tsx`, `KBEntryDetail.tsx`, `SidebarActions.tsx`, `AnalysisTabs.tsx`, `AnalysisScoreHeader.tsx`, `AnalysisError.tsx`, `ConsistencyError.tsx`, `ConsistencyLoading.tsx`, `ConsistencyResults.tsx`, `InterviewCompleteState.tsx`, `InterviewHeader.tsx`, `InterviewQuestionCard.tsx`, `_components/EnhanceReviewBulkActions.tsx`, `_components/EnhanceReviewCard.tsx`, `_components/EnhanceReviewHeader.tsx`, `_components/ImproveReviewSection.tsx` — all visible `t(...) || "English"` fallbacks removed; locale keys rely on the i18n registry instead.
  - `packages/web/components/studio/kb/useWorldbuildingAnalysis.ts` — localized apply-success and apply-error detail strings via two new keys: `worldbuilding.failedWithDetails` and `kb.failedToSaveEntry` (added to `de/en/fr/studio.json`).
- **Enforcement:**
  - Check 12 (`scripts/checks/_ai_interaction_checks/check_12_visible_i18n_fallbacks.py`) scans `packages/web/components/studio/kb/**` and `packages/web/components/studio/editor/**` production TS/TSX for `t(...) || "..."`, `t(...) ?? "..."`, and capitalized-literal `|| / ??` fallbacks. Governed allowlist at `scripts/checks/_ai_interaction_checks/visible_i18n_fallback_allowlist.yaml` (currently empty — no justified production-visible fallbacks).
  - Wired into `just check-ai-ux` via `scripts/checks/check_ai_interaction_compliance.py` (12 checks total).
  - Inventory entries `analysis.consistency`, `analysis.worldbuilding`, `kb.field_suggest`, `kb.enhance`, `kb.improve` remain `compliant`.
- **Tests:** `tests/unit/scripts/checks/test_check_12_visible_i18n_fallbacks.py` (23 cases: pattern detection, allowlist honoring, test-file exclusion, scan-directory scope); frontend regression coverage in `ConsistencyCheckPanel.test.tsx`, `WorldbuildingAnalysisPanel.test.tsx`, `WorldbuildingAnalysisCards.test.tsx`, `KBAssistedCreationFooter.test.tsx`, `KBSessionFieldList.test.tsx`, `KBTagInput.test.tsx`, `useWorldbuildingAnalysis.test.tsx`.
- **Validation:** `just check-ai-ux` reports 12 checks, 0 violations, 0 stale excludes.

#### CR-AUFG-07-15 — GhostText visible error affordance

**Exit evidence (2026-06-21):** Resolved — implementation + enforcement + tests complete.
- **Design:** ADR-043 non-react-extension structural category; ADR-043 Note 7 (localized strings via Extension options, no hardcoded English in ProseMirror DOM); CR-07 Follow-up v3 Phase A Task 2–3 plan. AbortError stays silent (normal typing cancellation); non-AbortError shows a transient, non-blocking, low-noise decoration that auto-clears.
- **Implementation:**
  - `packages/web/components/studio/editor/extensions/ghost-text-error-status.ts` (new, 77 lines, RULE-04 extraction) — `showErrorStatus(storage, editor, options)` sets `_errorStatusVisible`, anchors the decoration at the cursor, and schedules an auto-clear via `setTimeout` after `options.errorStatusDurationMs` (default 4000ms). `clearErrorStatus(storage, editor?)` cancels the timer and dispatches an empty transaction to re-render. Visible text comes from `options.errorStatusText` (React-injected), never hardcoded English.
  - `packages/web/components/studio/editor/extensions/ghost-text-types.ts` — `GhostTextOptions.errorStatusText` and `errorStatusDurationMs`; `GhostTextStorage._errorStatusVisible` and `_errorTimer`.
  - `packages/web/components/studio/editor/extensions/GhostText.ts` — decoration plugin renders the `ghost-text-error` widget span only when `_errorStatusVisible && !_isFetching && !currentSuggestion && cursor at anchor`; `hintText` default changed from `"Tab accept · Esc dismiss · → word"` to `""` (no hardcoded English; `TipTapEditorController` injects `t("ghostText.hint")`).
  - `packages/web/components/studio/editor/extensions/ghost-text-helpers.ts` — `fetchAndStreamSuggestion` catch block: AbortError → silent return; other errors → `showErrorStatus(...)` instead of `clearAll(...)`. `clearErrorStatus` is called on new fetch, cache hit, `clearAll`, and `cleanup` so retry/success/typing-clear all suppress the error.
  - `packages/web/components/studio/editor/TipTapEditorController.ts` — injects `errorStatusText: t("ghostText.errorUnavailable")` and `errorStatusDurationMs: 4000` via Extension options.
  - `packages/web/styles/editor.css` — `.ghost-text-error` styling (low-noise, muted).
  - `packages/i18n/messages/{de,en,fr}/studio.json` — new key `ghostText.errorUnavailable`.
- **Enforcement:**
  - Inventory entry `editor.ghost_text` (status `governed_exception`) now documents error/retry semantics: localized error status via Extension options, transient auto-clear after `errorStatusDurationMs`, retry/success/cache-hit clear via `clearErrorStatus`.
  - Check 12 prevents reintroduction of hardcoded English fallbacks in `packages/web/components/studio/editor/**`.
  - The pre-existing Check 2 governed exclude for `ghost-text-helpers.ts` (non-react-extension) remains fresh and AUFG-linked (`re_evaluated=2026-06-19`).
- **Tests:** `packages/web/components/studio/editor/extensions/__tests__/ghost-text-fetching.test.ts` (10 cases: error decoration appears on non-AbortError, AbortError stays silent, transient auto-clear after duration, manual clear on new fetch, clear on cache hit, clear on cleanup, localized text from options, no overlap with fetching indicator, no hardcoded English default).
- **Validation:** `just check-ai-ux` reports 12 checks, 0 violations, 0 stale excludes; `just check-frontend-size` reports 0 new debt.

---

### AUFG-05-07 — CORS-/Rate-Limiting-Security-Audit

| Field | Value |
|-------|-------|
| ID | AUFG-05-07 |
| Title | CORS-/Rate-Limiting-Security-Audit |
| Source | Review-05 release/security finding captured durably in ADR-047 §Context (`CORS and rate-limiting were not fully audited`). |
| Status | `resolved` |
| Priority | P0 |
| Area | Security, Backend, API middleware, deployment configuration |
| Owner role | Backend/Security Specialist, with Platform review for deploy-time configuration |
| Dependencies | ADR-009 security modernization; current FastAPI middleware stack; deployment environment configuration; rate-limit backend availability. |
| Review trigger/date | Re-review before the next release-readiness claim or whenever CORS origins/rate-limit storage changes. |

**Acceptance criteria:**

- All HTTP entry points have an explicit CORS policy assessment: allowed origins,
  credentials behavior, local-dev allowances, and production hardening.
- Rate limiting is audited for auth, AI/SSE, generation, setup, and write-heavy
  state-changing endpoints.
- Any environment-specific allowance is documented as configuration, not hardcoded
  router behavior.
- Security audit output distinguishes required fixes from accepted risk; no prose-only
  findings remain.

**Definition of Done:**

- Backend/Security audit document or architecture handoff is added to tracked docs.
- Required code/config changes are implemented with tests or checker evidence.
- `just check-ssot` and relevant architecture/security checks pass after implementation.
- This registry entry is updated with exit evidence and status `resolved` or
  `accepted_risk`.

**Exit evidence (2026-06-14):** Audit completed. Full audit document at
`docs/architecture/governance/security-audit-cors-rate-limiting.md`. Findings:

- **CORS:** PASS. No wildcard origins with credentials in any environment.
  Dev/test: `["http://localhost:3000"]` (specific origin). Production: `[]`
  (CORS disabled; Next.js reverse proxy makes API same-origin from browser).
  `allow_credentials=True` never paired with wildcard origins. Cookie
  credentials: `httpOnly`, `secure=production`, `samesite=lax`.
- **Rate limiting:** Auth `register` (3/min) and `login` (5/min) are rate-limited
  via `Depends()`. 14 AI/SSE/WebSocket endpoint classes lack rate limits →
  AUFG-05-12 created (P1/P2, `open`). 14 CRUD/auth-read endpoint classes lack
  rate limits → accepted risk (AR-05-03, AR-05-04, justified by local-first
  single-user model).
- **Architecture discrepancy:** TECH_STACK.md/ADR-009 specify Redis-based
  rate limiting, but implementation uses in-memory `pyrate_limiter` (Redis init
  never called). Accepted risk AR-05-02 — functional for single-instance; revisit
  if multi-instance deployment is pursued.
- **Follow-up items:** AUFG-05-12 (rate limiting for AI endpoints), AE-05-03
  (CORS origins as Settings field), AR-05-02/03/04 (accepted risks).
- **Release-security checklist:** Embedded in §5 of the audit document.

No code changes in this slice (audit + documentation only). Implementation
of AI-endpoint rate limits is tracked in AUFG-05-12.

---

### AUFG-05-08 — CSRF-Strategie für state-changing Endpoints

| Field | Value |
|-------|-------|
| ID | AUFG-05-08 |
| Title | CSRF-Strategie für state-changing Endpoints |
| Source | Review-05 release/security finding captured durably in ADR-047 §Context (`CSRF token validation was not explicitly decided for state-changing endpoints`). |
| Status | `resolved` |
| Priority | P0 |
| Area | Security, Backend architecture, Web client auth/session behavior |
| Owner role | Architecture Specialist for strategy decision; Backend/Security Specialist for implementation |
| Dependencies | Auth/session architecture; cookie/header credential mode; CORS audit AUFG-05-07; four-client model constraints from CONSTRAINTS.md RULE-12. |
| Review trigger/date | Re-review before enabling browser-authenticated state changes in production or changing auth credential transport. Re-open if any architectural invariant in §12 of the strategy document is violated. |

**Acceptance criteria:**

- A tracked CSRF strategy decision exists and explicitly covers browser WebUI,
  MCP, A2A, and CLI clients without making one client call another.
- Every state-changing route category is classified as protected, not applicable,
  or covered by a stronger same-site/token/auth mechanism.
- Chosen strategy includes failure semantics, test strategy, and migration impact.
- Any exception is documented as `accepted_risk` with owner, controls, and review date.

**Definition of Done:**

- Architecture decision or feature/security spec records the chosen CSRF strategy.
- Backend implementation follows the chosen contract without router-level hardcoded
  security shortcuts.
- Integration tests cover accepted and rejected state-changing requests where applicable.
- Registry status is updated with exit evidence.

**Exit evidence (2026-06-14):** CSRF strategy decision completed. Full strategy document
at `docs/architecture/governance/csrf-strategy.md`. Decision summary:

- **Strategy chosen:** SameSite=Lax (existing) + Origin/Referer validation (defense-in-
  depth, follow-up AUFG-05-13). No Double-Submit-Token.
- **Root cause:** The backend authenticates state-changing endpoints via `Authorization:
  Bearer` header (HTTPBearer), NOT via cookies. CSRF is structurally inapplicable because
  the browser cannot auto-attach `Authorization` headers cross-origin. Only two endpoints
  (`/auth/refresh`, `/auth/logout`) use cookie-based auth, and they are protected by
  SameSite=Lax + path-restriction with no data-integrity impact.
- **Options evaluated:** Option A (SameSite=Lax + Origin/Referer — chosen), Option B
  (Double-Submit-Token — rejected: solves non-existent vector), Option C (SameSite=Strict
  — rejected: breaks `restoreSession()` UX), Option D (combination — rejected:
  over-engineering).
- **Endpoint inventory:** ~85 route handlers are N/A (Bearer-authenticated, CSRF-
  inapplicable); 2 are cookie-protected (SameSite=Lax); ~6 are N/A (no auth); 1 WebSocket
  endpoint has CSWSH risk (→ AUFG-05-13).
- **Accepted risk:** AR-05-05 (no Double-Submit-Token) — rationale: Bearer auth makes
  CSRF structurally inapplicable. Controls: Bearer auth, SameSite=Lax, JSON-only API,
  CORS disabled in prod, Origin/Referer validation (pending AUFG-05-13).
- **4-client compatibility:** WebUI (Origin validated), CLI/MCP/A2A (Bearer-exempt from
  Origin check). No client calls another.
- **Architectural invariants:** 5 invariants documented (INV-1 through INV-5) — backend
  must never add cookie-based auth for state-changing endpoints without re-review.
- **Follow-up:** AUFG-05-13 (Origin/Referer validation + WebSocket Origin check) — P1,
  open, before public release.

No code changes in this slice (architecture decision + documentation only). Implementation
of Origin/Referer validation is tracked in AUFG-05-13.

---

### AUFG-05-09 — Secret-Scanning als CI-Gate

| Field | Value |
|-------|-------|
| ID | AUFG-05-09 |
| Title | Secret-Scanning als CI-Gate |
| Source | Review-05 release/security finding captured durably in ADR-047 §Context (`Secret scanning was not configured as a dedicated CI gate`). |
| Status | `resolved` |
| Priority | P0 |
| Area | Platform, CI, supply-chain security |
| Owner role | Platform Specialist |
| Dependencies | Existing GitHub Actions CI; local developer check workflow; Gitleaks CI/dev gate; optional GitHub Secret Scanning where repository settings support it; baseline policy for historical findings; no `--no-verify` bypass. |
| Review trigger/date | Re-review when CI workflow topology changes or before first public release artifact. |

**Tooling decision (Architecture, 2026-06-14):**

- **Chosen gate:** Gitleaks is the required repository-local secret-scanning gate for CI
  and local developer handoff commands.
- **Defense in depth:** GitHub Secret Scanning / push protection should be enabled in
  repository settings where available, but it is not the sole acceptance mechanism because
  it is not guaranteed for all repository plans and does not provide the local-first command
  evidence this AUFG requires.
- **Rejected as primary:** `detect-secrets` is not the primary gate because its baseline-first
  workflow is weaker for blocking new high-confidence secret patterns in Git history. It may
  be reconsidered only if Platform needs a Python-native supplemental audit path.
- **ADR scope:** No new ADR is required for this AUFG-level tool selection as long as the
  implementation treats Gitleaks as CI/developer security tooling and does not add a runtime
  product dependency or change `docs/_shared/TECH_STACK.md`. If Platform adds a persistent
  project dependency, changes the Tech Stack, or makes secret scanning a new cross-cutting
  architecture pattern beyond this gate, Architecture must re-review and decide whether a
  dedicated ADR is required.
- **Blocking semantics:** CI must block new unapproved secret findings from the first
  implementation. A short baseline/grace path is allowed only for pre-existing historical
  findings and only with explicit owner, rationale, redacted evidence, and review trigger.
- **Dummy/test secrets:** Test-only values are allowed only when obviously non-production
  and explicitly scoped, for example `.env.example`, CI test environment values, or generated
  temporary fixtures. Synthetic positive tests should generate a fake secret in a temporary
  file and assert Gitleaks fails, rather than committing realistic-looking provider secrets.
  If a committed positive fixture is unavoidable, it must be confined to a dedicated
  secret-scanning fixture path and allowlisted by exact rule/value or inline marker, never by
  a broad repository-wide path ignore.

**Acceptance criteria:**

- Gitleaks is documented and implemented as the dedicated CI/local secret-scanning gate,
  including detection scope, ignore/baseline policy, and failure semantics.
- CI blocks new unapproved secrets; any historical false positives have explicit
  redacted baseline entries with owner, rationale, and expiry/review trigger.
- GitHub Secret Scanning is enabled or explicitly recorded as unavailable/not-applicable for
  the repository; it must not replace the Gitleaks CI gate.
- Local command documentation exists so specialists can run the gate before handoff.
- Dummy/test secret allowances are narrow, documented, and prove both detection and approved
  baseline/allowlist behavior without committing live or realistic production credentials.
- No real secrets are committed as part of implementation or validation evidence.

**Definition of Done:**

- CI workflow includes the secret-scanning gate.
- Platform tests or dry-run evidence prove the gate detects a synthetic secret and
  honors approved baselines/allowlists.
- Developer docs list the command and expected status semantics.
- Registry status is updated with exit evidence.

**Exit evidence (2026-06-14):** Implemented as blocking Gitleaks CI/local gate.
Evidence paths: `.gitleaks.toml` (default Gitleaks rules plus narrow exact fake-value
allowlist; no broad path ignores; no baseline file because no approved historical findings
were introduced), `scripts/check_secrets.py` (invokes `gitleaks detect --source ...
--redact --config ...` and fails with actionable install guidance when the binary is
missing), `justfile` (`just check-secrets`, included by `just security` and
`just check-full`), and `.github/workflows/ci.yml` (`security` job installs Gitleaks
v8.30.1 and runs the wrapper before Bandit/pip-audit; `fetch-depth: 0` enables full
history scanning). Validation evidence: targeted tests
`tests/unit/scripts/test_check_secrets.py` cover missing-binary install guidance (exit
127), command construction with mandatory `--source/--redact/--config` flags, default
config path resolution to the project-root `.gitleaks.toml`, and config-not-found
wrapper error (exit 2); GREEN `4 passed`; targeted Ruff, format, and TOML/YAML static
validation passed. Local runtime scan could not run in the implementation environment
because `gitleaks` was not installed; the wrapper returned exit 127 with install guidance
(`just check-secrets` confirmed). GitHub Secret Scanning / push protection remains optional
defense-in-depth and is not the acceptance mechanism for this AUFG.

---

### AUFG-05-10 — OTel-Health-Severity-Semantik

| Field | Value |
|-------|-------|
| ID | AUFG-05-10 |
| Title | OTel-Health-Severity-Semantik |
| Source | Review-05 observability finding captured durably in ADR-047 §Context (`OTel setup failures were warnings, with no explicit Health-severity policy`). |
| Status | `resolved` |
| Priority | P1 |
| Area | Observability, Platform health, Backend health/readiness endpoints |
| Owner role | Architecture Specialist (policy + contract); Platform/Backend Specialist for implementation (AUFG-05-14) |
| Dependencies | ADR-031 local-first OpenTelemetry; `apps/api/narrare/_app/observability.py`; health/readiness endpoint behavior; current system health scoring. |
| Review trigger/date | Re-review before changing health score thresholds or OTel exporter configuration, or when AE-05-02 (managed hosting) is promoted (S5/CRITICAL mechanism must be decided). |

**Architecture decision (2026-06-14):**

- **Severity policy:** OTel-not-configured (no OTLP endpoint) → **HEALTHY**
  (intentional local-first default); OTel-configured-and-operational → **HEALTHY**;
  OTel-configured-but-setup-failed → **DEGRADED** (warning-only); OTel-package-
  unavailable → **DEGRADED**. **CRITICAL is reserved** for a future mandatory-
  telemetry deployment profile (none exists today; tied to AE-05-02 managed
  hosting). DEGRADED never blocks serving and never flips `/ready` to 503.
- **Root cause:** `setup_telemetry` swallows its setup `Exception` after logging,
  and `get_observability_status()` probes only package importability — so
  "configured but broken" is a RULE-11 silent failure invisible to `/health`.
  This policy specifies the severity semantics; the visibility fix is AUFG-05-14.
- **Review-05 question answered:** OTel-Ausfall is **DEGRADED, not CRITICAL**, for
  the local-first single-user model — graceful degradation is architecturally
  correct (core functionality has zero OTel runtime dependency).
- **Vocabulary alignment:** `/health` adopts the same severity semantics as
  `scripts/check_system_health.py` (HEALTHY/DEGRADED/CRITICAL; lowercase in JSON
  payload per REST convention). This is shared *vocabulary*, not a shared
  measurement surface — OTel is not added as a CI governance gate (category
  error: OTel status is runtime, not static baseline debt).
- **Content capture:** `NARRARE_OTEL_INCLUDE_CONTENT` production default remains
  `false` (privacy invariant INV-OH-2); already implemented and tested.

**Acceptance criteria:**

- OTel setup degradation states have explicit severity mapping: warning-only,
  DEGRADED, or CRITICAL. → **Met by policy §2.1** (severity table + state mapping).
- Health/readiness behavior states whether telemetry exporter failure blocks serving
  requests, blocks release, or only emits governance debt. → **Met by policy §2.1
  / §4.3** (DEGRADED = warning-only; does not block serving or release).
- Failure semantics are visible in tracked docs and validated by tests or checker
  output. → **Policy docs: met. Tests: delegated to AUFG-05-14** (§7.5 test matrix).
- Local-first operation remains valid when external telemetry exporters are absent.
  → **Met by policy §2.1 S1 / §2.2** (not-configured = HEALTHY).

**Definition of Done:**

- Tracked observability/health documentation records the severity policy. → **Done
  (policy doc).**
- Backend health response and/or system-health checker reflects the policy without
  silent failure. → **Contract specified (policy §7); implementation in AUFG-05-14.**
- Tests cover exporter unavailable/misconfigured states where applicable. → **Test
  matrix specified (policy §7.5); implementation in AUFG-05-14.**
- Registry status is updated with exit evidence. → **Done (this entry).**

**Exit evidence (2026-06-14):** OTel Health-Severity Policy completed. Full policy
at `docs/architecture/governance/otel-health-severity-policy.md`. This AUFG's
*architecture/policy* scope (severity mapping, ADR-031 alignment, vocabulary
alignment, no-silent-failure contract, content-capture invariant) is complete and
follows the AUFG-05-07 → AUFG-05-12 precedent (policy/audit resolved; implementation
in a follow-up AUFG). The *implementation* scope — closing the RULE-11 silent-failure
gap by making "configured but broken" queryable from `/health` — is tracked in
**AUFG-05-14** (`open`, Backend/Platform). Policy invariants INV-OH-1 through INV-OH-5
govern future changes. No code changes in this slice (architecture policy +
contract specification only).

---

### AUFG-05-11 — CURRENT_STATE Volatile Stats De-duplication

| Field | Value |
|-------|-------|
| ID | AUFG-05-11 |
| Title | CURRENT_STATE Volatile Stats De-duplication |
| Source | ADR-047 `CURRENT_STATE Volatility Policy`; repeated `just check-ssot` drift from generated counts such as backend test-file totals. |
| Status | `resolved` |
| Priority | P1 |
| Area | Documentation SSOT, Governance checks, Platform tooling |
| Owner role | Docs Specialist for `CURRENT_STATE.md`; Platform Specialist for checker/test changes; Architecture Specialist for policy validation |
| Dependencies | ADR-047; `docs/_shared/CONSTRAINTS.md` §8; `docs/_shared/CURRENT_STATE.md`; `scripts/check_current_state_facts.py`; `just check-ssot`; Governance Health aggregation path. |
| Review trigger/date | Re-review whenever `CURRENT_STATE.md` reintroduces machine-derived counts, or when `check-ssot` changes from warn-only to governance-health reporting. |

**Acceptance criteria:**

- `CURRENT_STATE.md` contains human-curated status, blockers, risks, decision summaries,
  and authority links/commands, but no volatile generated inventory counts.
- Volatile generated facts are replaced by authoritative links or commands, not by freshly
  updated numbers.
- `check_current_state_facts.py` rejects forbidden volatile-count patterns and verifies
  required authority links/commands instead of requiring those counts to be present.
- Checker output remains warn-only until cleanup is complete; any future blocking behavior
  is introduced through the ADR-047 governance-health ratchet path.

**Definition of Done:**

- Docs Specialist updates `docs/_shared/CURRENT_STATE.md` according to ADR-047
  `CURRENT_STATE Volatility Policy` without changing the authoritative source hierarchy.
- Platform Specialist updates `scripts/check_current_state_facts.py` and its unit tests for
  the new policy semantics.
- `just check-ssot` no longer fails because generated counts were intentionally removed
  from `CURRENT_STATE.md`.
- Registry status is updated with exit evidence and either `resolved` or a documented
  governed-debt state.

**Exit evidence (2026-06-15):** Implementation complete. All 14 volatile count claims
removed from `docs/_shared/CURRENT_STATE.md`: Knowledge Graph node/edge counts,
backend/frontend test-file counts, architecture rule counts, ADR/feature inventory
counts, adoption-debt and health-score counts, router inventory counts. Replaced with
authoritative commands and index links: `code-review-graph list-graph-stats`, `just test`,
`just test-frontend`, `docs/_shared/CONSTRAINTS.md`, `docs/architecture/decisions/INDEX.md`,
`docs/features/INDEX.md`, `docs/architecture/questions/INDEX.md`, `just check-adoption`,
`just check-health`, `docs/architecture/governance/aufg-registry.md`.
`scripts/check_current_state_facts.py` (updated in prior session) enforces the policy
with forbidden-pattern detection and required-authority checks. `just check-ssot` now
passes cleanly: "✅ No forbidden volatile count claims found. ✅ Required authority
references/commands are present. ✅ CURRENT_STATE.md follows the volatility policy."
Human-curated content preserved: ADR-045 runtime adoption terminology note, Phase 6
summaries, Decisions/Open Questions/Risks tables.

---

### AUFG-05-12 — Rate-Limiting für AI-/SSE-/WebSocket-Endpoints

| Field | Value |
|-------|-------|
| ID | AUFG-05-12 |
| Title | Rate-Limiting für AI-/SSE-/WebSocket-Endpoints |
| Source | AUFG-05-07 security audit coverage matrix — 14 AI-cost-bearing endpoint classes without rate limits. See `docs/architecture/governance/security-audit-cors-rate-limiting.md` §4. |
| Status | `resolved` |
| Priority | P1 (SSE writing, chat, consistency, analysis, WebSocket session), P2 (generation, KB extraction/improve, setup provider models) |
| Area | Security, Backend, API middleware |
| Owner role | Backend/Security Specialist |
| Dependencies | ADR-009 (fastapi-limiter); AR-05-02 (Redis vs in-memory backend decision); existing rate-limiter DI pattern in `auth/router.py`. |
| Review trigger/date | Before public release or when AE-05-02 (managed hosting) is promoted. |

**Acceptance criteria:**

- Every AI-cost-bearing endpoint (SSE writing/extend/rewrite/coauthor/suggest,
  chat, consistency, analysis, timeline, WebSocket writing session, generation/names,
  KB extraction/improve/sessions, setup provider models) has an explicit rate limit
  via `Depends()`.
- Limits are per-user for authenticated endpoints, per-IP for unauthenticated
  (setup provider models).
- Integration tests prove the limit triggers (HTTP 429 response).
- No router-level hardcoded security; all limits flow through DI cascade.
- Rate-limit backend (Redis vs in-memory) is decided per AR-05-02 resolution.

**Definition of Done:**

- Backend implementation follows the existing `Depends()` pattern from
  `auth/router.py` without router-level hardcoded security shortcuts.
- Integration tests cover accepted (200) and rejected (429) rate-limit scenarios
  for representative endpoints per priority tier.
- Registry status is updated with exit evidence.

**Exit evidence (2026-06-15):** Implementation complete. Shared module at
`apps/api/narrare/_app/rate_limits.py` provides 3 reusable AI limiters:
`AI_WRITE_LIMITER` (3/min, Depends()), `AI_ANALYSIS_LIMITER` (5/min, Depends()),
`AI_LIGHT_LIMITER` (10/min, Depends()), and `AI_WS_LIMITER` (3/min, raw Limiter
for WebSocket inline check) plus `SETUP_MODELS_LIMITER` (10/min, IP-based).
17 router files wired via `dependencies=[Depends(CONSTANT)]`. WebSocket
rate-inline check in `router_sessions.py`. 14 unit tests at
`tests/unit/api/_app/test_rate_limits.py` covering type-check, enforcement,
independence, and WebSocket scenarios. 963+ broader backend tests pass.
Uses in-memory `pyrate_limiter` per AR-05-02 accepted risk (no Redis init).

---

### AUFG-05-13 — Origin/Referer Validation + WebSocket Origin Check (CSRF Defense-in-Depth)

| Field | Value |
|-------|-------|
| ID | AUFG-05-13 |
| Title | Origin/Referer Validation + WebSocket Origin Check (CSRF Defense-in-Depth) |
| Source | AUFG-05-08 CSRF strategy decision — defense-in-depth layer to close subdomain CSRF, SameSite=Lax 2-minute-window, and Cross-Site WebSocket Hijacking (CSWSH) gaps. See `docs/architecture/governance/csrf-strategy.md` §9. |
| Status | `resolved` |
| Priority | P1 (before public release or managed hosting promotion) |
| Area | Security, Backend middleware, WebSocket |
| Owner role | Backend/Security Specialist |
| Dependencies | CSRF strategy decision (`docs/architecture/governance/csrf-strategy.md`); trusted-origin configuration; existing middleware stack in `apps/api/narrare/_app/middleware.py`; WebSocket endpoint `apps/api/narrare/writing/router_sessions.py`; AR-05-05 (accepted risk that this AUFG partially mitigates). |
| Review trigger/date | Before public release, when AE-05-02 (managed hosting) is promoted, or when subdomain deployment is configured. |

**Scope:**

1. Origin/Referer validation middleware for all state-changing HTTP methods (POST/PUT/
   PATCH/DELETE). Trusted origins configurable via `Settings.csrf_trusted_origins`.
   Requests without Origin allowed only if valid `Authorization: Bearer` present
   (programmatic clients: CLI/MCP/A2A). Rejection: HTTP 403 with
   `{"detail": "Origin not allowed", "code": "CSRF_ORIGIN_MISMATCH"}`.
2. WebSocket Origin validation during handshake on `/writing/sessions/{chapter_id}` to
   prevent CSWSH. Reject non-trusted Origin (close code 4001).
3. `Settings.csrf_trusted_origins` field added (default: `["http://localhost:3000"]`;
   production: deployed origin via env var).

**Acceptance criteria:**

- All POST/PUT/PATCH/DELETE requests validated against trusted origins.
- Same-origin requests accepted (200); cross-origin rejected (403).
- Bearer-authenticated requests without Origin accepted (programmatic clients).
- Requests without Origin AND without Bearer rejected (403).
- WebSocket connections validate Origin during handshake.
- Integration tests cover accepted, rejected, and exempt scenarios.
- No router-level hardcoded security — middleware or dependency-based.

**Definition of Done:**

- Middleware implemented in `apps/api/narrare/_app/middleware.py`.
- WebSocket Origin check implemented in `router_sessions.py`.
- `Settings.csrf_trusted_origins` field added.
- Integration tests cover: same-origin accepted, cross-origin rejected, no-Origin-with-
  Bearer accepted, no-Origin-without-Bearer rejected, WebSocket origin validated.
- Registry status is updated with exit evidence.

**Exit evidence (2026-06-15):** Implementation complete. `OriginValidationMiddleware`
in `apps/api/narrare/_app/middleware.py` validates Origin/Referer on all
POST/PUT/PATCH/DELETE requests; Bearer-authenticated requests without Origin
are exempt (programmatic clients). Middleware registered in `main.py` after CORS.
`Settings.csrf_trusted_origins` field (`NARRARE_CSRF_TRUSTED_ORIGINS`, default
`["http://localhost:3000"]`) configures trusted origins. WebSocket Origin check
in `writing/router_sessions.py` rejects non-matching origins with close code
4001. 12 unit tests at `tests/unit/api/_app/test_csrf_middleware.py` covering
same-origin (200), cross-origin (403), Bearer-exempt (200), WebSocket (4001),
Referer fallback, and invalid Bearer scenarios. Backend middleware gated in test
environment to avoid breaking existing TestClient-based tests.

---

### AUFG-05-14 — OTel-Health-Severity Implementierung (Backend/Platform)

| Field | Value |
|-------|-------|
| ID | AUFG-05-14 |
| Title | OTel-Health-Severity Implementierung (Backend/Platform) |
| Source | AUFG-05-10 OTel Health-Severity Policy §7 (Implementation Contract). AUFG-05-10's architecture/policy scope is resolved; this AUFG carries the implementation scope that closes the RULE-11 silent-failure gap. |
| Status | `resolved` |
| Priority | P1 |
| Area | Observability, Backend health/readiness endpoints, Platform testing |
| Owner role | Backend Specialist (observability/telemetry + health endpoint) with Platform Specialist (tests/smoke-checks) |
| Dependencies | ADR-031; OTel Health-Severity Policy (`docs/architecture/governance/otel-health-severity-policy.md` §7); `apps/api/narrare/_app/observability.py`; `apps/api/narrare/_app/telemetry.py`; `apps/api/narrare/metrics/router.py`; `scripts/check_system_health.py` (vocabulary reference, not modified). |
| Review trigger/date | Re-review if the OTel Health-Severity Policy (§7 contract or §10 invariants) changes, or when AE-05-02 promotes S5/CRITICAL. |

**Scope (normative: policy §7):**

1. **`get_observability_status()` extension** (`observability.py`): add `state`
   (`not_configured` | `configured_ok` | `configured_failed` | `package_unavailable`),
   `severity` (`healthy` | `degraded` | `critical`), and `endpoint_configured` to the
   return shape. Retain `available` (backward-compat) = `severity == "healthy"`.
   State → severity mapping per policy §2.1.
2. **New `record_otel_setup_outcome()`** (`observability.py`): thread-safe function
   called by `setup_telemetry` to record setup success/failure so it is queryable.
   Signature per policy §7.2.
3. **`setup_telemetry` wiring** (`telemetry.py`): call `record_otel_setup_outcome()`
   on the no-endpoint early-return (succeeded, not configured), on success
   (configured_ok), and in the `except Exception` branch (configured_failed) —
   replacing the current silent swallow while preserving the no-raise contract.
4. **`/health` endpoint** (`metrics/router.py`): return `status = observability
   severity` (`healthy`/`degraded`/`critical`) instead of always `"ok"`. HTTP 200
   for healthy and degraded (liveness). `/ready` unchanged.
5. **Tests** (policy §7.5): cover no-endpoint (T1), configured-but-failed (T2),
   successful configuration (T3), and reaffirm production-safe content-capture
   default (T4). Update existing tests in `tests/unit/api/_app/test_observability.py`
   and `test_telemetry*.py` for the new return shape (backward-compat `available`
   retained).

**Acceptance criteria:**

- `get_observability_status()` exposes `state` and `severity` per policy §7.1.
- `setup_telemetry` records outcome via `record_otel_setup_outcome()` on all three
  paths (no-endpoint, success, failure); the failure path no longer swallows state
  silently (RULE-11).
- `/health` `status` reflects the policy severity vocabulary; DEGRADED returns HTTP
  200 and does not affect `/ready`.
- Tests cover T1–T4 (policy §7.5); no OTel failure elevates severity above DEGRADED
  without a mandatory-telemetry profile (invariant INV-OH-1).
- `available` backward-compat key retained so existing consumers do not break.
- No new external dependency; no `apps/` → `core/` import (RULE-07).

**Definition of Done:**

- Implementation follows the policy §7 contract without router-level business logic
  (RULE-06).
- Unit tests for observability state transitions + telemetry outcome recording +
  `/health` payload pass GREEN.
- This registry entry is updated with exit evidence and status `resolved`.

**Exit evidence (2026-06-15):** Implementation complete. `get_observability_status()`
in `apps/api/narrare/_app/observability.py` extended with `state`
(not_configured|configured_ok|configured_failed|package_unavailable), `severity`
(healthy|degraded|critical), and `endpoint_configured` keys; `available` retained
for backward compatibility (= `severity == "healthy"`). New
`record_otel_setup_outcome()` function records setup outcomes thread-safely.
`setup_telemetry()` in `telemetry.py` calls it on all 3 paths: no-endpoint
(not_configured), success (configured_ok), failure (configured_failed). `/health`
in `metrics/router.py` returns `status: obs["severity"]` instead of hardcoded
`"ok"`; DEGRADED returns HTTP 200 (liveness). 13 unit tests at
`tests/unit/api/_app/test_observability_health.py` covering T1–T5 (no-endpoint,
configured-failed, configured-ok, content-capture default, package-unavailable).
RULE-11 silent-failure gap closed: configured-but-broken is now both logged AND
queryable from `/health`.

---

## Cross-Review AUFG Migration (Reviews 01–04 → Durable Registry)

These entries migrate AUFGs first defined in earlier technical reviews (01–04) into
the durable lifecycle registry so that consolidated Review-05 findings reference
machine-checkable lifecycle states rather than prose-only review text. Each status is
based on current platform evidence verified 2026-06-20 (not the original review date):
the gates and artefacts named in the exit evidence were re-run or re-inspected. Full
acceptance criteria remain in the source review files referenced under `Source`.

### AUFG-01-04 — useExtractionPhase RULE-04 und AI-UX-Regression beheben

| Field | Value |
|-------|-------|
| ID | AUFG-01-04 |
| Source | review-01-architektur.md §Aufgaben; consolidated in review-05-release.md §5. |
| Status | `resolved` |
| Priority | P1 |
| Area | Frontend architecture, RULE-04, AI UX |
| Review trigger/date | Re-review if check-frontend-size or check-ai-ux regresses for extraction hooks. |

**Exit evidence (2026-06-20):** `useExtractionPhase.ts` is within the hook hard limit
(modularized, not compressed). `just check-frontend-size` reports
`0 current, 0 baseline, 0 new, 0 resolved`; `just check-ai-ux` reports `Violations: 0`
with 3 governed exclusions tracked as baseline debt. The callback-based SSE transport
remains a justified governed exception under CR-AUFG-07-09.

---

### AUFG-01-05 — AI-UX-Test-Harness für NameGenerator bereinigen

| Field | Value |
|-------|-------|
| ID | AUFG-01-05 |
| Source | review-01-architektur.md §Aufgaben; consolidated in review-05-release.md §5. |
| Status | `resolved` |
| Priority | P2 |
| Area | Testing, Frontend quality, AI UX checker |
| Review trigger/date | Re-review if check-ai-ux flags a raw AbortController in NameGenerator tests. |

**Exit evidence (2026-06-20):** `NameGenerator.test.tsx` no longer triggers a raw
`AbortController()` violation. `just check-ai-ux` reports `Violations: 0`; no
production-code workaround was introduced (test-/checker-conformant harness only).

---

### AUFG-02-08 — Aktuelle CI-Blocker aus Review 01 vor Merge bereinigen

| Field | Value |
|-------|-------|
| ID | AUFG-02-08 |
| Source | review-02-testing.md §Aufgaben (tracking task for AUFG-01-04/01-05); consolidated in review-05-release.md §5. |
| Status | `resolved` |
| Priority | P1 |
| Area | CI, Frontend quality gates |
| Review trigger/date | Re-review if the architecture/frontend CI path is blocked by AI-UX or RULE-04 violations. |

**Exit evidence (2026-06-20):** Tracking task for AUFG-01-04 and AUFG-01-05. Both
underlying gates are green: `just check-ai-ux` → `Violations: 0`;
`just check-frontend-size` → `0 current, 0 baseline`. No compression-based limit
evasion; `useExtractionPhase.ts` was modularized.

---

### AUFG-02-02 — Coverage-Gate vom Übergangszustand auf RULE-10-Endzustand heben

| Field | Value |
|-------|-------|
| ID | AUFG-02-02 |
| Source | review-02-testing.md §Aufgaben; consolidated in review-05-release.md §5. |
| Status | `resolved` |
| Priority | P1 |
| Area | Testing, CI, RULE-10 coverage governance |
| Review trigger/date | Re-review if the global cov-fail-under drops below 80% or per-module ratcheted baselines are removed. |

**Exit evidence (2026-06-20):** The transition exception is closed. CI
(`.github/workflows/ci.yml`) runs `--cov-fail-under=80` as a blocking global gate
(documented at global 82.51%); `scripts/check_module_coverage.py --fail` enforces
per-module RULE-10 thresholds via ratcheted baselines in the `test-unit` job; and
`scripts/check_test_coverage_gaps.py --fail-on-missing` runs in the `architecture`
job. No `coverage-threshold` architecture exception remains. CI, README badge and
testing standards describe the same 80% global status.

---

### AUFG-01-07 — Adoption-/Health-Ratchet mit CURRENT_STATE.md synchronisieren

| Field | Value |
|-------|-------|
| ID | AUFG-01-07 |
| Source | review-01-architektur.md §Aufgaben; consolidated in review-05-release.md §5. |
| Status | `resolved` |
| Priority | P2 |
| Area | DX, Governance, SSOT consistency |
| Review trigger/date | Re-review if CURRENT_STATE.md reintroduces a hard-coded adoption-debt count that drifts from check-adoption. |

**Exit evidence (2026-06-20):** Say-Do drift is closed. `CURRENT_STATE.md` defers
to `just check-adoption` as the authoritative source. AUFG-05-11 removed all
volatile generated counts from CURRENT_STATE.md.

Implementation:
- `docs/_shared/CURRENT_STATE.md` — defers to authoritative commands, no hardcoded debt counts
- `scripts/check_adoption.py` — authoritative adoption scoring (static/runtime/adopted semantics)
- `scripts/check_current_state_facts.py` — SSOT volatility-policy checker

Enforcement:
- `scripts/check_adoption.py` in pre-commit (always_run) + CI (blocking) — prevents adoption score regression
- `scripts/check_current_state_facts.py` in CI (CI gate) — detects reintroduction of volatile counts in CURRENT_STATE.md

---

### AUFG-03-05 — AI-Adoption-Runtime-Evidence-Semantik klären

| Field | Value |
|-------|-------|
| ID | AUFG-03-05 |
| Source | review-03-ai-features.md §Aufgaben; consolidated in review-05-release.md §5. |
| Status | `resolved` |
| Priority | P1 |
| Area | AI, Governance, adoption semantics |
| Review trigger/date | Re-review if adoption reporting reintroduces a conflation of static-verified and runtime-adopted. |

**Exit evidence (2026-06-20):** Runtime-evidence semantics clarified and aligned.
`just check-adoption` reports `static_verified`, `runtime_verified`, `adopted` as
distinct columns; all required modes show `runtime ✅ | adopted ✅` (score 0.97 PASS).
`CURRENT_STATE.md` records the ADR-045 terminology. A static-only change no longer
raises `adopted`.

Implementation:
- `scripts/check_adoption.py` — runtime semantics columns (`static_verified`, `runtime_verified`, `adopted`)
- `scripts/check_system_health.py` — aggregates runtime adoption into health score

Enforcement:
- `scripts/check_adoption.py` in pre-commit (always_run) + CI (blocking) — enforces distinct status columns
- `tests/unit/scripts/test_check_adoption_runtime_semantics.py` — pytest unit tests validating runtime semantics

---

### AUFG-01-03 — MCP/A2A-Produktstatus und Adapter-Gates klären

| Field | Value |
|-------|-------|
| ID | AUFG-01-03 |
| Source | review-01-architektur.md §Aufgaben; consolidated in review-05-release.md §5. |
| Status | `accepted_enhancement` |
| Priority | P3 |
| Area | Architecture, adapter strategy |
| Review trigger/date | Re-review when Q-001 (MCP auth) or Q-002 (A2A streaming) is decided, or when a multi-adapter product requirement is approved. |

**Disposition (2026-06-20):** MCP/A2A is deliberately not implemented and is a
deferred strategic capability, not a quality gap. The documentation/clarification
acceptance criteria are met: the directory structure, feature index
(ADAPTER-001/002 note) and open questions Q-001/Q-002 consistently describe MCP/A2A
as planned-not-implemented, with contract-test gates defined for the first adapter
(see also AUFG-03-04). No adapter skeleton is created merely to satisfy review.
Capability implementation remains gated on a Q-001/Q-002 decision and a dedicated
adapter spec.

---

### AUFG-03-04 — MCP/A2A als geplante Adapter konkretisieren oder aus Review-Scope entfernen

| Field | Value |
|-------|-------|
| ID | AUFG-03-04 |
| Source | review-03-ai-features.md §Aufgaben; consolidated in review-05-release.md §5. |
| Status | `accepted_enhancement` |
| Priority | P3 |
| Area | AI, Architecture, adapter strategy |
| Review trigger/date | Re-review when Q-001/Q-002 is decided, or when an adapter-specific spec is written. |

**Disposition (2026-06-20):** Verified (per review-03) that the INDEX.md
ADAPTER-001/002 note and Q-001/Q-002 are current and act as SSOT, with contract-test
gates (service-layer call, auth/identity mapping, streaming/non-streaming parity,
error mapping, no business logic in adapter) already defined for the first adapter.
Q-001 and Q-002 remain marked as blockers until an adapter-specific spec is written.
No `apps/mcp/` or `apps/a2a/` skeleton exists solely to satisfy review. Capability
remains a deferred strategic enhancement (paired with AUFG-01-03).

---

### AUFG-05-04 — pnpm-Version im Dockerfile aktualisieren

| Field | Value |
|-------|-------|
| ID | AUFG-05-04 |
| Source | review-05-release.md §Aufgaben; consolidated in review-05-release.md §5. |
| Status | `resolved` |
| Priority | P2 |
| Area | Release, DX, build consistency |
| Review trigger/date | Re-review if the Dockerfile pnpm version drifts from the root packageManager pin again. |

**Exit evidence (2026-06-20):** `Dockerfile:53` uses `ARG PNPM_VERSION=11.5.2`,
matching the root `package.json` `packageManager: pnpm@11.5.2` pin. The release-build
`pnpm install --frozen-lockfile` stage, Dockerfile, DevContainer Dockerfile and root
package.json now share one pnpm version. (DevContainer parity tracked under AUFG-04-03.)

Implementation:
- `Dockerfile` — ARG PNPM_VERSION=11.5.2
- `package.json` — packageManager: pnpm@11.5.2

Enforcement:
- `scripts/check_doc_drift.py` — CI-blocking gate (via `scripts/doc_drift/tool_version_checks.py` pnpm checks) validates Dockerfile PNPM_VERSION matches package.json SSOT

---

### AUFG-02-06 — Pydantic-Evals in CI/Nightly-Governance einbinden

| Field | Value |
|-------|-------|
| ID | AUFG-02-06 |
| Source | review-02-testing.md §Aufgaben; consolidated in review-05-release.md §5. |
| Status | `resolved` |
| Priority | P2 |
| Area | AI, CI, evaluation governance |
| Review trigger/date | Re-review if eval smoke coverage is removed from CI or if check_eval_drift semantics change. |

**Exit evidence (2026-06-20):** Secret-free smoke evals are wired into CI as a
blocking step: `.github/workflows/ci.yml` runs
`uv run python -m evals run --suite all --mode smoke` in the `architecture` job, and
`scripts/check_eval_drift.py` runs warning-only with no-growth semantics. Runtime
evals with provider secrets remain separated from normal pytest jobs. The residual
"dedicated nightly runtime workflow" is tracked as ongoing eval-expansion work
(AUFG-03-07) rather than a blocker for CI integration. Testing standards document
the smoke/runtime/optional-LLM-judge distinction.

---

### AUFG-03-07 — Pydantic-Evals fachlich verbreitern

| Field | Value |
|-------|-------|
| ID | AUFG-03-07 |
| Source | review-03-ai-features.md §Aufgaben; consolidated in review-05-release.md §5. |
| Status | `resolved` |
| Priority | P2 |
| Area | AI, Testing, evaluation coverage |
| Owner role | Core/AI Specialist with Platform CI support |
| Review trigger/date | Re-review when a new eval dataset/suite is added or when the eval-expansion roadmap is revised. |

**Exit evidence (2026-06-21):** Eval coverage now spans all 19 AI agents across
9 datasets under `evals/datasets/` — the original 6 suites (KB Extraction, Rewrite
Selection, Preference Analysis, Analysis Feedback, Chat Generation, Consistency
Staged) plus 3 new suites added in this cycle: `analysis_metrics` (Readability,
POV Detection, Chapter Summary), `planning_structure` (Outline, Character Arc,
Timeline, Worldbuilding), and `kb_operations` (KB Agent, KB Assist, KB Improve, KB
Merge). Matching evaluators live under `evals/evaluators/` and drift baselines
exist for all 9 suites under `evals/baselines/`. All 9 suites are smoke-green in
CI (`uv run python -m evals run --suite all --mode smoke` runs in the
`architecture` job). A dedicated nightly runtime workflow
(`.github/workflows/eval-nightly.yml`) exercises the 6 Tier-1 runtime suites
against a real provider via the `NARRARE_EVAL_API_KEY` secret. The 3 new
Tier-2/3 suites (`analysis_metrics`, `planning_structure`, `kb_operations`) are
smoke-only: they ship dataset + evaluator + structural validators but no runtime
task yet, so the runner skips them gracefully in `--mode runtime` rather than
failing. Real runtime validation for these 3 suites requires adding runtime tasks
plus the `NARRARE_EVAL_API_KEY` secret in CI. Test coverage: 67 eval unit tests
under `tests/unit/evals/` covering dataset shape, evaluator logic, runner
behaviour, and drift detection.

---

## Coverage Pointers

### AUFG-05-03 — Memory/Embedding-Spans and Metrics-Exporter Decision/Extension

| Field | Value |
|-------|-------|
| ID | AUFG-05-03 |
| Title | Memory/Embedding-Spans and Metrics-Exporter Decision/Extension |
| Source | Review-05 observability scope referenced by ADR-047-related handoff; durable coverage pointer created here to avoid duplicate AUFGs. |
| Status | `covered_by_existing_aufg` |
| Priority | P1 |
| Area | Observability, Memory, Embeddings, metrics export |
| Owner role | Platform Specialist with Core Specialist for memory/embedding instrumentation |
| Dependencies | ADR-031 OpenTelemetry standard; ADR-033 mem0 memory architecture; existing memory/embedding clients and metrics/exporter decisions. |
| Review trigger/date | Re-review whenever AUFG-05-03 is closed, or if AUFG-05-10 changes health semantics for telemetry/exporter failures. |

**Acceptance criteria:**

- AUFG-05-03 exit evidence explicitly states whether memory/embedding spans are
  implemented, rejected as not applicable, or tracked as accepted risk/enhancement.
- Metrics-exporter behavior is decided in AUFG-05-03 or a linked ADR/spec; no separate
  prose-only observability finding remains.
- If AUFG-05-03 scope is insufficient, this pointer must be converted into a separate
  AUFG before release governance claims are made.

**Definition of Done:**

- AUFG-05-03 tracked evidence includes memory/embedding span and metrics-exporter
  decision coverage.
- This pointer remains `covered_by_existing_aufg` only while that evidence exists.

**Exit evidence:** Pending AUFG-05-03 closure evidence.

---

## Accepted Enhancements

Accepted enhancements are non-blocking by default. They become blocking only if a
later ADR/spec/release gate promotes them to `open` AUFG scope.

### AE-05-01 — Cosign/SLSA Release Provenance Hardening

| Field | Value |
|-------|-------|
| ID | AE-05-01 |
| Title | Cosign/SLSA Release Provenance Hardening |
| Source | `docs/development/deployment-guide.md` §Cosign Signing (Future) and provenance trust model. |
| Status | `accepted_enhancement` |
| Priority | P2 |
| Area | Platform, release engineering, supply-chain security |
| Owner role | Platform Specialist |
| Dependencies | Release workflow, GHCR publishing, SBOM generation, GitHub OIDC permissions, secret-scanning gate AUFG-05-09. |
| Review trigger/date | Review before first public release artifact, or by 2026-09-30 if release hardening has not been revisited. |

**Acceptance criteria:**

- Platform decides whether to implement Cosign keyless signing, SLSA provenance, or
  both, with rationale and verification commands.
- Release documentation explains how users verify image signatures/provenance.
- CI/release workflow evidence demonstrates signed/provenance-bearing artifacts if promoted.

**Definition of Done:**

- If promoted: workflow, docs, and verification evidence are added in one coherent change.
- If deferred: registry remains `accepted_enhancement` with renewed review date and rationale.

**Exit evidence:** Non-blocking enhancement accepted; implementation evidence pending only
if promoted by Platform/release planning.

---

### AE-05-02 — Managed Hosting Strategy Exploration

| Field | Value |
|-------|-------|
| ID | AE-05-02 |
| Title | Managed Hosting Strategy Exploration |
| Source | `docs/architecture/questions/Q-011-distribution-strategy.md` Option C / Variant C2 and recommendation. |
| Status | `accepted_enhancement` |
| Priority | P3 |
| Area | Product architecture, distribution strategy, platform operations |
| Owner role | Architecture Specialist with Product/Coordinator decision from user |
| Dependencies | Q-011 distribution strategy; local-first product vision; auth/multi-tenancy, billing, GDPR, rate limiting, and operational support decisions. |
| Review trigger/date | Review at Post-MVP Phase 4 or when active non-developer onboarding begins, whichever comes first. |

**Acceptance criteria:**

- Managed hosting remains an exploration/enhancement, not an implementation decision.
- Any move toward hosted/SaaS delivery requires a new ADR covering local-first impact,
  multi-tenancy, data isolation, billing, rate limiting, and GDPR/compliance.
- Q-011 remains the strategy question until the user explicitly selects a distribution path.

**Definition of Done:**

- No production code is added for managed hosting under this enhancement entry alone.
- If promoted, Architecture creates a dedicated ADR/spec before implementation.
- If rejected, status changes to `not_applicable` or `accepted_risk` with rationale.

**Exit evidence:** Non-blocking strategic enhancement accepted for future review; no
implementation evidence required until user-approved promotion.

---

### AE-05-03 — CORS Origins als Settings-Feld

| Field | Value |
|-------|-------|
| ID | AE-05-03 |
| Title | CORS Origins als Settings-Feld |
| Source | AUFG-05-07 security audit §2.4 — CORS origins hardcoded in app factory. |
| Status | `accepted_enhancement` |
| Priority | P3 |
| Area | Backend, configuration, deployment |
| Owner role | Backend Specialist |
| Dependencies | `apps/api/narrare/_app/settings_model.py`; `apps/api/narrare/_app/main.py` CORS middleware. |
| Review trigger/date | Re-review when a deployment scenario requires custom CORS origins, or by 2027-06-14. |

**Acceptance criteria:**

- `Settings.cors_origins` field added so operators configure CORS via env var.
- Default remains `["http://localhost:3000"]` for dev, `[]` for production.
- No behavior change for existing deployments.

**Definition of Done:**

- If promoted: Settings field + tests in one coherent change.
- If deferred: registry remains `accepted_enhancement` with renewed review date.

**Exit evidence:** Non-blocking enhancement accepted; implementation evidence pending
only if promoted.

---

## Accepted Risks

Accepted risks are knowingly accepted with owner, rationale, controls, and review
date. They become blocking only if a later ADR/spec/release gate promotes them to
`open` AUFG scope.

### AR-05-02 — Rate-Limiting Backend Discrepanz (In-Memory vs Redis)

| Field | Value |
|-------|-------|
| ID | AR-05-02 |
| Type | `accepted_risk` |
| Risk | Rate limits are process-local in-memory (`pyrate_limiter`), not Redis-based as specified in TECH_STACK.md / ADR-009. Multi-instance deployments would have independent counters per instance. |
| Owner | Backend/Security Specialist |
| Rationale | Current deployment model is single-instance local-first. In-memory rate limiting is functionally equivalent for single-instance. `pyrate-limiter` is a transitive dependency of `fastapi-limiter`; the combination works in practice (e2e tests confirm HTTP 429 responses on auth endpoints). |
| Controls | (1) TECH_STACK.md documents the intended Redis-based approach. (2) AUFG-05-12 implementation should evaluate whether to align with TECH_STACK.md (call `FastAPILimiter.init(redis)`) or update TECH_STACK.md/ADR-009 to reflect the in-memory approach. |
| Review trigger/date | Re-review when AE-05-02 (managed hosting) is promoted to implementation, or when multi-instance API deployment is configured. No fixed date — gated by deployment topology change. |
| Source | AUFG-05-07 security audit §3.3 |

### AR-05-03 — Auth-Non-Brute-Force Endpoints ohne Rate Limit

| Field | Value |
|-------|-------|
| ID | AR-05-03 |
| Type | `accepted_risk` |
| Risk | `/auth/refresh`, `/auth/logout`, `GET /auth/me` have no rate limits. |
| Owner | Backend/Security Specialist |
| Rationale | Refresh: cookie-scoped (`samesite=lax`, `path=/api/v1/auth`), token rotation on every call, invalid tokens clear the cookie. Logout: no-op (clears cookie). Me: read-only, auth-protected. None present a meaningful brute-force or cost-abuse surface. |
| Controls | `sameSite=lax` prevents CSRF-based abuse. Token rotation invalidates stolen refresh tokens on use. Auth-protected endpoints require valid JWT. |
| Review trigger/date | Re-review if refresh token flow changes, or if `sameSite` is weakened. By 2027-06-14 if no change. |
| Source | AUFG-05-07 security audit §4.2 |

### AR-05-04 — State-Changing CRUD ohne Rate Limit (Local-First)

| Field | Value |
|-------|-------|
| ID | AR-05-04 |
| Type | `accepted_risk` |
| Risk | State-changing CRUD endpoints (novels, chapters, volumes, KB, settings, embeddings, prompts, templates, wiki), setup validation/complete have no rate limits. |
| Owner | Backend/Security Specialist |
| Rationale | All endpoints are auth-protected (require valid JWT). Deployment model is local-first, single-user self-hosted. No multi-tenant or public-facing surface. Rate-limiting CRUD on a single-user local instance adds complexity without security benefit. |
| Controls | JWT authentication on all endpoints. `ENVIRONMENT` defaults to `development`. Production requires explicit operator configuration. Setup complete requires authentication. |
| Review trigger/date | Re-review when AE-05-02 (managed hosting) is promoted, or when multi-user/multi-tenant features are added. No fixed date — gated by product evolution. |
| Source | AUFG-05-07 security audit §4.2 |

### AR-05-05 — No Double-Submit-CSRF-Token

| Field | Value |
|-------|-------|
| ID | AR-05-05 |
| Type | `accepted_risk` |
| Risk | No Double-Submit-CSRF-Token is used. CSRF defense relies on (1) Bearer-token authentication for all state-changing endpoints, (2) SameSite=Lax for cookie-authenticated auth endpoints, and (3) Origin/Referer validation (to be implemented per AUFG-05-13). |
| Owner | Architecture Specialist |
| Rationale | The backend authenticates state-changing endpoints via `Authorization: Bearer` headers (`HTTPBearer` in `get_current_user_id`), not cookies. CSRF is structurally inapplicable because the browser cannot auto-attach `Authorization` headers cross-origin. The only cookie-authenticated endpoints (`/auth/refresh`, `/auth/logout`) are protected by SameSite=Lax + path-restriction (`/api/v1/auth`) and have no data-integrity impact (token rotation, logout). A Double-Submit-Token would protect against a vector that does not exist in the current architecture, adding complexity (token generation, storage, client-server coordination, contract, test surface) without proportional security benefit. |
| Controls | (1) Bearer-token auth via `HTTPBearer` (`apps/api/narrare/_app/dependencies_auth.py`). (2) SameSite=Lax + path-restriction on `narrare_refresh` cookie (`apps/api/narrare/auth/cookie_helpers.py`). (3) JSON-only API (Pydantic rejects non-JSON bodies). (4) CORS disabled in production (same-origin proxy). (5) Origin/Referer validation per AUFG-05-13 (pending implementation). (6) Architectural invariant INV-1 through INV-5 (see `docs/architecture/governance/csrf-strategy.md` §12): backend must never add cookie-based auth for state-changing endpoints. |
| Review trigger/date | Re-review if: (a) cookie-based authentication is added to any state-changing endpoint, (b) AE-05-02 (managed hosting) is promoted introducing subdomains, (c) WebSocket auth model changes, or (d) by 2027-06-14 if no change. |
| Release trigger | Origin/Referer validation (AUFG-05-13) should be implemented before public release or managed hosting promotion. Until then, the current posture (Bearer auth + SameSite=Lax) is safe for local-first single-user deployment. |
| Source | AUFG-05-08 CSRF strategy decision (`docs/architecture/governance/csrf-strategy.md` §8) |
