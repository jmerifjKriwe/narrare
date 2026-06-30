---
archived: true
archived_at: 2026-06-30
reason: "Completed epic specification — all 11 work items (CR-AUFG-07-14 through CR-AUFG-07-24) resolved with implementation + enforcement evidence in aufg-registry.md"
---

# CR-07 Follow-up v3 — AI UX Compliance & Modernization Epic

> **Status:** Architecture specification — review-ready, not implemented
> **Date:** 2026-06-21
> **Owner:** Architecture Specialist
> **Related:** CR-07 UX audit, `docs/development/ui-principles.md` §16, `docs/architecture/governance/ai-ux-compliance-v2.md`, `docs/architecture/governance/aufg-registry.md`, `docs/features/prompt-customization-ux.md`, `docs/features/onboarding-user-guide.md`

---

## 1. Scope

This document specifies the staged CR-07 Follow-up v3 epic. It is a governance and
implementation contract for future specialists; it does not mark any item resolved.

### In scope

- **Phase A:** residual §16 compliance plus frontend i18n fallback hardening.
- **Phase B:** feature-level gaps:
  - PROMPT-003 implementation path with contract-first Core/Backend/Frontend boundaries.
  - ONBOARD-001 conceptual "aha moment" follow-up for KB + Storyboard + AI.
- **Phase C:** CR-07 §8 modern AI-UX enhancements, split into independently reviewable subfeatures.
- AUFG lifecycle entries for every new actionable work item.
- Platform enforcement plan so future "green" claims are tied to explicit regression gates.

### Out of scope

- Production code changes.
- Test implementation.
- Marking CR-07, PROMPT-003, or ONBOARD-001 follow-ups as `resolved`.
- New runtime dependencies or tech-stack changes.
- Reopening already resolved CR-AUFG-07-07 through CR-AUFG-07-13 unless their evidence regresses.

---

## 2. Root Cause Analysis

**Symptom:** CR-07 v2 closed the originally registered §16 gaps, but follow-up review still finds hardcoded UI fallbacks, silent GhostText error behavior, an unimplemented prompt-customization UX, an incomplete conceptual onboarding story, and unplanned modern AI-UX enhancements.

**Warum 1?** The previous closure focused on the shared AI interaction primitive and the seven immediate compliance findings. It did not treat adjacent user-understanding gaps, fallback-string drift, and CR-07 §8 enhancement potential as a single governed epic.

**Warum 2?** The governance surface validates operations and resolved AUFG evidence, but it does not yet block frontend `t(...) || "English fallback"` drift, does not decide GhostText error affordance semantics, and does not connect planned feature specs (PROMPT-003 / ONBOARD-001) to CR-07 lifecycle work items.

**Root cause:** CR-07 compliance was governed at the operation-lifecycle layer, while user-facing text integrity, prompt transparency, conceptual onboarding, and advanced AI-UX patterns remained split across audit prose and planned feature specs. That separation lets "documented" or "planned" look closer to "implemented" than the evidence supports.

**Design response:** Use a staged epic with durable AUFG IDs and enforceable phase gates. Phase A closes hard compliance and fallback regressions first. Phase B turns planned feature specs into contract-first implementation paths without downgrading stable features. Phase C decomposes enhancements into separate subfeatures so modernization does not become an unbounded bucket.

---

## 3. Existing Evidence and Residual Gaps

### Verified residuals

- `ConsistencyCheckPanel.tsx` still has a hardcoded fallback path: `(error?.userMessage ?? t("worldbuilding.error")) || "Check failed"`.
- GhostText has visible loading status from CR-AUFG-07-10, but error affordance semantics remain undecided: silent dismissal is still a user-understanding gap.
- A frontend fallback scan found `t(...) || "English fallback"` patterns in KB, Worldbuilding, Consistency, and related panels, including `AnalysisTabs`, `KBAssistedCreationFooter`, `KBSessionFieldList`, `WorldbuildingAnalysisPanel`, `ConsistencyLoading`, `ConsistencyError`, and `ConsistencyCheckPanel`.
- PROMPT-003 remains `planned`; existing `PromptEditor` / `PromptPreview` are local UI affordances, not a provider-free resolved prompt preview with provenance, diagnostics, optional live test, and contract tests.
- ONBOARD-001 remains `stable` for its implemented demo/tour scope, but CR-07 §5 still identifies a missing conceptual orientation: how KB, Storyboard, and AI work together.

### Status discipline

- CR-AUFG-07-07 through CR-AUFG-07-13 stay `resolved` because their current registry entries include implementation and enforcement evidence.
- New work is tracked as CR-AUFG-07-14 through CR-AUFG-07-24 and starts `open`.
- ONBOARD-001 is not downgraded: its original acceptance criteria are complete. The new conceptual-tour gap is a follow-up AUFG, not proof that ONBOARD-001's earlier scope was falsely stable.
- PROMPT-003 remains `planned` until the full feature DoD is implemented and enforced.

---

## 4. Alternatives Considered

### Option 1 — One monolithic "CR-07 v3 fix" implementation wave

**Description:** Put all residuals and §8 enhancements into one implementation task.

**Pros:** One delivery label; fewer lifecycle entries.

**Cons:** Violates the intent of RULE-20 by making completion ambiguous; Phase A compliance could be blocked by speculative Phase C enhancements. Hard to review, hard to test, and likely to generate broad file-size pressure.

### Option 2 — Staged epic with phase gates (chosen)

**Description:** Split into Phase A compliance, Phase B feature-level gaps, and Phase C modern enhancements, with separate AUFG IDs and acceptance criteria.

**Pros:** Lets compliance land before enhancements; each phase has clear owners and enforcement; supports RULE-21 re-review if a phase materially changes; avoids turning §8 into an unstructured backlog.

**Cons:** More governance surface to maintain; Coordinator must sequence handoffs carefully.

### Option 3 — Only update PROMPT-003 and ONBOARD-001 specs

**Description:** Treat all residuals as feature documentation updates and avoid a governance epic.

**Pros:** Minimal new documentation.

**Cons:** Misses Phase A checker needs and Phase C decomposition. Audit findings would remain prose-only and could be lost outside the AUFG lifecycle SSOT.

### Recommendation

Choose **Option 2**. It is the simplest correct architecture: hard compliance first, contract-first feature implementation second, enhancements third. It avoids workaround sequencing and keeps every new claim tied to an AUFG lifecycle state.

---

## 5. ADR Decision

**No new ADR is required for this specification.**

Reasoning:

- No new architectural primitive is introduced; ADR-043 already governs AI interaction primitives.
- No new external dependency or tech-stack change is proposed.
- No RULE-XX exception is requested.
- Prompt resolution remains inside `core/prompts/` under existing RULE-02/RULE-02b constraints; PROMPT-003 needs a feature/contract implementation path, not a new prompt architecture decision.
- AUFG lifecycle governance already exists in ADR-047's registry surface.

**ADR trigger for future re-review:** A future phase must return to Architecture for an ADR if it introduces a new prompt resolution mechanism, changes `useAIOperation`/WebSocket lifecycle primitives materially, adds a dependency, changes public Service Layer API semantics across clients, or requests a RULE-XX exception.

---

## 6. Epic Phase Plan

### Phase A — Residual §16 Compliance + i18n Fallback Hardening

**AUFG IDs:** CR-AUFG-07-14, CR-AUFG-07-15
**Priority:** P1
**Owners:** Frontend Specialist → Platform Specialist → Docs Specialist
**Depends on:** CR-AUFG-07-07 through CR-AUFG-07-13 resolved evidence; `check_ai_interaction_compliance.py` current checks 1-11.

#### A.1 Consistency and hardcoded fallback cleanup

Scope:

- Remove the Consistency hardcoded fallback path and replace it with structured i18n-backed error handling.
- Remove or justify every production `t(...) || "English fallback"` occurrence in KB/Worldbuilding/Consistency UI.
- Ensure fallback removal does not hide missing i18n keys; missing keys must fail tests/checkers, not degrade to English strings.

Acceptance criteria:

- `ConsistencyCheckPanel`, `ConsistencyError`, `ConsistencyLoading`, and related components use registered i18n keys or typed error objects, not hardcoded fallback strings.
- Every visible string remains available in DE/EN/FR through the registered namespace(s).
- Components still render actionable errors under §16.5.
- No production TS/TSX file in `packages/web/components/studio/kb/` uses `t(...) || "..."` or equivalent `?? "..."` visible fallback except explicitly approved non-UI data cases.

#### A.2 GhostText error affordance decision

Chosen semantics:

- GhostText may remain a governed non-React extension for lifecycle mechanics.
- Fetch failures must no longer be purely silent. The UI must expose a low-noise, localized affordance appropriate to inline suggestions: transient status decoration, editor status text, or non-blocking notification.
- The affordance must not interrupt typing, must not modal-block, and must clear after retry/success or user dismissal.

Acceptance criteria:

- GhostText error state is visible enough for users to understand that suggestions are unavailable.
- Visible text is injected through localized extension options or a React-controlled status surface, never hardcoded in ProseMirror DOM code.
- Retrying preserves typed content and does not auto-apply suggestions.
- The AI Operation Inventory records loading, error, retry, and exception semantics for `editor.ghost_text`.

#### A.3 Platform gate

Required gate:

- Add an i18n fallback hardening checker, either as check 12 under AI-UX compliance or as a broader frontend i18n checker wired into `just check`.
- The checker must flag visible hardcoded fallback patterns such as `t("key") || "Text"`, `(t("key")) ?? "Text"`, and hardcoded fallback branches in production TS/TSX.
- The checker must allow documented exceptions for test fixtures, mock data, and non-user-visible data labels only through a narrow allowlist with owner and review trigger.

Definition of Done:

- Frontend cleanup is present on disk.
- Checker and checker tests are present on disk.
- `just check-ai-ux` or successor plus the frontend i18n validator fail on reintroduced fallbacks.
- AUFG entries are updated only after implementation and enforcement evidence exists.

---

### Phase B — Feature-Level Gaps

**AUFG IDs:** CR-AUFG-07-16, CR-AUFG-07-17
**Priority:** P1/P2
**Owners:** Architecture Specialist for contract review → Core Specialist → Backend Specialist → Frontend Specialist → Platform Specialist → Docs Specialist
**Depends on:** Phase A for fallback gate; PROMPT-001/002; INFRA-002; ONBOARD-001 existing implementation.

#### B.1 PROMPT-003 implementation path

PROMPT-003 stays `planned` until all layers below are implemented and enforced.

##### Core boundaries

Implementation must start with contracts before service logic:

| Path | Responsibility |
|------|----------------|
| `packages/core/narrare_core/prompts/contracts.py` | Protocols for provider-free preview resolution and variable metadata access. |
| `packages/core/narrare_core/prompts/preview_types.py` | Typed preview results, diagnostics, variable metadata, provenance/security view models. |
| `packages/core/narrare_core/prompts/preview.py` | Provider-free prompt rendering via existing PromptComposer/variable engine path; no model/provider imports. |
| `packages/core/narrare_core/prompts/variable_taxonomy.py` | Existing provenance/security taxonomy remains the source for variable metadata; extend only if required by contract review. |

Contract semantics:

- Preview resolves prompt text, variable substitutions, provenance, security class, cascade source, and diagnostics.
- Preview must not call the LLM Gateway, instantiate agents, import provider SDKs, or consume tokens.
- Missing variables return typed diagnostics; they do not degrade to inline prompt fallbacks.
- User-authored variables retain injection-defense metadata so UI can explain why XML wrapping/security rules exist.

##### Backend boundaries

| Path | Responsibility |
|------|----------------|
| `apps/api/narrare/prompts/contracts.py` | Extend existing prompt service Protocols before implementation. |
| `apps/api/narrare/prompts/schemas.py` | Pydantic v2 request/response schemas for preview, live-test start/stream metadata, reset. |
| `apps/api/narrare/prompts/preview_service.py` | Orchestrates provider-free preview through injected core prompt preview protocol. |
| `apps/api/narrare/prompts/live_test_service.py` | Optional live-test orchestration through the approved agent/gateway/model registry path. |
| `apps/api/narrare/prompts/router.py` or split `router_prompt_ux.py` | Thin routes only; split before RULE-04 pressure. |

Endpoint contract:

- `POST /api/v1/settings/prompts/{intent}/preview` — REST, no provider required, no model call.
- `POST /api/v1/settings/prompts/{intent}/reset` — REST, removes the override and returns current effective prompt metadata.
- Optional live test — SSE for generated output; REST may create metadata only if needed. The live test must use the normal Narrare agent/gateway/model registry route and §16 UI semantics.

##### Frontend boundaries

| Path | Responsibility |
|------|----------------|
| `packages/web/lib/api/prompts.ts` | Typed API client methods for preview, reset, and live test transport. |
| `packages/web/components/studio/settings/PromptEditor.tsx` | Orchestrator only; no direct preview substitution logic. |
| `packages/web/components/studio/settings/PromptPreviewDialog.tsx` | Provider-free resolved prompt view with diagnostics/provenance. |
| `packages/web/components/studio/settings/VariableMetadataPanel.tsx` | Variable descriptions, examples, source/provenance/security labels. |
| `packages/web/components/studio/settings/PromptLiveTestDialog.tsx` | Optional SSE live-test UI using §16 lifecycle controls. |
| `packages/web/components/studio/settings/PromptResetConfirmDialog.tsx` | Reset confirmation and status. |

Frontend rules:

- Do not locally substitute variables with hardcoded sample values as the authoritative preview.
- Provider-free preview and live test must be visually distinct.
- Live test must show token/privacy warning before first run per prompt/session.
- Live test uses SSE if it generates model output; no REST-only streaming deferral.

Acceptance criteria:

- Contract files exist before implementation files are expanded.
- Preview endpoint can be tested without configured provider secrets.
- Variable metadata includes provenance and security classification.
- Reset semantics delete or deactivate only the user/project override; bundled defaults remain immutable.
- Optional live test is provider-/secret-gated, rate-limited, stream-capable, and never counted as preview evidence.

#### B.2 ONBOARD-001 conceptual "aha moment" follow-up

ONBOARD-001 remains `stable`; this follow-up adds a new conceptual guidance layer.

Required user story:

> "Narrare helps because your KB stores facts, the Storyboard plans narrative structure, and AI actions draw from both. If you update KB or Storyboard context, future AI suggestions become more coherent."

Scope:

- Add a conceptual tour/story, not just feature-location tour steps.
- Explain KB → context assembly → AI output and Storyboard → chapter plan → AI output at a high level.
- Include one concrete "before/after" or guided demo moment using existing demo projects.
- Keep explanations localized and accessible from onboarding replay/help.

Acceptance criteria:

- First-run or replayable tour includes a conceptual "How Narrare thinks with your world" step.
- The tour distinguishes KB, Storyboard, and AI without exposing implementation jargon.
- The explanation does not claim AI uses context that the runtime path does not actually consume.
- User-facing text is in DE/EN/FR and follows the no-hardcoded-string gate.

Definition of Done for Phase B:

- PROMPT-003 contract-first implementation evidence exists across Core/Backend/Frontend.
- ONBOARD-001 follow-up is implemented without changing the stable status semantics of the original feature.
- Prompt preview contract tests, API/frontend contract tests, and component tests are present.
- AUFG statuses remain `open` or `in_progress` until enforcement evidence exists.

---

### Phase C — Modern AI-UX Enhancements

**AUFG IDs:** CR-AUFG-07-18 through CR-AUFG-07-24
**Priority:** P2/P3 by subfeature
**Owners:** Architecture Specialist for each subfeature spec review → domain specialists by feature
**Depends on:** Phase A complete; Phase B complete for prompt-history work that depends on prompt customization.

Each Phase C item needs its own feature/spec slice before implementation. None may be implemented as an unstructured "UX polish" bucket.

| ID | Subfeature | Priority | Dependencies | Acceptance criteria |
|----|------------|----------|--------------|---------------------|
| CR-AUFG-07-18 | Diff view standardization for Rewrite, Co-Author, KB Enhance, Beta Reader | P2 | Existing rewrite/co-author diff affordances; KB Enhance review UI; Beta Reader issue model | Shared diff vocabulary and component contract; consistent original/suggested/accepted states; keyboard and a11y tests; no feature-specific duplicate diff logic when a shared primitive is appropriate. |
| CR-AUFG-07-19 | Prompt history | P2 | PROMPT-003 preview/reset contracts; PROMPT-001/002 storage semantics | Version/history semantics for prompt overrides; restore/compare behavior; privacy and retention policy; contract tests proving history does not affect active prompt unless restored. |
| CR-AUFG-07-20 | Slash commands for AI actions | P3 | Editor command architecture; §16 action vocabulary; prompt/context contracts | Command grammar, discoverability, i18n labels, conflict handling with TipTap shortcuts, and tests for command parsing and action routing. |
| CR-AUFG-07-21 | SessionPanel server-side stop + WebSocket recovery | P2 | WRITE-005 session contracts; Chat/Session WebSocket path; existing cancel semantics | Stop reaches server-side session state; connection loss preserves partial state; retry/reconnect semantics documented and tested. |
| CR-AUFG-07-22 | Regenerate with style variants | P2 | Rewrite variants; generation/co-author output review components; style/tone settings | Variant taxonomy, consistent regenerate UI, accept/reject semantics, and tests proving selected variant flows into the correct service request. |
| CR-AUFG-07-23 | Emotional intensity curve | P3 | Analysis visualization patterns; sentiment/emotion analysis data contracts | Feature spec defines whether this is deterministic analysis, LLM analysis, or hybrid; chart contract; no speculative model call without service/prompt contract. |
| CR-AUFG-07-24 | AI feedback rating expansion to Co-Author, KB flows, Chat | P2 | LEARN-001 feedback service; mem0 memory contract; existing generation rating | Rating component reused or generalized; feedback persistence path defined; privacy-safe learning semantics; tests proving rating reaches the intended service/memory boundary. |

Phase C sequencing:

1. CR-AUFG-07-18 and CR-AUFG-07-24 first: they standardize existing output/review patterns.
2. CR-AUFG-07-21 next: closes resilience semantics for already-existing session surfaces.
3. CR-AUFG-07-22 after diff/rating patterns are stable.
4. CR-AUFG-07-19 after PROMPT-003 Phase B contracts exist.
5. CR-AUFG-07-20 and CR-AUFG-07-23 last unless the user explicitly prioritizes them.

Definition of Done for Phase C:

- Each subfeature has a feature spec or ADR-trigger decision before implementation.
- Shared primitives are extracted when multiple features need the same UI/contract behavior.
- Tests and AI Operation Inventory updates exist for every AI-affecting UI path.
- No subfeature is marked `resolved` from documentation alone.

---

## 7. RULE-XX Compliance Matrix

| Rule | Status | Evidence / requirement |
|------|--------|------------------------|
| RULE-03 | ✅ Specified | Phase B requires Core and Backend Protocols before implementation; Phase C items require a spec/contract before code. |
| RULE-04 | ✅ Specified | PromptEditor and router growth must split into focused files; Phase C shared primitives prevent bloated feature components. |
| RULE-06 | ✅ Specified | Governance, frontend UI, backend services, core prompt rendering, and platform gates have separate responsibilities. |
| RULE-10 | ✅ Specified | Each phase names regression tests/checkers required before any resolved status. |
| RULE-11 | ✅ Specified | GhostText silent errors and Consistency fallback errors are explicitly tracked rather than hidden. |
| RULE-13 | ✅ Specified | PROMPT-003 live test and SessionPanel recovery must use streaming-capable interfaces where model output streams. |
| RULE-16 | ✅ Specified | Phase A blocks fallback strings and requires DE/EN/FR parity for new user-facing text. |
| RULE-17 | ✅ Specified | PROMPT-003 preview/live-test/reset schemas require API↔Frontend contract tests. |
| RULE-20 | ✅ Specified | Staged phases are complete subsystems, not partial "for now" implementations; no item resolves without implementation + enforcement. |
| RULE-21 | ✅ Specified | Material changes to phase boundaries, contracts, endpoints, or public APIs require Architecture re-review. |
| RULE-22 | ✅ Specified | PROMPT-003 shares prompt registry/context data; ONBOARD-001 claims must match runtime context consumption; feedback expansion touches learning/memory. |
| RULE-23 | ✅ Specified | New tests/fakes must implement Protocols instead of suppressing type errors; no new suppression is acceptable without review. |

---

## 8. Enforcement Plan

### Platform gates

- **i18n fallback hardening:** checker for visible `t(...) || "..."` / nullish fallback strings in production TS/TSX, with narrow governed allowlist.
- **AI-UX operation inventory:** extend existing inventory for GhostText error semantics, PROMPT-003 live test, and Phase C AI operations.
- **Prompt preview contract tests:** Core tests prove preview uses `core/prompts/` and does not call providers; API tests prove response schemas match frontend types; frontend tests prove preview/live-test/reset states.
- **Live-test streaming gate:** ensure any PROMPT-003 live test that generates model output uses SSE and abort signal propagation.
- **Session stop/recovery tests:** for CR-AUFG-07-21, prove server-side stop and WebSocket recovery behavior rather than local UI cancellation only.
- **§8 feature tests:** each Phase C subfeature must add targeted component/service/contract tests matching its acceptance criteria.

### Evidence required before `resolved`

Every new AUFG requires:

1. Design evidence: this spec or a more specific feature/ADR spec.
2. Implementation evidence: exact files on disk.
3. Enforcement evidence: checker/test names and command output from the responsible specialist.
4. Cross-feature evidence where applicable: prompt context, KB/Storyboard, learning/memory, or API/frontend contract verification.

---

## 9. Sustainability Check

1. **Still correct in 3 months?** Yes. The phase split separates compliance, planned features, and enhancements; new AI operations can be added by extending the inventory and AUFG lifecycle.
2. **Hard-to-undo coupling?** No. Core prompt preview is separated from backend orchestration and frontend presentation; Phase C requires shared primitives only where cross-feature behavior repeats.
3. **Simplest correct solution?** Yes. It reuses ADR-043, ADR-047, existing prompt architecture, and existing frontend patterns instead of adding dependencies or bypassing contracts.
4. **Design intent understandable?** Yes. Each phase has owners, dependencies, acceptance criteria, and explicit non-resolution semantics.

---

## 10. Handoff Plan

1. **Architecture Specialist** — finalize this spec and registry entries; review any material phase changes.
2. **Frontend Specialist (Phase A)** — remove hardcoded fallbacks, decide and implement GhostText error affordance.
3. **Platform Specialist (Phase A)** — add i18n fallback checker and tests; wire into existing check command.
4. **Core Specialist (Phase B/PROMPT-003)** — define prompt preview contracts/types and provider-free preview logic.
5. **Backend Specialist (Phase B/PROMPT-003)** — implement preview/reset/live-test services and thin routes after contracts exist.
6. **Frontend Specialist (Phase B)** — implement PROMPT-003 UI surfaces and ONBOARD-001 conceptual tour follow-up.
7. **Platform Specialist (Phase B)** — add prompt preview/API/frontend contract tests and AI-UX inventory coverage.
8. **Architecture Specialist (Phase C pre-gate)** — create/review per-subfeature specs before any Phase C implementation.
9. **Docs Specialist** — update user-facing docs/help/status only after implementation and enforcement evidence exists.

---

## 11. Review Triggers

- Any new AI operation is added to the frontend.
- A phase proposes a new endpoint, service contract, or shared frontend primitive not listed here.
- PROMPT-003 implementation deviates from provider-free preview vs live-test separation.
- ONBOARD-001 text claims runtime context consumption not proven by implementation.
- Any CR-AUFG-07-14 through CR-AUFG-07-24 is proposed for `resolved` without enforcement evidence.
- Phase C subfeature scope expands beyond its row in §6.
