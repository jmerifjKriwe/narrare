# AI UX Compliance v2 — Governance Specification

> **Status:** Active governance specification
> **Date:** 2026-06-18
> **Owner:** Architecture Specialist
> **Related:** ADR-043, ADR-047, CR-07 UX Audit, `docs/development/ui-principles.md` §16, `docs/architecture/governance/aufg-registry.md`

---

## 1. Scope

This specification defines the governance contract for closing CR-AUFG-07-07
through CR-AUFG-07-13 and preventing future drift in AI interaction UX.

**In scope:**

- Durable lifecycle tracking for CR-AUFG-07-07 through CR-AUFG-07-13.
- A required AI Operation Inventory for all frontend AI operations.
- Mapping `ui-principles.md` §16 requirements to enforceable checks.
- Stale-exclude handling for `scripts/checks/.ai_interaction_exclude`.
- Sequencing for Architecture → Frontend → Platform → Docs handoff.

**Out of scope:**

- Frontend production implementation. That belongs to the Frontend Specialist.
- Checker/test implementation. That belongs to the Platform Specialist.
- A new runtime primitive. ADR-043 remains the primitive decision.
- New dependencies or changes to the product tech stack.

---

## 2. Root Cause Analysis

**Symptom:** CR-07 was reported as fully implemented in `CURRENT_STATE.md`, while
the refreshed CR-07 audit identified CR-AUFG-07-07 through CR-AUFG-07-13 as open
AI-UX gaps.

**Warum 1?** The original ADR-043 closure treated `useAIOperation` adoption and a
small set of static checks as sufficient evidence for §16 compliance.

**Warum 2?** There is no durable AI Operation Inventory tying every user-facing AI
operation to its transport, cancel semantics, signal propagation, error mapping,
i18n labels, keyboard behavior, exclusions, and AUFG lifecycle state. As a result,
audit-only prose can discover gaps that are not represented in the lifecycle SSOT,
and checker green can cover only the inspected slice.

**Root cause:** The governance model lacked a feature-by-feature compliance
inventory and lifecycle sync rule. ADR-043 correctly specified the shared primitive,
but governance over-inferred full-system compliance from primitive existence and
partial static checks.

**No-workaround conclusion:** Do not patch the seven frontend gaps ad hoc and call
CR-07 resolved. The correct sequence is: register every CR-AUFG in the durable AUFG
registry, define the inventory/enforcement contract, implement frontend fixes
against that contract, then add Platform gates that prove the same gaps cannot
silently return.

---

## 3. Artifact Decision

### Option A — New ADR

Create a new ADR for AI-UX compliance v2.

**Pros:** High visibility; strong status lifecycle.

**Cons:** No new architectural primitive, dependency, module boundary, or RULE-XX
exception is being introduced. ADR-043 already owns the primitive decision, and
ADR-047 already owns durable governance for review findings. A new ADR would
duplicate existing decisions rather than decide a new architecture.

### Option B — Revise ADR-043

Append the full v2 governance contract to ADR-043.

**Pros:** Keeps all AI interaction primitive material in one document.

**Cons:** ADR-043 is about the runtime primitive (`useAIOperation`) and its
interface. CR-AUFG-07-07 through CR-AUFG-07-13 are a governance/enforcement gap:
inventory, stale excludes, checker expansion, and lifecycle sync. Expanding ADR-043
would mix implementation contract and governance operating model.

### Option C — AUFG-only policy

Add CR-AUFG-07-07 through CR-AUFG-07-13 to the registry without a separate spec.

**Pros:** Minimal documentation surface; lifecycle entries become durable.

**Cons:** Seven entries would share the same root cause, checker plan, and
sequencing rules. Repeating that in every AUFG would be noisy; omitting it would
leave Frontend and Platform without a single implementation contract.

### Option D — Governance spec + AUFG registry entries (chosen)

Create this governance spec and add durable AUFG entries for CR-AUFG-07-07 through
CR-AUFG-07-13.

**Pros:** Keeps ADR-043 stable as the primitive decision, uses ADR-047's registry
as lifecycle SSOT, and provides one reusable contract for Frontend, Platform, and
Docs.

**Cons:** Adds one governance document that must remain aligned with the AUFG
registry and `CURRENT_STATE.md`.

**Decision:** Choose Option D. No ADR index update is required because no ADR is
created or status-changed. This spec operationalizes accepted decisions from
ADR-043 and ADR-047.

---

## 4. AI Operation Inventory

The AI Operation Inventory is the mandatory compliance surface for frontend AI
operations. It may begin as a governance document or checked data file, but Platform
must make it machine-readable before CR-AUFG-07-07 through CR-AUFG-07-13 can be
marked `resolved`.

### Required fields per operation

| Field | Requirement |
|-------|-------------|
| `operation_id` | Stable identifier, e.g. `kb.field_suggest` or `timeline.extraction`. |
| `feature` | Feature or product area. |
| `entry_points` | Components/hooks/extensions that expose the operation. |
| `transport` | `sse`, `rest`, `websocket`, or `non_react_extension`; include endpoint/API wrapper. |
| `lifecycle_owner` | `useAIOperation`, `useAISession`, `tanstack_query_adapter`, `non_react_adapter`, or `governed_exception`. |
| `loading_feedback` | Evidence of immediate visual feedback (<200ms) or justified N/A. |
| `cancel_ui` | Visible cancel control, keyboard cancel, or justified N/A. |
| `signal_propagation` | Evidence that cancel reaches `AbortSignal`/transport, not only UI state. |
| `error_mapping` | `mapSSEError`, `mapRestApiError`, or equivalent structured `AIErrorResponse`. |
| `partial_output` | Preservation behavior for streaming/long-running operations. |
| `ai_action_i18n` | Canonical `studio.aiActions.*` keys used for AI action labels. |
| `deprecated_key_usage` | Exact deprecated §16.8 aliases absent, or migration AUFG listed. |
| `keyboard` | Required shortcuts, if this operation presents AI output actions. |
| `tests` | Unit/component/e2e tests proving applicable §16 behavior. |
| `aufg_id` | Linked CR-AUFG when non-compliant or recently remediated. |
| `exclude_entry` | Linked exclude entry if present; must include exit and re-evaluation date. |
| `status` | `compliant`, `open`, `in_progress`, `governed_exception`, or `not_applicable`. |

### Initial inventory minimum for CR-AUFG-07-07 through CR-AUFG-07-13

| Operation | Required linked AUFG |
|-----------|----------------------|
| KB Field Suggest | CR-AUFG-07-07 |
| KB Improve | CR-AUFG-07-08 |
| Timeline Extraction | CR-AUFG-07-09 |
| GhostText Suggestion Fetch | CR-AUFG-07-10 |
| KB Enhance | CR-AUFG-07-11 |
| AI action i18n aliases | CR-AUFG-07-12 |
| AI output action keyboard shortcuts | CR-AUFG-07-13 |

---

## 5. §16 Requirement → Enforcement Matrix

| §16 requirement | Required evidence | Existing checker coverage | Required Platform expansion |
|-----------------|-------------------|----------------------------|-----------------------------|
| §16.1 Streaming | SSE used where backend provides SSE; no REST-only frontend for SSE-capable backend. | Partial via AI-UX checker and streaming compliance. | Inventory must record transport and endpoint; checker flags REST-only use against known SSE-capable operations unless `not_applicable` is justified. |
| §16.2 Cancel | Visible cancel for operations >2s and transport receives cancellation signal. | Raw AbortController scan only. | Add cancel UI evidence check and signal-propagation check. UI-only `cancel()` without passing `AbortSignal` is non-compliant. |
| §16.3 Loading | Immediate feedback within 200ms; state distinguishes loading/streaming/complete where applicable. | Partial through hook usage. | Inventory field plus component tests for each remediated AUFG. |
| §16.4 Action labels | AI output actions use canonical `studio.aiActions.*`. | i18n parity exists; deprecated aliases not fully gated. | Exact deprecated alias usage gate for TS/TSX. Broader namespaces are allowed unless the exact §16.8 deprecated AI-action alias is used. |
| §16.5 Errors | Actionable structured errors; no raw `error.message` in AI UI. | Existing hardcoded error scan. | Extend to inventory: each operation lists mapper and tests. |
| §16.6 Feedback | Visible AI output requires accept/reject or equivalent user confirmation. | Manual review. | Inventory field and targeted component tests for operations touched by CR-AUFG-07-13. |
| §16.7 Connection loss | Preserve partial output and offer retry for long-running streams. | Partial through `useAIOperation`; no inventory. | Inventory must mark preservation owner; checker flags missing evidence for long-running SSE operations. |
| §16.8 Vocabulary | `studio.aiActions.*` de/en/fr parity; deprecated aliases absent or governed. | i18n validation for parity. | Add deprecated exact-key usage gate and optional stale-key-definition cleanup policy. |
| §16.9 Machine checks | Compliance is CI-visible and ratcheted. | Current checker has five checks. | Add operation inventory, stale excludes, signal propagation, cancel UI, deprecated aliases, and lifecycle sync. |

---

## 6. Checker Expansion Plan

Platform owns implementation of these gates. The architecture contract is normative;
the exact parser implementation is Platform-owned as long as the same evidence is
machine-checked.

1. **Operation inventory gate** — every AI operation in the inventory has required
   fields; any `open`/`in_progress` status references a CR-AUFG registry entry.
2. **Deprecated alias gate** — reject exact §16.8 deprecated AI-action aliases in
   TS/TSX usage. The checker must not reject unrelated broader namespace keys
   solely because they share a namespace prefix.
3. **Signal propagation gate** — for `useAIOperation` and adapter consumers, verify
   that the `execute(signal)` parameter reaches the API wrapper or transport layer.
4. **Cancel UI gate** — operations marked long-running or streaming must expose a
   visible cancel affordance or a documented `not_applicable` reason in the inventory.
5. **Stale-exclude gate** — entries in `scripts/checks/.ai_interaction_exclude` fail
   when mandatory fields are missing, `re_evaluated` is older than the allowed window,
   or `migration-in-progress` lacks a linked AUFG.
6. **Lifecycle sync gate** — CR-AUFG IDs cited in `_audit/results/content-review/cr-07-ux.md`
   must exist in `aufg-registry.md` or be explicitly marked `covered_by_existing_aufg`.
7. **Resolution evidence gate** — no registry entry may be set to `resolved` without
   implementation files and enforcement evidence named in its Exit evidence block.

---

## 7. Stale-Exclude Policy

`scripts/checks/.ai_interaction_exclude` is a temporary governance tool, not a
waiver mechanism.

Rules:

1. Each entry keeps ADR-043 mandatory fields: file, owner, gate, reason, exit,
   added, and re_evaluated.
2. `migration-in-progress` entries must also link to a durable AUFG ID before the
   stale-exclude gate can pass.
3. `re_evaluated` must be refreshed at least quarterly. For P1 AI-UX debt, refresh
   before every release-readiness claim.
4. When an AUFG is resolved, linked excludes must be removed unless they remain
   valid under one of ADR-043's structural categories: `hook-internals`,
   `non-react-extension`, or `central-test-helper`.
5. A structural exclude must still have an exit condition. Permanent exceptions
   require Architecture re-review and either `accepted_risk` or `not_applicable`
   lifecycle state in the AUFG registry.

---

## 8. Lifecycle Sync Rule for CR-AUFG IDs

Every material CR-AUFG finding has exactly one durable lifecycle state in
`docs/architecture/governance/aufg-registry.md`.

Status discipline:

- `_audit/results/**` is evidence input, not lifecycle SSOT.
- `CURRENT_STATE.md` must reflect the conservative status from the registry.
- `resolved` requires implementation + enforcement evidence and, where applicable,
  verification of signal propagation or user-visible UX behavior.
- A checker passing without inventory coverage is not full §16 compliance.
- A component using `useAIOperation` is not automatically compliant unless its UI
  exposes the required controls and the transport receives cancellation.

---

## 9. Implementation Sequencing

1. **Architecture (this slice)**
   - Create this governance spec.
   - Register CR-AUFG-07-07 through CR-AUFG-07-13 in the AUFG registry.
   - Correct `CURRENT_STATE.md` to remove full-implementation overclaims.

2. **Frontend**
   - Implement CR-AUFG-07-07 through CR-AUFG-07-13 without changing governance
     semantics.
   - Add/adjust component and hook tests proving visible cancel, signal propagation,
     structured errors, loading state, and keyboard behavior.
   - Remove obsolete migration excludes or update them with linked AUFG evidence.

3. **Platform**
   - Expand `scripts/checks/check_ai_interaction_compliance.py` or successor modules
     per §6.
   - Add tests for each new gate and wire the gate into the existing AI-UX command.
   - Ensure lifecycle sync blocks audit-only CR-AUFG loss.

4. **Docs**
   - Update `ui-principles.md` §16.9 after Platform checkers exist.
   - Update `CURRENT_STATE.md` and AUFG exit evidence only after Frontend and
     Platform evidence exists.

---

## 10. RULE-XX Compliance

| Rule | Status | Nachweis |
|------|--------|----------|
| RULE-03 | ✅ | This spec is the contract before Frontend/Platform implementation. |
| RULE-04 | ✅ | Production implementation is out of scope; future checker expansion must modularize rather than grow one monolithic script. |
| RULE-06 | ✅ | Governance spec, AUFG lifecycle, frontend remediation, and platform checks remain separate responsibilities. |
| RULE-10 | ✅ | Platform and Frontend tests are explicit DoD before any `resolved` status. |
| RULE-11 | ✅ | Errors must be structured/actionable; silent GhostText dismissal is tracked as CR-AUFG-07-10 rather than concealed. |
| RULE-13 | ✅ | SSE-capable AI operations remain governed by streaming/cancel semantics; no REST-only deferral. |
| RULE-16 | ✅ | Canonical `studio.aiActions.*` vocabulary and de/en/fr parity remain required. |
| RULE-17 | ✅ | Frontend/backend transport contracts are captured in the operation inventory. |
| RULE-20 | ✅ | No half-implementation claims: CR-07 remains open until frontend fixes and enforcement exist. |
| RULE-21 | ✅ | Any deviation from this spec requires Architecture re-review. |
| RULE-22 | ✅ | Cross-feature AI-UX compliance is checked through a shared inventory, not feature-local claims only. |

---

## 11. Sustainability Check

1. **Still correct in 3 months?** Yes. Inventory + lifecycle sync remains valid as
   AI operations grow.
2. **Hard-to-undo coupling?** No. The spec separates inventory, frontend code, and
   Platform gates rather than coupling features through a global runtime provider.
3. **Simplest correct solution?** Yes. It reuses ADR-043 and ADR-047 instead of
   inventing a duplicate primitive or governance ADR.
4. **Design intent understandable?** Yes. Root cause, artifact decision, enforcement
   matrix, and sequencing are documented here.

---

## 12. Review Triggers

- Any new frontend AI operation is added.
- Any `migration-in-progress` exclude exceeds its re-evaluation window.
- A CR-AUFG-07 entry is proposed for `resolved` without both implementation and
  enforcement evidence.
- `useAIOperation` or its successor interface changes.
- A WebSocket AI lifecycle primitive (`useAISession`) is introduced.
