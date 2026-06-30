---
archived: true
archived_at: 2026-06-30
reason: "Completed specification pack — all 7 Phase C subfeatures resolved with implementation + enforcement evidence in aufg-registry.md"
---

# CR-07 Follow-up v3 Phase C — AI-UX Enhancement Specification Pack

> **Status:** Specification pack — review-ready, not implemented
> **Date:** 2026-06-22
> **Owner:** Architecture Specialist
> **Related:** `docs/architecture/governance/cr-07-followup-v3.md`, `docs/architecture/governance/aufg-registry.md`, `docs/development/ui-principles.md` §16, `docs/architecture/governance/ai-ux-compliance-v2.md`

---

## 1. Authoring note — discovery record from authoring session

The authoring session recorded the following discovery notes before direct file
reads. These notes document authoring process context only; they are not
implementation evidence and do not prove runtime behavior:

- `code-review-graph_build_or_update_graph_tool` — incremental graph update after Phase B commits.
- `code-review-graph_get_minimal_context_tool` — CR-07 Phase C task context noted during authoring.
- `code-review-graph_get_architecture_overview_tool` — attempted architecture overview; output exceeded tool limits, so this spec relies on targeted graph queries instead of the truncated dump.
- `code-review-graph_semantic_search_nodes_tool` — broad Phase C searches returned no direct results; fallback was targeted `file_summary` graph queries for known affected files.
- Targeted graph queries were used as authoring aids for `SessionPanel`, `useSessionSocket`, prompt settings, sentiment/beta-reader surfaces, rewrite/co-author/KB enhance review surfaces, and WebSocket/session backend files.

Fallbacks after graph-first during authoring: direct reads of authoritative governance docs, UI principles §16, feature specs, AI Operation Inventory, and selected frontend/backend/core source files. Any implementation claim still requires separate implementation-on-disk and enforcement evidence.

---

## 2. Scope

This pack specifies the seven Phase C subfeatures from CR-07 Follow-up v3. It does **not** authorize production implementation and does **not** mark any AUFG as resolved.

| AUFG | Subfeature spec |
|------|-----------------|
| CR-AUFG-07-18 | [`docs/features/ai-ux/CR-AUFG-07-18-diff-view-standardization.md`](../../features/ai-ux/CR-AUFG-07-18-diff-view-standardization.md) |
| CR-AUFG-07-19 | [`docs/features/ai-ux/CR-AUFG-07-19-prompt-history.md`](../../features/ai-ux/CR-AUFG-07-19-prompt-history.md) |
| CR-AUFG-07-20 | [`docs/features/ai-ux/CR-AUFG-07-20-slash-commands-ai-actions.md`](../../features/ai-ux/CR-AUFG-07-20-slash-commands-ai-actions.md) |
| CR-AUFG-07-21 | [`docs/features/ai-ux/CR-AUFG-07-21-session-stop-websocket-recovery.md`](../../features/ai-ux/CR-AUFG-07-21-session-stop-websocket-recovery.md) |
| CR-AUFG-07-22 | [`docs/features/ai-ux/CR-AUFG-07-22-style-variants-regeneration.md`](../../features/ai-ux/CR-AUFG-07-22-style-variants-regeneration.md) |
| CR-AUFG-07-23 | [`docs/features/ai-ux/CR-AUFG-07-23-emotional-intensity-curve.md`](../../features/ai-ux/CR-AUFG-07-23-emotional-intensity-curve.md) |
| CR-AUFG-07-24 | [`docs/features/ai-ux/CR-AUFG-07-24-feedback-rating-expansion.md`](../../features/ai-ux/CR-AUFG-07-24-feedback-rating-expansion.md) |

### Out of scope for this pack

- Production code, tests, migrations, commits, or status promotion.
- New runtime dependencies.
- Replacing ADR-043 `useAIOperation` or the existing AI Operation Inventory.
- Reopening Phase A/B items that are already resolved unless evidence regresses.

---

## 3. Root cause across Phase C

**Symptom:** Narrare now has §16-compliant AI operations, but higher-level AI output review patterns still vary by feature: diffs, prompt versioning, command invocation, session stop/recovery, regeneration variants, emotional visualizations, and feedback rating do not share a coherent product contract.

**Warum 1?** CR-07 Phase A/B focused on compliance and prompt/onboarding closure. Those phases ensured each operation has lifecycle/cancel/error evidence, but they did not standardize cross-feature review and learning affordances.

**Warum 2?** Existing features were implemented at different times with local UI concepts: rewrite has alternatives/diff, co-author has change lists, KB enhance has before/after fields, beta reader has feedback cards, sessions use WebSocket state, and learning records feedback through separate surfaces.

**Root cause:** AI-UX maturity moved from "operation lifecycle compliance" to "shared author-control patterns," but the architecture still lacks per-subfeature contracts that define reusable vocabulary, ownership, data flow, and enforcement gates.

**Design response:** Keep Phase C decomposed. Each AUFG gets its own spec and remains independently implementable. Shared primitives are introduced only where multiple existing features already need the same behavior.

---

## 4. Alternatives considered for the pack

### Option A — One Phase C mega-feature

**Pros:** One document and one implementation wave.
**Cons:** Violates CR-07's own decomposition rule; completion would be ambiguous; file-size and cross-feature coupling risk would be high.

### Option B — Seven independent feature specs with this governance index (chosen)

**Pros:** Each AUFG has explicit root cause, contracts, tests, i18n, and lifecycle requirements. Shared work can still be sequenced through the umbrella.
**Cons:** More documentation files to maintain.

### Option C — AUFG registry prose only

**Pros:** Minimal file churn.
**Cons:** Registry entries would be too terse for implementation gates and would repeat architecture rationale poorly.

**Decision:** Choose Option B. It is the simplest correct structure: no mega-feature, no duplicate registry-only prose, and no implementation without spec.

---

## 5. Phase C sequencing contract

| Order | AUFG | Reason |
|-------|------|--------|
| 1 | CR-AUFG-07-18 Diff view | Establishes shared review vocabulary before variants and feedback attach to AI outputs. |
| 2 | CR-AUFG-07-24 Feedback rating expansion | Aligns learning semantics for outputs that already have accept/reject flows. |
| 3 | CR-AUFG-07-21 Session stop/recovery | Fixes true transport/server resilience for an existing WebSocket surface; independent of prompt history. |
| 4 | CR-AUFG-07-22 Style variants | Uses shared diff/review and feedback vocabulary for variant comparison. |
| 5 | CR-AUFG-07-19 Prompt history | Depends on PROMPT-003 stability and benefits from shared diff comparison. |
| 6 | CR-AUFG-07-20 Slash commands | Routes to already-governed AI operations; should not precede operation standardization. |
| 7 | CR-AUFG-07-23 Emotional intensity curve | Uses existing ANAL-002 data first; lowest dependency pressure and P3 priority. |

This is an architecture sequencing constraint, not an implementation plan. Any material deviation requires Architecture re-review under RULE-21.

---

## 6. RULE-XX compliance matrix

| Rule | Status | Evidence / requirement |
|------|--------|------------------------|
| RULE-03 | ✅ Specified | Subfeatures with backend/core changes require Protocols before services; frontend-only contracts are explicit TS interfaces before component expansion. |
| RULE-04 | ✅ Specified | Shared primitives prevent repeated large feature-local diff/rating/command logic; specs name split boundaries. |
| RULE-06 | ✅ Specified | UI primitives, API clients, services, repositories, schemas, and platform checks are separated by responsibility. |
| RULE-10 | ✅ Specified | Each subfeature names unit, integration, component, and checker gates required before `resolved`. |
| RULE-11 | ✅ Specified | Error and recovery states are explicit; no silent WebSocket, prompt history, or feedback failures. |
| RULE-13 | ✅ Specified | AI streaming paths continue to use SSE/WebSocket streaming; no REST-only replacement for streaming output. |
| RULE-16 | ✅ Specified | All new user-facing text requires DE/EN/FR keys and registered namespace parity. |
| RULE-17 | ✅ Specified | Any new or changed backend schemas require frontend type parity and contract tests. |
| RULE-20 | ✅ Specified | Each increment must be complete and usable; no UI-only stop, fake analytics, or history without restore/compare semantics. |
| RULE-21 | ✅ Specified | Material changes to contracts, endpoints, storage, or shared primitives require re-review. |
| RULE-22 | ✅ Specified | Prompt history, feedback learning, style variants, and shared diff all define cross-feature data contracts. |
| RULE-23 | ✅ Specified | Tests must use typed fakes/protocols; no suppressions as a workaround. |

---

## 7. Sustainability check

1. **Still correct in 3 months?** Yes. The pack creates durable AUFG-level specs and keeps shared primitives explicit.
2. **Hard-to-undo coupling?** No. Shared primitives are frontend contracts or service protocols; backend state remains owned by domain modules.
3. **Simplest correct solution?** Yes. It reuses ADR-043, PROMPT-003, WRITE/KB/ANAL/LEARN specs, and existing settings/model cascades.
4. **Design intent understandable?** Yes. Each spec states root cause, layer ownership, contracts, acceptance criteria, tests, and exclusions.

---

## 8. Review gate

Implementation planning may start only after user review of this specification pack. The next step after approval is implementation planning for the chosen first AUFG, not coding.
