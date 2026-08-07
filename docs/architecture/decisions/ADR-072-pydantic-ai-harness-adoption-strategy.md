# ADR-072 — pydantic-ai-harness Adoption Strategy

> **Status:** ✅ Accepted
> **Date:** 2026-07-25
> **Deciders:** Architecture Specialist (Phase 1 + 2 evaluation), Coordinator (escalation resolution)
> **Supersedes:** —
> **Relates to:** ADR-058 (ProcessHistory Sliding Window — confirmed, **not** superseded),
> ADR-015 (pydantic-AI Agents as First-Class Citizens), ADR-033 (mem0 Memory Architecture),
> ADR-066 (Agent Context Store)
> **Amendment (2026-08-07):** `pydantic-ai-harness` dependency **fully removed**
> from `packages/core/pyproject.toml` + `uv.lock`; 0 capabilities adopted; strategic
> decision (Option C) unchanged. See [Amendment below](#adr-072-amendment--dependency-fully-removed-2026-08-07).

---

## Context

A user question about the value of [`pydantic-ai-harness`](https://github.com/pydantic/harness)
for Narrare triggered a two-phase architectural evaluation. This ADR consolidates the
findings of both phases into a single adoption-strategy decision.

### Phase 1 — Spike (pydantic-ai-slim upgrade + Harness install)

**Scope:** Verify that upgrading `pydantic-ai-slim` from 2.13.0 → 2.18.0 (and adding
`pydantic-ai-harness==0.11.0` for evaluation) is safe.

**Result:** ✅ Upgrade is safe — **0 Breaking Changes** for Narrare. The V2 migration
(the large breaking-change bundle: `OpenAIChatModel` rename, `builtin`→`native`,
`history_processors`→`ProcessHistory`, `Usage`→`RunUsage`, MCP API, Google provider
consolidation) was already absorbed at 2.13.0. The 2.13→2.18 path lies entirely within
the V2 stability window (V2 promises no breaking changes until V3).

Evidence: `pyright --strict` → 0 errors; `pytest tests/unit/` → 9630 passed, 0 failed;
0 `PydanticAIDeprecationWarning`. Full spike findings:
`feat/pydantic-ai-upgrade` branch (worktree `/tmp/opencode/narrare-spike-pydantic-ai`),
documented in `_spike-pydantic-ai-upgrade-findings.md`.

### Phase 2 — Capability Build-vs-Buy Evaluation

**Scope:** Evaluate all 9 Harness capabilities potentially relevant to Narrare against a
strict Build-vs-Buy framework (function need → existing coverage → harness advantage →
cost/risk → decision). Full evaluation: [`_phase2-capability-evaluation.md`](_phase2-capability-evaluation.md).

**Result:** **0 capabilities adopted.** Distribution: EXTEND (2), DEFER (4), BUILD (1),
REJECT (2). The common factor across every non-adoption: **Harness 0.11.0 is
`Development Status :: 3 - Alpha` with 0.x versioning** — minor releases may include
breaking changes (renames, defaults, restructured APIs); only patch releases are stable.
Every ADOPT decision would therefore impose a per-minor-bump migration cost on Narrare.

### Coordinator-Resolved Escalation Points

Phase 2 surfaced three decisions that were escalated to the Coordinator. All three were
resolved in favour of the conservative recommendation:

1. **Compaction — conservative.** Confirmed: ADR-058 sliding window stays In-House
   (~40 lines). No LLM-based `SummarizingCompaction` for creative-writing coherence
   (a silent summary could drop a crucial foreshadowing beat).
2. **Guardrails — EXTEND, not ADOPT.** Confirmed: refactor the three scattered
   validators (`worldbuilding_validators.py`, `beta_reader_validators.py`,
   `draft_validators.py`) into an in-house `NarrareGuardrails` capability. Keeps
   user-defined rules (CONS-002) in our prompt cascade, not a generic registry.
3. **Memory — REJECT.** Confirmed: ADR-066 (`AgentContextStore`, ✅ Accepted) + mem0
   (ADR-033, ✅ Implemented) cover Narrare's governed preference/artifact memory needs.
   Harness Memory is a *model-writable* notebook — wrong abstraction for a creative-
   writing tool that requires explicit, auditable preference signals.

---

## Decision Drivers

- **Local-first principle.** Narrare must not acquire a hard cloud dependency. Paid/
  external capabilities (Exa API, hosted stores) breach local-first unless wrapped in a
  provider adapter with a local fallback.
- **0.x lock-in avoidance.** Harness 0.x/Alpha imposes per-minor-bump migration cost.
  No current unmet need justifies accepting that cost. `pydantic-ai-slim` 2.18, by
  contrast, is in the V2 stability window — safe to adopt.
- **Premature-coupling avoidance.** Every roadmap feature that *might* benefit from a
  Harness capability (WRITE-008, GEN-002, PLAN-001/002, WRITE-013, CONS-002, ANAL-006)
  is `📋 planned` **without a spec**. Adopting now couples Narrare to a 0.x API before
  the data model is defined.
- **Domain control.** Narrare is a creative-writing tool. Most Harness capabilities
  (CodeMode, Filesystem, Shell, LocalStack, ModalSandbox, Macroscope, ACP) explicitly
  target *coding* agents and are out of scope. The 9 evaluated were the only potentially-
  relevant subset — and even those are either generic (Planning, Subagents) or solve a
  different problem than Narrare has (Memory, ACP).
- **ADR-058 precedent.** ADR-058 already established that ~40 lines of In-House logic
  is preferred over a 0.x dependency. This ADR generalises that precedent to all 9
  capabilities.
- **RULE-01b / RULE-07.** Harness capabilities are `AbstractCapability` subclasses;
  they may only attach inside `core/agents/` (RULE-01b) and must not pull HTTP/DB
  concerns into Core (RULE-07).

---

## Options Considered

### Option A — Full Adoption (3+ capabilities)

Adopt Harness wholesale: Compaction, Step Persistence, Guardrails, Planning as a
starting bundle, expand from there.

**Pros:**
- Battle-tested subsystems (Step Persistence in particular is a non-trivial ~8-module
  subsystem with the exact `fork_run`/`continue_run` semantics WRITE-008 needs).
- Ecosystem conformity — Narrare follows the Harness API shape.
- Less In-House code to maintain.

**Cons:**
- 0.x/Alpha lock-in for capabilities whose ROI is undefined (most drivers are `📋 planned`
  without specs).
- `SummarizingCompaction` lossy semantics unsafe for creative-writing coherence.
- Model-driven Planning/Subagents conflict with Narrare's deterministic `WritingGraph`
  philosophy (we encode the workflow; we do not let the model decide to skip review).
- Harness Memory is the wrong abstraction (model-writable notebook vs. governed
  preference/artifact memory).
- **Rejected:** Premature coupling + 0.x instability outweigh speculative ROI.

### Option B — Selective Adoption (Step Persistence + Exa only)

Adopt only the two highest-ROI candidates: Step Persistence (for WRITE-008) and Exa
Search (for GEN-002, behind a provider adapter).

**Pros:**
- Minimal 0.x surface area.
- Captures the two subsystems where Harness offers genuinely non-trivial value.
- Exa behind an adapter satisfies local-first (DuckDuckGo fallback).

**Cons:**
- Both drivers (WRITE-008, GEN-002) are `📋 planned` **without specs**. Adopting now
  means committing to a 0.x API shape before the data model is defined — if the spec
  diverges from Harness's `StepStore`/`ExaSearch` assumptions, we eat migration cost
  for nothing.
- `is_provider_valid` in Step Persistence hints at provider-specific constraints not yet
  investigated.
- `experimental/acp/` precedent shows Harness is willing to ship experimental APIs
  "without a deprecation period" — even non-experimental 0.x APIs carry that risk.
- **Rejected:** DEFER both until the spec exists. Re-evaluate at spec-time with full
  Build-vs-Buy rigour.

### Option C — No Adoption; In-House/DEFER (recommended)

Adopt **zero** Harness capabilities now. Each capability receives a per-capability
decision (EXTEND / DEFER / BUILD / REJECT) with an explicit re-evaluation trigger.
Update `pydantic-ai-slim` to 2.18.0 (safe per Phase 1).

**Pros:**
- No 0.x dependency in production.
- Full control over capability implementation — domain fit over ecosystem conformity.
- Each future feature session re-evaluates the relevant Harness capability with full
  context (spec, data model, driver) rather than speculation.
- ADR-058 proceeds unchanged (confirmed, not superseded).
- `pydantic-ai-slim` 2.18 is safe to adopt — we capture the upgrade value without the
  Harness risk.

**Cons:**
- Harness battle-tested subsystems (notably Step Persistence) may be re-implemented
  In-House if/when WRITE-008 is specified.
- At Harness 1.0, a migration review of any In-House solutions built in the interim
  may be warranted.
- Lower ecosystem conformity (In-House `NarrareGuardrails` instead of Harness Guardrails).

---

## Decision

**We choose Option C: strategic non-adoption of `pydantic-ai-harness`, combined with a
version update of `pydantic-ai-slim` to 2.18.0.**

### Strategic decision

1. **`pydantic-ai-slim` 2.13.0 → 2.18.0:** ADOPT (safe — V2 stability window, 0 breaking
   changes per Phase 1 spike). Pin in `packages/core/pyproject.toml`. Lockstep
   `pydantic-evals` to 2.18.0.
2. **`pydantic-ai-harness`:** DO NOT ADOPT any capability. The spike-installed
   `pydantic-ai-harness==0.11.0` should move from a production dependency to an
   **optional/dev dependency** (see Implementation Notes), so it remains available for
   spec-time evaluation without shipping to production users.

### Per-capability decisions

Each capability was evaluated in Phase 2 against the strict Build-vs-Buy framework
(function need → existing coverage → harness advantage → cost/risk → decision). The
table below consolidates the decisions and their re-evaluation triggers.

| # | Capability | Decision | Trigger for Re-Evaluation |
|---|-----------|----------|---------------------------|
| 1 | **Compaction** | **EXTEND** (confirm ADR-058) | Empirical evidence from ANAL-010/011 that pure sliding-window drops critical early context in sessions >50 turns → then evaluate (likely still in-house, ~80 lines, with explicit user opt-in for any summarisation). Harness reaches 1.0 → re-evaluate per ADR-058's existing trigger. |
| 2 | **Step Persistence** | **DEFER** | WRITE-008 Architecture session begins. **Highest-value Harness candidate** — at that point evaluate ADOPT (Harness `StepPersistence` + `SqliteStepStore` behind a `RunRepository` adapter, RULE-08) vs. BUILD (in-house `RunPersistence` Protocol + SQLite repo). |
| 3 | **Overflowing Tool Output** | **DEFER** | First agent whose tool return empirically exceeds 25% of the model context window (measured, not speculated) → evaluate ADOPT (behind a Postgres-backed `OverflowStore` adapter) vs. BUILD (`ToolOutputBudget` with per-agent `default_strategy`). |
| 4 | **Guardrails** | **EXTEND** (in-house `NarrareGuardrails`) | CONS-002 or ANAL-006 Architecture session — whichever comes first. Specify `NarrareGuardrails` capability in `core/agents/capabilities/` with `InputGuard`/`OutputGuard` Protocols mirroring Harness's API shape (consolidates 3 scattered validator files; RULE-06 win). |
| 5 | **Planning** | **BUILD** (extend `WritingGraph`) | PLAN-001 or PLAN-002 Architecture session. Add domain-specific planning nodes (`scene_planning`, `gap_analysis`) to the existing pydantic-graph state machine. Do NOT adopt Harness `Planning` — generic task-list model does not match narrative structure; model-driven planning is unsafe for deterministic writing workflows. |
| 6 | **Subagents** | **DEFER** | WRITE-013 Architecture session defines the delegation model. If WRITE-013 only needs new `WritingGraph` nodes → BUILD them. If it needs the model to *choose* delegations at runtime → evaluate Harness `SubAgents`. `DynamicWorkflow` is explicitly "API subject to change" — extra instability. |
| 7 | **Exa Search** | **DEFER** | GEN-002 Architecture session. Build a provider-adapter pattern (Exa-principle generalised): `ResearchProvider` Protocol with `ExaProvider` (paid, opt-in) + `DuckDuckGoProvider` (pydantic-ai native, local-first fallback). Default: DuckDuckGo. **Reality-check note:** the original task premise "Bestehend: WebSearch (DuckDuckGo)" was incorrect — no web search exists in Narrare today; the true baseline is pydantic-ai's native `WebSearch` capability, which Narrare has not yet adopted either. |
| 8 | **Memory** | **REJECT** | None (architectural). Harness Memory is a *model-writable* notebook; Narrare's needs are (a) cross-session user preferences (mem0, ADR-033) and (b) cross-invocation artifact sharing (ADR-066 `AgentContextStore`). Adopting would introduce an ungoverned, model-controlled persistence path that violates RULE-22 and Narrare's privacy discipline (mem0 records structural metadata only, never raw draft prose). Only revisit if a future feature explicitly needs model-writable memory — that requires its own ADR. |
| 9 | **ACP** | **REJECT** | None (protocol mismatch). ACP targets *coding editors* (Zed, Toad) with coding-agent semantics (diff-rendered edits, filesystem tools, terminal toolsets). Narrare's A2A needs (INFRA-006) are service-to-service, not editor-to-agent. Additionally, `experimental/acp/` emits `HarnessExperimentalWarning` and "may change or be removed without a deprecation period" — adopting experimental APIs in production is forbidden by architectural-discipline.md §7. When INFRA-006 is specified, evaluate actual A2A protocols (A2A protocol spec, MCP, or Narrare-defined RPC). |

**Decision distribution:** EXTEND (2), DEFER (4), BUILD (1), REJECT (2).
**Net Harness adoption: ZERO capabilities.**

---

## Rationale

1. **No unmet need justifies an Alpha dependency.** Every "yes, but later" capability is
   driven by a `📋 planned` feature without a spec. Adopting now would couple Narrare to
   a 0.x API before the data model is defined. The Build-vs-Buy framework (architectural-
   discipline.md §1, §3, §5) is explicit: no concrete driver → do not speculate.

2. **"Aufwand" is not an argument for adoption.** Per @no_effort_excuse: the AI
   implements In-House solutions at the same speed as adoption integration. The
   question is not "is Harness less work?" — it is "is Harness the *correct* abstraction?"
   For Memory and ACP the answer is no (wrong problem). For Planning the answer is no
   (wrong paradigm — model-driven vs. deterministic). For Compaction and Guardrails the
   In-House cost is trivially small (~40 and ~150 lines respectively). Only Step
   Persistence and Exa have non-trivial In-House cost — and both are correctly DEFERRED
   until their specs exist, at which point the Build-vs-Buy rigour applies with full context.

3. **Domain control matters for a creative-writing tool.** Narrare's value proposition
   includes *governed* preference learning (explicit feedback signals, auditable per
   RULE-22) and *deterministic* writing workflows (we encode the review step; the model
   does not decide to skip it). Harness optimises for the opposite — model autonomy and
   generic task management. The paradigm mismatch is a feature, not a bug.

4. **Version-policy asymmetry is decisive.** `pydantic-ai-slim` 2.18 is in the V2
   stability window (promises no breaking changes until V3) — safe to adopt, and the
   spike proves 0 breaking changes empirically. `pydantic-ai-harness` 0.11 is Alpha
   with 0.x versioning — minor releases may break. ADOPT would mean accepting per-minor-
   bump migration cost for speculative ROI. The asymmetry is the single most important
   sustainability factor and the reason ADR-058 Option D was rejected (still valid).

5. **Each DEFER has a concrete, named trigger.** This is not "defer indefinitely." Every
   DEFER is bound to a specific feature session (WRITE-008, GEN-002, PLAN-001/002,
   WRITE-013, CONS-002/ANAL-006) or to empirical evidence (>50-turn sessions, tool
   overflow). When the trigger fires, the relevant capability gets a focused Build-vs-Buy
   evaluation as a mandatory spec section.

6. **ADR-058 is confirmed, not superseded.** ADR-058 already rejected Harness Compaction
   (Option D) on pre-1.0 risk. That risk is unchanged in 0.11.0. This ADR confirms
   ADR-058's In-House choice for Compaction and generalises the precedent to the other
   8 capabilities. ADR-058 proceeds to implementation as-specified — ADR-072 modifies
   nothing about it.

---

## Consequences

**Positive:**
- No 0.x/Alpha dependency in production.
- Full control over capability implementation — domain fit over ecosystem conformity.
- Clear, named re-evaluation trigger for every DEFER — nothing is silently shelved.
- ADR-058 unmodified — can proceed to Acceptance and implementation as-specified.
- `pydantic-ai-slim` 2.18 upgrade captures additive value (new `AbstractCapability`
  hooks, `Thinking`, `Instrumentation`, `Hooks`, deferred-loading capabilities) without
  Harness risk.
- The two highest-value Harness candidates (Step Persistence, Exa) are flagged for
  spec-time re-evaluation — not lost.

**Negative / Tradeoffs:**
- Harness battle-tested subsystems may be re-implemented In-House. Most notably, if
  WRITE-008's spec diverges from Harness's `StepStore` assumptions, Narrare builds
  `RunPersistence` from scratch (~non-trivial). This is an accepted tradeoff: the
  alternative is committing to a 0.x API before the spec exists.
- At Harness 1.0, a migration review of any In-House solutions built in the interim
  (Compaction, Guardrails, and any DEFER-turned-BUILD) is warranted. The review trigger
  below makes this explicit.
- Lower ecosystem conformity. In-House `NarrareGuardrails` will diverge in shape from
  Harness Guardrails. This is acceptable — the API surface is small (~4 classes, ~150
  lines) and mirroring Harness's shape costs nothing.
- The Guardrails EXTEND decision introduces a future spec obligation: when CONS-002 or
  ANAL-006 begins, `NarrareGuardrails` must be specified as part of that Architecture
  session. This ADR records the obligation; it does not discharge it.

**Constraints introduced:**
- **Production `pyproject.toml` must NOT add `pydantic-ai-harness`** as a non-optional
  dependency until a capability is adopted via its own ADR. Enforcement: this ADR + the
  existing dependency-review practice. The spike-installed `pydantic-ai-harness==0.11.0`
  moves to optional/dev (see Implementation Notes).
- Every future Architecture session for WRITE-008, GEN-002, PLAN-001/002, WRITE-013,
  CONS-002, or ANAL-006 MUST include a Harness Build-vs-Buy re-evaluation as a mandatory
  spec section, referencing the relevant row in this ADR's Decision table.

---

## Implementation Notes

### What this ADR authorises immediately

| Change | File | Status |
|--------|------|--------|
| `pydantic-ai-slim` 2.13.0 → 2.18.0 | `packages/core/pyproject.toml` | Authorised by this ADR (safe per Phase 1 spike) |
| `pydantic-evals` 2.13.0 → 2.18.0 (lockstep) | `pyproject.toml` (root) | Authorised by this ADR (lockstep with slim) |
| `pydantic-graph` 2.13.0 → 2.18.0 (auto via slim) | (transitive) | Automatic |

### Harness dependency handling

> **Superseded 2026-08-07:** The relocation target described in this section was
> implemented in code (commit `03f253e2`, 2026-07-25 — `harness-eval` optional
> group present in `packages/core/pyproject.toml`), but was **never closed out as
> this ADR's final state** (Gate 12 remained open). On **2026-08-07 the dependency
> was fully removed** instead — from `packages/core/pyproject.toml` **and**
> `uv.lock` — so the `harness-eval` optional group no longer exists anywhere.
> The historical relocation description below is preserved for context; the
> current, authoritative state is **full removal**. See
> [Amendment below](#adr-072-amendment--dependency-fully-removed-2026-08-07).

The Phase 1 spike added `pydantic-ai-harness==0.11.0` to `packages/core/pyproject.toml`.
Since no capability is adopted, this ADR requires it to move to an **optional/dev
dependency** so it remains available for spec-time evaluation without shipping to
production users:

```toml
# packages/core/pyproject.toml
[project.optional-dependencies]
# Available for spec-time Harness Build-vs-Buy evaluation (ADR-072).
# NOT installed by default. No production code may import pydantic_ai_harness.
harness-eval = ["pydantic-ai-harness==0.11.0"]
```

**Enforcement:** No production code may `import pydantic_ai_harness` or
`from pydantic_ai_harness` until a capability is adopted via its own ADR. Verified
baseline (Phase 2): 0 such imports exist in `packages/core/` source today. A future
adoption ADR lifts this constraint for the specific capability adopted.

### ADR-058 relationship (explicit)

- **ADR-058 is NOT superseded by this ADR.** ADR-058 remains `🔄 Proposed` and proceeds
  to Acceptance/implementation on its own merits.
- This ADR **confirms** ADR-058's rejection of Harness Compaction (Option D) — the
  pre-1.0 risk ADR-058 cited is unchanged in Harness 0.11.0.
- If ADR-058 is Accepted and implemented, it implements the In-House sliding window
  as-specified. ADR-072 does not modify ADR-058's contract, API, or implementation plan.
- The Compaction row in this ADR's Decision table is the cross-reference: any future
  re-evaluation of Compaction (per ADR-058's review triggers or this ADR's) updates both.

### Future spec obligations recorded (not discharged)

This ADR records the following obligations for future Architecture sessions. Each must
include a Harness Build-vs-Buy re-evaluation as a mandatory spec section:

| Feature | Capability to Re-Evaluate | Obligation |
|---------|--------------------------|------------|
| WRITE-008 (Multi-Draft Generation) | Step Persistence | ADOPT-vs-BUILD decision with full data-model context |
| GEN-002 (Research Assistant) | Exa Search | Provider-adapter design (Exa-principle) |
| PLAN-001 / PLAN-002 (Scene Planning, Gap Analysis) | Planning | Confirm BUILD (extend WritingGraph) — re-confirm Harness paradigm mismatch |
| WRITE-013 (Workflows) | Subagents | Determine delegation model (deterministic vs. model-driven) |
| CONS-002 (Custom Consistency Rules) or ANAL-006 (Sensitivity Review) | Guardrails | Specify `NarrareGuardrails` capability (InputGuard/OutputGuard Protocols) |
| ANAL-010 / ANAL-011 (Analysis Suite) | Compaction (re-eval), Overflowing Tool Output | Empirical evidence check; specify overflow strategy if triggered |

### Observability behaviour-change (carried from Phase 1, non-blocking)

`pydantic-ai-slim` 2.18 defaults `InstrumentationSettings` to `version=5` and
`use_aggregated_usage_attribute_names=True`. Narrare sets neither explicitly → OTel
Run-spans will report token usage under `gen_ai.aggregated_usage.*` instead of
`gen_ai.usage.*`. This is an observability-config concern, not a code break. If Logfire
dashboards/alerts read `gen_ai.usage.*` on Run-spans, either update the dashboards or
set `use_aggregated_usage_attribute_names=False` in `agents/instrumentation.py`. Out of
scope for this ADR — track separately.

---

## Review Trigger

This ADR is revisited when **any** of the following fires:

- [ ] **`pydantic-ai-harness` reaches 1.0** (stable API promise) → re-evaluate the
      entire strategy. At minimum, review every In-House solution built in the interim
      (Compaction, Guardrails, and any DEFER-turned-BUILD) for migration ROI. Note
      (amended 2026-08-07): the dependency was removed from the project; a future
      re-introduction — for evaluation or adoption — happens only **via its own
      adoption ADR**, never by re-adding the dependency on spec.
- [ ] **A concrete spec exists for WRITE-008, GEN-002, PLAN-001/002, WRITE-013,
      CONS-002, or ANAL-006** → the corresponding DEFER is lifted and that capability
      gets a focused Build-vs-Buy ADR.
- [ ] **Empirical evidence of an unmet need** →
  - First agent whose tool return exceeds 25% of the model context window (Overflowing
    Tool Output DEFER lifted).
  - Sessions >50 turns where pure sliding-window drops critical early context
    (Compaction re-evaluation per ADR-058).
- [ ] **A future feature explicitly requires model-writable memory** → Memory REJECT is
      revisited via its own ADR (not this one).
- [ ] **INFRA-006 (A2A) is specified** → evaluate actual A2A protocols. ACP REJECT stands
      unless the spec surprisingly reveals editor-to-agent semantics (unlikely).
- [ ] **Annual review (2026-07-25 + 1 year)** → re-evaluate the strategy against the
      then-current Harness version and Narrare feature landscape.

---

## RULE-XX Compliance

| Rule | Status | Nachweis |
|------|--------|----------|
| RULE-01b | ✅ | No new LLM imports. Harness capabilities (if ever adopted) attach inside `core/agents/` only — this ADR adopts none, so the constraint is trivially satisfied. `pydantic-ai-slim` 2.18 upgrade touches no LLM-import boundaries (spike: 0 import changes). |
| RULE-02 | ✅ | No prompt changes. Harness Guardrails adoption is DEFERRED/EXTEND-in-house — user-defined rules (CONS-002) stay in the prompt cascade when `NarrareGuardrails` is eventually specified. |
| RULE-03 | ✅ | No new contract introduced by this ADR. Future `NarrareGuardrails` (Guardrails EXTEND) and `RunPersistence` (Step Persistence DEFER) will define Protocols in their respective `contracts.py` before implementation — recorded as future spec obligations. |
| RULE-04 | ✅ | No file-size impact — this ADR is documentation only. Future In-House capabilities (`NarrareGuardrails` ~150 lines) will respect limits per their own specs. |
| RULE-05 | ✅ | No module-boundary changes. Harness (if adopted later) attaches in `core/agents/capabilities/`; Exa provider adapter would live in `core/research/` — both recorded as future obligations, not enacted here. |
| RULE-06 | ✅ | The Guardrails EXTEND decision *improves* RULE-06 compliance: consolidates 3 scattered validator files (`worldbuilding_validators.py`, `beta_reader_validators.py`, `draft_validators.py`) into one `NarrareGuardrails` capability when CONS-002/ANAL-006 begins. |
| RULE-07 | ✅ | No Core→apps/ or apps/→Core leaks. Harness capabilities (if adopted) are `AbstractCapability` subclasses restricted to `core/agents/`; they must not pull HTTP/DB concerns into Core — recorded as a constraint on any future adoption ADR. |
| RULE-08 | ✅ | External integrations stay abstracted. Exa (DEFER) will use a provider-adapter pattern (`ResearchProvider` Protocol) with a local DuckDuckGo fallback — local-first preserved. No adoption in this ADR means no new external dependency. |
| RULE-09 | ✅ | All future contracts (`NarrareGuardrails`, `RunPersistence`, `ResearchProvider`) will be fully typed Protocols — recorded as future spec obligations. |
| RULE-10 | ✅ | No implementation in this ADR → no tests required. Future In-House capabilities carry their own test plans per their specs. |
| RULE-11 | ✅ | No silent failures introduced. The Harness dependency move to optional is documented and enforced (no production imports). Future adoption ADRs must define error handling at boundaries (e.g., Exa provider-adapter fallback). |
| RULE-12 | ✅ | Service layer remains the sole public API. This ADR touches no client surface. |
| RULE-13 | ✅ | No streaming/non-streaming interface split. Harness Capabilities attach at the agent level (below the service boundary) — they do not affect the run/stream contract. |
| RULE-17 | ✅ | Local-first preserved. No cloud dependency adopted. Exa (the only paid/external candidate) is DEFERRED behind a provider adapter with a local fallback. |
| RULE-18b | ✅ | No governed defaults introduced. The Harness version pin (`0.11.0`) moves to optional — not a production default. |
| RULE-19 | ✅ | Documentation-driven: this ADR is the authoritative record. Future spec sessions reference it. |
| RULE-20 | ✅ | No partial implementations, no stubs, no TODOs. This ADR enacts documentation + dependency relocation only. |
| RULE-22 | ✅ | Cross-feature coherence preserved. The Memory REJECT explicitly protects RULE-22 (governed preference/artifact memory via ADR-066 + mem0, not an ungoverned model-writable notebook). |
| RULE-23 | ✅ | All 9 capability decisions are traceable to root cause, sustainability check, and trigger (Phase 2 evaluation `_phase2-capability-evaluation.md`). |

---

## Sustainability Check

1. **Correct in 3 months?** Yes. The strategy is "adopt nothing now, re-evaluate per
   spec." DEFER triggers fire when concrete specs emerge — by definition the right time.
   No speculative coupling to lock in.
2. **Hard-to-undo coupling?** None. Rejecting/deferring avoids coupling entirely. The
   `pydantic-ai-slim` 2.18 upgrade is within the V2 stability window (no lock-in). The
   Harness optional-dependency relocation is reversible — a future adoption ADR lifts it
   for a specific capability.
3. **Simplest correct solution?** Yes. Only what is needed today (version bump) is
   enacted; nothing premature is adopted. Each future decision is made with full spec
   context rather than speculation.
4. **Design intent clear?** Yes. "Harness is evaluated per-capability at spec-time;
   nothing is adopted on speculation; ADR-058's In-House precedent generalises to all
   9 capabilities until a spec proves a capability worth the 0.x cost."

---

## ADR Implementation Completeness Gate (Gate 12)

This ADR is primarily a strategy decision, not a code change. Its "implementation" is
the set of documentation + dependency-relocation actions below. Before marking this ADR
as "✅ Implemented":

- [ ] ADR-072 file created at `docs/architecture/decisions/ADR-072-pydantic-ai-harness-adoption-strategy.md`
- [ ] Entry added to `docs/architecture/decisions/INDEX.md`
- [ ] `pydantic-ai-slim` bumped to 2.18.0 in `packages/core/pyproject.toml` (Phase 4 — Platform Specialist)
- [ ] `pydantic-evals` bumped to 2.18.0 in `pyproject.toml` (root) (Phase 4 — Platform Specialist)
- [x] `pydantic-ai-harness` **fully removed** from `packages/core/pyproject.toml` **and** `uv.lock` (2026-08-07). Supersedes the original "relocate to `[project.optional-dependencies] harness-eval`" item: the optional-group target was implemented in commit `03f253e2` but never closed out, and is now obsolete — removal is the actual outcome. Dependabot PR #147 (Bump 0.11.0 → 0.14.0) closed as stale. See [Amendment below](#adr-072-amendment--dependency-fully-removed-2026-08-07)
- [ ] `uv lock` regenerates cleanly with the above
- [ ] `pyright --strict` passes (baseline: 0 errors per Phase 1 spike)
- [ ] `pytest tests/unit/` passes (baseline: 9630 passed per Phase 1 spike)
- [ ] No production source file imports `pydantic_ai_harness` (grep verification)
- [ ] ADR-058 status and content unchanged (this ADR confirms, does not supersede)

> **Note:** Items 3–9 (the version bump + dependency handling — originally
> "relocation", amended 2026-08-07 to **full removal**, see
> [Amendment below](#adr-072-amendment--dependency-fully-removed-2026-08-07)) are
> implementation work for the Platform Specialist, not part of this ADR's authoring.
> This ADR authorises those changes; it does not enact them.

---

## ADR-072 Amendment — Dependency Fully Removed (2026-08-07)

> **Amendment Date:** 2026-08-07
> **Amends:** Implementation Notes — Harness dependency handling; Gate 12 checklist item;
> Review Trigger — "`pydantic-ai-harness` reaches 1.0" (confirmed still valid)
> **Trigger:** Dependabot PR #147 (Bump `pydantic-ai-harness` 0.11.0 → 0.14.0) closed as
> stale; `pydantic-ai-harness` fully removed from `packages/core/pyproject.toml` + `uv.lock`

### Summary

**2026-08-07:** Abhängigkeit vollständig entfernt (`packages/core/pyproject.toml` +
`uv.lock`) — **0 Capabilities adoptiert** seit der Entscheidung; Dependabot-PR #147
(Bump 0.11.0 → 0.14.0) geschlossen als **stale**. Strategische Entscheidung
(Option C) **unverändert**.

### What happened

The original decision (2026-07-25) chose Option C: adopt zero Harness capabilities,
and relocate the spike-installed `pydantic-ai-harness==0.11.0` to an optional/dev
dependency (`harness-eval` group) so it would remain available for spec-time
evaluation. That relocation **was implemented** in commit `03f253e2` (the same
commit that created this ADR) — the `harness-eval` optional group existed in
`packages/core/pyproject.toml`. However, the ADR's implementation gate
(Gate 12) was **never formally closed** for the relocation item, and the optional
group was **never used** for any evaluation.

On **2026-08-07** the dependency was **fully removed** — from
`packages/core/pyproject.toml` **and** `uv.lock` (0 imports of `pydantic_ai_harness`
in the codebase). The `harness-eval` optional-group target state therefore **no
longer exists**; the current, authoritative state is **full removal**. The
relocation description in the Implementation Notes is preserved as history but is
superseded.

Dependabot PR #147, which proposed bumping `pydantic-ai-harness` 0.11.0 → 0.14.0,
was closed as **stale** after the removal — consistent with this ADR's position
that a 0.x/Alpha dependency has no place in Narrare absent an adopted capability.

### Why removal, not continued optional presence

- **0 capabilities adopted since the decision** — the optional group served no
  evaluation purpose in the intervening period.
- **0.x/Alpha lock-in avoidance** (Decision Driver) argues against even an optional
  dependency that is never used: it still appears in `uv.lock`, attracts Dependabot
  bump PRs, and creates surface area for accidental imports.
- **Re-evaluation discipline unchanged** — Harness capabilities are still evaluated
  per-capability at spec-time (WRITE-008 → Step Persistence, GEN-002 → Exa Search,
  etc.). A re-introduction happens **via its own adoption ADR** (see below), never
  by re-adding the dependency on spec.

### Effect on Review Trigger

The **"`pydantic-ai-harness` reaches 1.0"** review trigger **remains valid** and is
now clarified: a future re-introduction — whether for evaluation or adoption —
occurs **only via a dedicated adoption ADR**, with the full Build-vs-Buy rigour
this ADR established. The dependency itself is absent from the project until such
an ADR is accepted.

### Effect on Implementation Notes / Gate 12

- **Implementation Notes — "Harness dependency handling":** marked superseded
  (see note at the top of that section). The historical relocation description is
  preserved; the authoritative outcome is removal on 2026-08-07.
- **Gate 12 checklist:** the relocation item is replaced by the actual outcome
  (full removal, checked 2026-08-07). The remaining Gate-12 items (version bumps,
  `uv lock`, `pyright`, `pytest`, import-free verification, ADR-058 unchanged)
  are unaffected by this amendment.

### Constraint status (unchanged)

The constraint "Production `pyproject.toml` must NOT add `pydantic-ai-harness`
until a capability is adopted via its own ADR" remains in force — now trivially
satisfied, since the dependency is absent entirely. The related requirement that
every future Architecture session for WRITE-008, GEN-002, PLAN-001/002, WRITE-013,
CONS-002, or ANAL-006 includes a Harness Build-vs-Buy re-evaluation also stands.

---

## References

- **Phase 1 Spike Findings:** `feat/pydantic-ai-upgrade` branch,
  `_spike-pydantic-ai-upgrade-findings.md` (worktree `/tmp/opencode/narrare-spike-pydantic-ai`)
- **Phase 2 Capability Evaluation:** [`_phase2-capability-evaluation.md`](_phase2-capability-evaluation.md)
- **ADR-058:** ProcessHistory Sliding Window (confirmed, not superseded)
- **ADR-015:** pydantic-AI Agents as First-Class Citizens (RULE-01b foundation)
- **ADR-033:** mem0 2.0.x OSS Memory Architecture (Memory REJECT basis)
- **ADR-066:** Agent Context Store (Memory REJECT basis)
- **Harness METADATA:** `Development Status :: 3 - Alpha`, 0.x versioning policy
  (per-minor breaking changes allowed)
- **pydantic-ai changelog:** <https://ai.pydantic.dev/changelog/> (V2 stability window)
