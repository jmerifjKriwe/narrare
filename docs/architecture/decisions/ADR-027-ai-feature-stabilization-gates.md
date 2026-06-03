# ADR-027 — AI Feature Stabilization Gates

> **Status:** ✅ Accepted
> **Date:** 2026-06-02
> **Deciders:** Architecture Specialist
> **Supersedes:** —
> **Related:** ADR-002, ADR-019, ADR-025, ADR-026, INFRA-011, RULE-02, RULE-03, RULE-04, RULE-12, RULE-13, RULE-20, RULE-22

---

## Context

Review 03 found that Narrare's AI infrastructure is strong but unevenly adopted:

- Prompt adoption passes overall (`0.88`) but KB is WARN (`0.78`) and inline fallbacks remain.
- Prompt-structure checks report many warnings: EN-only prompts, missing memory/preference variables, and missing category-specific variables.
- Agent instruction sources contain drift; some path-scoped docs can be read as allowing inline prompts more broadly than RULE-02/RULE-02a.
- Frontend AI streaming has a central `connectSSE`, but Generation/Rewrite/Extend/CoAuthor maintain separate fetch/SSE parsers because the central abstraction is too narrow.
- KB Interview Resume persists state in browser storage without a complete privacy contract.
- MCP/A2A are planned, not implemented; review scope must not imply implemented adapter quality.
- Large frontend hubs are above the spirit of RULE-04 and create review/maintenance risk.

### Root Cause Analysis

**Symptom:** AI features are implemented, but quality checks still produce WARNs and streaming behavior is duplicated.

**Why #1:** The project added several AI surfaces before all AI-specific gates were hard, automated, and cross-layer.

**Why #2:** The enforcement model is split across passive documentation, manual review, and partially automated checks. For streaming, the shared frontend abstraction does not cover all endpoint shapes, so feature code reimplemented parsing.

**Root cause:** AI-feature quality contracts are not yet fully operationalized. More feature implementation would compound inconsistent prompts, duplicated streaming behavior, and documentation drift. Stabilization must therefore become a precondition for new AI work.

---

## Decision Drivers

- RULE-20 forbids half-implementations and deferred streaming.
- RULE-22 requires cross-feature coherence for prompt registry, KB data, memory/preferences, and settings.
- Stage 2.5 Semantic Review must verify prompt/i18n/variable semantics before implementation.
- Stage 3.5 UX Review requires SSE, abort/cancel, partial-output preservation, retry, and clear error handling for AI interactions.
- RULE-04 requires modularization, not compression, for oversized files.
- The 4-client model requires MCP/A2A to be future Service Layer adapters, not peer clients or WebUI-derived APIs.

---

## Options Considered

### Option A — Continue feature work and clean gaps opportunistically

**Pros:**
- Does not pause roadmap items such as ANAL-005.
- Requires fewer immediate gate changes.

**Cons:**
- Violates the root-cause analysis: gaps are produced by weak enforcement, not lack of individual effort.
- New AI features would inherit duplicated SSE parsing and prompt/adoption ambiguity.
- Conflicts with RULE-20 because known prompt and streaming gaps would be deferred.

### Option B — Full stop until every warning is zero immediately

**Pros:**
- Strictest possible quality stance.
- Simple implementation condition: no WARNs at all.

**Cons:**
- Treats all current WARNs as equal before classification.
- Can block implementation on documented low-risk legacy warnings without improving architectural clarity first.
- Encourages superficial warning suppression rather than correct classification and remediation.

### Option C — Stabilization program with ratcheted gates and AI feature freeze

**Pros:**
- Stops new AI scope growth while allowing ordered stabilization work.
- Converts passive governance into operational gates without pretending legacy warnings are already understood.
- Preserves RULE-20: no new half-implementations, no deferred streaming.
- Gives Core, Frontend, Docs, and Platform explicit handoffs and acceptance criteria.

**Cons:**
- Requires baseline and ratchet implementation.
- Delays new AI features until stabilization passes.

---

## Decision

**We choose Option C — Stabilization program with ratcheted gates and AI feature freeze.**

Narrare will treat INFRA-011 as the required stabilization program before new AI features proceed. Current warning debt must be classified and ratcheted down; new warnings and exception growth fail. Frontend AI streaming must converge on one shared transport/parser contract. Documentation sources must be harmonized so path-scoped instructions cannot weaken global constraints.

---

## Rationale

This decision addresses root causes rather than symptoms. Editing individual prompts may reduce warning counts temporarily, but the same drift returns if gates remain WARN-only. Replacing one duplicated SSE parser helps one feature, but the root problem is a too-narrow transport abstraction. Editing one AGENTS file removes one contradiction, but drift returns unless the source hierarchy and no-weaker-rule check are explicit.

The accepted trade-off is roadmap delay for new AI features. That delay is architecturally required: building new AI features on inconsistent prompt, streaming, and documentation contracts would create permanent coupling and violate RULE-20.

---

## Consequences

**Positive:**

- New AI features cannot expand known prompt/streaming debt.
- Prompt/adoption warning behavior becomes measurable and monotonic.
- Frontend streaming behavior becomes consistent across AI features.
- Documentation source hierarchy becomes explicit.
- MCP/A2A remain correctly scoped as future adapters under RULE-12.

**Negative / Tradeoffs:**

- ANAL-005 and other new AI features wait until stabilization gates pass.
- Platform must implement baseline/ratchet mechanics before some cleanup can be validated automatically.
- Frontend SSE migration requires careful tests to avoid event-semantics regressions.

**Constraints introduced:**

- No new AI feature implementation starts until INFRA-011 Core, Frontend, Docs, and Platform gates pass or the user explicitly approves a narrower exception via Architecture review.
- Existing prompt/adoption WARNs must be classified; unclassified WARNs are not acceptable long-term state.
- New WARNs fail after the baseline is established.
- Approved architecture exceptions may not grow without ADR/user approval.

---

## Implementation Notes

- The detailed layer plan and DoD live in `docs/features/infra/INFRA-011-ai-feature-stabilization.md`.
- Platform should create a machine-readable baseline for current prompt/adoption warnings and architecture exceptions.
- Core should fix prompts through `packages/core/narrare_core/prompts/` and ADR-026 mechanisms only.
- Frontend should extend or split `packages/web/lib/api/streaming.ts` into a shared transport/parser with feature accumulators in feature modules.
- Docs should treat `docs/_shared/CONSTRAINTS.md` and ADRs as authoritative; AGENTS/context files may only summarize stricter or equal rules.
- MCP/A2A wording must reference Q-001/Q-002 and RULE-12; no implemented-adapter claims are allowed until adapters exist.

---

## Compliance Checklist

| Rule / Gate | Status | Evidence |
|-------------|--------|----------|
| RULE-02/02a | ✅ | Prompt fixes must route through `core/prompts/` and ADR-026 categories. |
| RULE-03 | ✅ | This ADR and INFRA-011 define contracts before implementation. |
| RULE-04 | ✅ | Frontend hub modularization is part of the stabilization scope. |
| RULE-10 | ✅ | INFRA-011 defines unit/integration/frontend/gate test expectations. |
| RULE-11 | ✅ | Shared streaming errors must be normalized and surfaced. |
| RULE-12 | ✅ | MCP/A2A remain future adapters calling Service Layer. |
| RULE-13 | ✅ | SSE-capable backend AI endpoints require frontend SSE. |
| RULE-20 | ✅ | AI feature freeze prevents known half-implementation growth. |
| RULE-22 | ✅ | Stage 2.5 prompt/KB/memory/settings coherence is explicit in INFRA-011. |
| Stage 3.5 | ✅ | Streaming, abort, partial-output, retry, and error handling are acceptance criteria. |

---

## Review Trigger

- [ ] When all INFRA-011 gates pass, review whether the AI feature freeze can be lifted.
- [ ] When MCP or A2A implementation starts, revisit Q-001/Q-002 and create adapter-specific specs.
- [ ] When a new AI feature requests an exception before stabilization is complete, require Architecture re-review and explicit user approval.
- [ ] If prompt/adoption baseline grows, treat it as an architecture violation unless backed by a new ADR.
