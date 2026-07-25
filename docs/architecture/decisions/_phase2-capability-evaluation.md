# Phase 2: pydantic-ai-harness Capability Build-vs-Buy Evaluation

> **Status:** Evaluation (input for Phase 3 ADR)
> **Date:** 2026-07-25
> **Author:** Architecture Specialist
> **Input:** Spike findings (`_spike-pydantic-ai-upgrade-findings.md`), ADR-058 (Proposed),
> installed `pydantic-ai-harness==0.11.0` introspection, codebase graph analysis
> **Output for:** Phase 3 ADR on Harness adoption strategy

---

## Framework

Each capability is evaluated in this strict order (per architectural-discipline.md §1, §3, §5):

1. **FUNKTION** — Does a current or concretely-planned feature need this?
   (No concrete driver → REJECT, do not speculate.)
2. **BESTEHEND** — Can the existing implementation cover it (possibly after refactor)?
   (Yes → EXTEND, do not ADOPT.)
3. **HARNESS-VORTEIL** — Does Harness offer something we could not sensibly build ourselves?
   (No → BUILD in-house.)
4. **KOSTEN/RISIKO** — New dependency, lock-in, local-first breach, fallback story.
5. **ENTSCHEIDUNG** — ADOPT | EXTEND | BUILD | COMBINE | DEFER | REJECT
   Each decision carries a Root Cause and a Sustainability-Check (3-month question).

### Cross-cutting constraints applied to every decision

- **0.x versioning (HARNESS RISK).** Harness 0.11.0 is `Development Status :: 3 - Alpha`
  and uses **0.x versioning** — *minor releases may include breaking changes* (renames,
  defaults, restructured APIs); only patch releases are stable. Every ADOPT decision
  therefore imposes a per-minor-bump migration cost. This is the single most important
  sustainability factor and the reason ADR-058 Option D was rejected.
- **Local-first.** Capabilities requiring external paid services (Exa API, Modal cloud,
  hosted PostgresMemoryStore) breach local-first unless wrapped in a provider adapter
  with a local fallback (the "Exa-principle" generalised — see §Exa).
- **RULE-01b / RULE-07.** Harness capabilities are pydantic-ai `AbstractCapability`
  subclasses; they may only be attached inside `core/agents/` (RULE-01b). They must not
  pull HTTP/DB concerns into Core (RULE-07).
- **Creative-writing domain fit.** Harness is explicitly framed as "turn your agent into
  a coding agent, a research assistant, or anything else" (METADATA). Most capabilities
  (CodeMode, Filesystem, Shell, LocalStack, ModalSandbox, Macroscope, ACP) target coding
  agents and are out of scope for Narrare. Only the 9 capabilities evaluated below were
  deemed potentially relevant.

---

## ADR-058 Relationship

**This evaluation does not silently supersede ADR-058.** ADR-058 is `🔄 Proposed` and its
implementation gate is unchecked. ADR-058 already evaluated Harness (Option D) and
rejected it on pre-1.0 risk — that rejection is **still valid** because Harness is still
0.x/Alpha in 0.11.0.

For Compaction specifically, this evaluation **confirms ADR-058's In-House choice**
(see §Compaction). For the other 8 capabilities, ADR-058 sets no precedent — they receive
a normal Build-vs-Buy evaluation.

**No Production code may depend on ADR-058's contract until its implementation gate
passes** (architectural-discipline.md §7). Likewise, no Production code may depend on
any decision in this document until Phase 3 produces an `✅ Accepted` ADR.

---

## Reality-Check Findings (Premise Corrections)

The Coordinator's task brief contained two premise inaccuracies, verified against the
codebase (graph + grep) before continuing. These do not block the evaluation but shift
two decisions:

| # | Task premise | Verified reality | Impact |
|---|--------------|------------------|--------|
| 1 | "Exa Bestehend: `WebSearch` (DuckDuckGo)" | **No web search exists in Narrare.** Only `LLMIntent.RESEARCH` enum (planned). No `WebSearch` tool, no DuckDuckGo client, no `core/research/` module. | The relevant baseline for Exa is **pydantic-ai's native `WebSearch` capability** (provider-adaptive, local DuckDuckGo fallback), not a Narrare-built one. Changes Exa from "extend existing" to "defer until GEN-002 spec". |
| 2 | (Implicit) ADR-058 might be superseded by Harness Compaction | ADR-058 already rejected Harness (Option D) on pre-1.0 risk; that risk is unchanged in 0.11.0. | Compaction decision is **confirm ADR-058**, not "ADOPT Harness". |

All other premises (ADR-058 status, codebase state, roadmap features) were verified
accurate.

---

## Capability Decisions

### 1. Compaction — **EXTEND (confirm ADR-058)**

**Function need:** YES. Driven by ANAL-010 (Literary Analysis Suite), ANAL-011 (Plot
Analysis), and long Chat sessions (CHAT-001). ProcessHistory currently grows unbounded
(verified: `process_history.py` is 63 lines, `messages: list[Any]`, no trimming).

**Bestehend:** ADR-058 Proposed → `ProcessHistory` Sliding Window (~40 lines In-House,
token-aware, drops at message-pair boundaries, backward-compatible via `max_tokens=None`).
Verified `chat_service.py:237` calls `history.add(event.new_messages)` without
`input_tokens` — the ADR-058 wiring point is unchanged and ready.

**Harness advantage:** Harness Compaction offers *more modes* than ADR-058:
- `SlidingWindow` — equivalent to ADR-058's plan
- `SummarizingCompaction` — LLM-summarises dropped messages (ADR-058 explicitly excludes this)
- `LimitWarner` — warns the agent before hitting limits (ADR-058 explicitly defers this)
- `TieredCompaction`, `ClampOversizedMessages`, `ClearToolResults`, `DeduplicateFileReads`

**Kosten/Risiko:**
- 0.x lock-in for ~40 lines of logic we already have a Proposed ADR for.
- `SummarizingCompaction` changes conversation semantics (lossy LLM summary of dropped
  turns) — risky for creative-writing coherence where early character/setting details
  matter. A silent summary could drop a crucial foreshadowing beat.
- `LimitWarner` is genuinely useful but additive — can be built in-house in ~30 lines
  as a separate concern when needed.

**Root Cause:** Unbounded `ProcessHistory.messages` growth. The fix is token-aware
trimming. ADR-058 solves this directly in the owning class.

**Sustainability-Check:**
1. *Correct in 3 months?* Yes — ADR-058 is backward-compatible by default and uses
   data already flowing through `StreamEvent`.
2. *Hard-to-undo coupling?* None — `ProcessHistory` is a standalone dataclass with one
   consumer (`ChatService`).
3. *Simplest correct solution?* Yes — ~40 lines in the owning class vs. a 0.x dependency.
4. *Design intent clear?* Yes — "ProcessHistory manages its own memory budget".

**Decision: EXTEND (confirm ADR-058).** Implement ADR-058 as-specified. Do NOT adopt
Harness Compaction. ADOPT would supersede ADR-058 — rejected because (a) the pre-1.0
risk ADR-058 cited is unchanged, (b) `SummarizingCompaction`'s lossy semantics are
unsafe for creative-writing coherence without explicit user control, (c) the In-House
cost is trivially small (~40 lines).

**Review trigger for re-evaluation:**
- Empirical evidence (from ANAL-010/011 usage) that pure sliding-window drops critical
  early context in sessions >50 turns → then evaluate `SummarizingCompaction` (still
  likely in-house, ~80 lines, with explicit user opt-in).
- Harness reaches 1.0 → re-evaluate per ADR-058's existing review trigger.

**ADR-058-Bezug:** Confirms ADR-058. Does not supersede.

---

### 2. Step Persistence — **DEFER**

**Function need:** YES, concretely. WRITE-008 (Multi-Draft Generation) is `📋 planned`
and its semantic is `fork_run` (diverge a run into multiple branches). Session-resume
(`continue_run`) is also roadmap-relevant for long writing sessions.

**Bestehend:** Nothing. `ProcessHistory` is in-memory only; no run persistence layer.

**Harness advantage:** `StepPersistence` capability + `StepStore` Protocol with three
backends (`InMemoryStepStore`, `FileStepStore`, `SqliteStepStore`) + `continue_run` /
`fork_run` helpers + `is_provider_valid` guard. This is a non-trivial subsystem
(approx. 8 modules) with the exact semantics WRITE-008 needs.

**Kosten/Risiko:**
- 0.x lock-in — but for a genuinely complex subsystem we would otherwise build from
  scratch. Higher ROI than Compaction.
- `is_provider_valid` suggests provider-specific constraints (some providers may not
  support step replay) — needs investigation.
- Persistence backend choice (SQLite vs Postgres) intersects Narrare's existing DB
  layer (RULE-08: SQLite/SQLAlchemy only in `*/repository.py`). Harness `SqliteStepStore`
  would need an adapter or a RULE-08 exception.

**Root Cause:** WRITE-008 needs run-branching; no current persistence layer.

**Sustainability-Check:**
1. *Correct in 3 months?* Untestable until WRITE-008 spec exists.
2. *Hard-to-undo coupling?* Medium — once writes flow to a StepStore, migrating is non-
   trivial.
3. *Simplest correct solution?* Unknown — needs WRITE-008 spec to define the data model.
4. *Design intent clear?* Not yet — WRITE-008 has no spec.

**Decision: DEFER.** WRITE-008 is `📋 planned` without a spec. Adopting Harness
`StepPersistence` now would be premature coupling to a 0.x API for a feature whose
exact data model is undefined. When WRITE-008 reaches Architecture, evaluate:
- **Option A:** ADOPT Harness `StepPersistence` + `SqliteStepStore` behind a
  `RunRepository` adapter (RULE-08 compliance).
- **Option B:** BUILD in-house `RunPersistence` Protocol + SQLite repository.

**Trigger:** WRITE-008 Architecture session begins. This is the highest-value Harness
candidate — do not lose it.

---

### 3. Overflowing Tool Output — **DEFER**

**Function need:** PLANNED. ANAL-010 (Literary Analysis Suite) and KB agents may return
large payloads (entity graphs, full chapter analyses). Currently no agent returns
oversized tool output because we control all tool shapes — but ANAL-010 changes that.

**Bestehend:** Nothing. No tool-output-size management.

**Harness advantage:** `OverflowingToolOutput` capability with three `Band` actions
(`Truncate`, `Spill` to a queryable file via `OverflowStore`, `Summarize` via
configurable `SummarizeFunc`). Elegant band-based design — different size thresholds
trigger different actions. Includes `read_tool_result` tool so the model can pull back
spilled content on demand.

**Kosten/Risiko:**
- 0.x lock-in.
- `Spill` mode writes to `LocalFileStore` by default — file I/O in Core is a RULE-07
  concern (Core has no filesystem deps currently). Would need an adapter.
- `Summarize` mode runs an LLM call inside a tool-return path — cost/latency surprise
  if not bounded.

**Root Cause:** No current root cause — no agent overflows today. This is speculative
future-proofing.

**Sustainability-Check:**
1. *Correct in 3 months?* Untestable — no overflowing agent exists.
2. *Hard-to-undo coupling?* Low if deferred; medium if adopted (tool-return shape changes).
3. *Simplest correct solution?* Per-agent `max_result_tokens` truncation is simpler than
   the full band system, if truncation suffices.
4. *Design intent clear?* Not yet.

**Decision: DEFER.** No current driver. When ANAL-010 (or any agent) empirically
overflows context from tool output, evaluate:
- **Option A:** ADOPT Harness `OverflowingToolOutput` behind an adapter (with a
  Postgres-backed `OverflowStore` instead of `LocalFileStore`).
- **Option B:** BUILD in-house `ToolOutputBudget` with per-agent `default_strategy`
  (truncate | spill | summarize).

The Harness band-design is a good reference even if we BUILD.

**Trigger:** First agent whose tool return exceeds 25% of the model context window
(measured, not speculated).

---

### 4. Guardrails — **EXTEND (refactor existing validators)**

**Function need:** YES. CONS-002 (Custom Consistency Rules, `📋 planned`) and ANAL-006
(Sensitivity Review, `📋 planned`) both need pre/post-run validation with typed results.

**Bestehend:** Three validator files using pydantic-ai `ModelRetry`:
- `worldbuilding_validators.py` (106 lines) — Phase 1/2 output validation
- `beta_reader_validators.py` — output validation
- `draft_validators.py` — output validation
Verified: all use the `output_validator` pattern (post-run, raise `ModelRetry`).
**No input guards exist.**

**Harness advantage:** `InputGuard` (pre-run) + `OutputGuard` (post-run) with typed
`GuardResult`, `InputBlocked`/`OutputBlocked` exceptions. Clean separation of
"validate input" from "validate output", and a uniform result type that surfaces to
callers (vs. `ModelRetry` which retries silently).

**Kosten/Risiko:**
- The Harness Guardrails API is small (~4 classes, ~150 lines total). Easy to replicate.
- Adopting would mean our existing `ModelRetry`-based validators diverge from the
  Harness pattern, creating two validation paradigms.
- CONS-002 needs user-defined rules — these must integrate with our prompt cascade
  (RULE-02) and KB system, not with a generic guardrail registry.

**Root Cause:** Validation logic is scattered across three files with no shared
abstraction. CONS-002/ANAL-006 need both input and output guards with typed results.

**Sustainability-Check:**
1. *Correct in 3 months?* Yes — a `NarrareGuardrails` capability with `InputGuard`/
   `OutputGuard` Protocols is stable and domain-owned.
2. *Hard-to-undo coupling?* Low — Protocol-based, replaces scattered validators.
3. *Simplest correct solution?* Yes — ~150 lines in-house, exactly fits our domain.
4. *Design intent clear?* Yes — "all validation goes through NarrareGuardrails".

**Decision: EXTEND.** Refactor the three existing validators into a
`NarrareGuardrails` capability in `core/agents/capabilities/` with `InputGuard` and
`OutputGuard` Protocols (mirroring Harness's API shape, but in-house). This:
- Consolidates the three scattered validator files (RULE-06 win).
- Adds `InputGuard` capability we don't have yet.
- Keeps user-defined rules (CONS-002) in our prompt cascade, not a generic registry.
- Avoids 0.x lock-in for ~150 lines of logic.

**Trigger:** CONS-002 or ANAL-006 Architecture session. The `NarrareGuardrails`
capability should be specified as part of whichever comes first.

---

### 5. Planning — **BUILD (extend WritingGraph)**

**Function need:** YES. PLAN-001 (Scene Planning), PLAN-002 (Gap Analysis), WRITE-013
(Workflows) — all `📋 planned`.

**Bestehend:** `WritingGraph` (`packages/core/narrare_core/agents/writing_graph.py`,
287 lines) — a **deterministic** pydantic-graph state machine:
`plan_outline → write_draft → review_draft → (revise_draft | finalize) → generate_summary`.
Each step is a fixed function; edges are static.

**Harness advantage:** `Planning` capability + `PlanningToolset` — **model-driven**
planning. The model writes `PlanItem` objects (with `TaskStatus`: pending/in_progress/
completed) via a tool, then executes them. Cache-friendly (plan is a tool-call, not
a system-prompt bloat).

**Kosten/Risiko:**
- **Paradigm mismatch.** Harness Planning is *model-driven* (the model decides the
  plan). Narrare's WritingGraph is *deterministic* (we encode the workflow). For
  creative writing, deterministic orchestration is safer — we don't want the model
  deciding to skip the review step or invent a new workflow branch.
- `PlanItem`/`TaskStatus` is a generic todo model. Narrative structure (scenes, beats,
  gaps, character arcs) is domain-specific and already has typed schemas
  (`OutlineAgent`, `Storyboard`, etc.).
- PLAN-001/PLAN-002 need *structured domain planning*, not generic task lists.

**Root Cause:** PLAN-001/PLAN-002 need structured narrative planning. The plan
structure is domain-specific (scenes, gaps), not generic tasks.

**Sustainability-Check:**
1. *Correct in 3 months?* Yes — domain-specific planning nodes in WritingGraph match
   the narrative model.
2. *Hard-to-undo coupling?* Low — extends existing WritingGraph pattern.
3. *Simplest correct solution?* Yes — reuse pydantic-graph (already adopted) with new
   domain step nodes.
4. *Design intent clear?* Yes — "WritingGraph encodes narrative workflows".

**Decision: BUILD.** Extend `WritingGraph` with domain-specific planning nodes
(`scene_planning`, `gap_analysis`) using the existing pydantic-graph pattern. Do NOT
adopt Harness `Planning` — the generic task-list model does not match narrative
structure, and model-driven planning is unsafe for deterministic writing workflows.

**Trigger:** PLAN-001 or PLAN-002 Architecture session.

---

### 6. Subagents — **DEFER**

**Function need:** POSSIBLE. WRITE-013 (Workflows, `📋 planned`) *might* need dynamic
delegation. Currently no feature requires it.

**Bestehend:** `WritingGraph` orchestrates multiple agents deterministically
(`OutlineAgent`, `DraftAgent`, `ReviewAgent`, `ChapterSummaryAgent`). Verified: this is
fixed-step delegation, not model-driven.

**Harness advantage:**
- `SubAgents` capability + `SubAgentToolset` — model delegates to named child agents.
- `DynamicWorkflow` (separate capability) — model writes a Python script that fans out
  to sub-agents in a single tool call (massive round-trip savings).
- `clamp_effort` / `MINIMUM_EFFORT_FLOOR` — budget control on sub-agent runs.

**Kosten/Risiko:**
- **Determinism risk.** Model-driven delegation means the model decides which subagent
  to call and when. For creative writing, we want review steps to *always* run, not
  be subject to model judgement.
- `DynamicWorkflow` is explicitly "API subject to change while planned extensions
  settle" (METADATA) — extra instability on top of 0.x.
- WRITE-013 has no spec — we don't know if it needs dynamic delegation.

**Root Cause:** No current root cause — `WritingGraph` handles current orchestration.

**Sustainability-Check:**
1. *Correct in 3 months?* Untestable — WRITE-013 has no spec.
2. *Hard-to-undo coupling?* High — once model-driven delegation is in prompts, removing
   it changes agent behaviour.
3. *Simplest correct solution?* WritingGraph (existing) is simpler for deterministic flows.
4. *Design intent clear?* Not yet.

**Decision: DEFER.** WritingGraph handles all current orchestration needs
deterministically. Re-evaluate only if WRITE-013 spec explicitly requires *dynamic,
model-driven* delegation (not just multi-step orchestration, which WritingGraph already
does). If WRITE-013 only needs new graph nodes, BUILD them; if it needs the model to
choose delegations at runtime, evaluate Harness `SubAgents`.

**Trigger:** WRITE-013 Architecture session defines delegation model.

---

### 7. Exa Search — **DEFER (with Reality-Check flag)**

> **⚠️ REALITY-CHECK:** The task brief stated "Bestehend: `WebSearch` (DuckDuckGo)".
> **This is incorrect.** Verified via graph + grep: there is NO `WebSearch` tool, no
> DuckDuckGo client, no `core/research/` module in Narrare. Only `LLMIntent.RESEARCH`
> exists as a planned enum. GEN-002 (Research Assistant) is `📋 planned`, no
> implementation. The relevant baseline for Exa is therefore **pydantic-ai's native
> `WebSearch` capability** (provider-adaptive, local DuckDuckGo fallback), which Narrare
> has not yet adopted either.

**Function need:** YES. GEN-002 (Research Assistant) — fact verification, citations,
confidence scoring. `📋 planned`, no spec.

**Bestehend:** Nothing in Narrare. pydantic-ai (not Harness) ships a native `WebSearch`
capability that is provider-adaptive and falls back to local DuckDuckGo. This is the
true baseline.

**Harness advantage:** `ExaSearch` + `ExaAgent` + `ExaSearchToolset` — web search
returning page excerpts, full single-page retrieval, and opt-in deep search with cited
answers via the [Exa](https://exa.ai) API. Also `ExaAgent` for delegating open-ended
research to Exa's hosted Agent API.

**Kosten/RISIKO (high):**
- **Paid external dependency.** Exa requires an API key + paid account. Violates
  local-first unless wrapped in a provider adapter with a local fallback.
- **Extra dependency.** Requires `pydantic-ai-harness[exa]` → adds `exa-py>=2.16.0`.
- **Lock-in.** Exa's API is proprietary; different from generic web search.

**Root Cause:** No current root cause — no web search exists. GEN-002 is the driver.

**Sustainability-Check:**
1. *Correct in 3 months?* Untestable — GEN-002 has no spec.
2. *Hard-to-undo coupling?* High if Exa is hardcoded; low if behind an adapter.
3. *Simplest correct solution?* Adapter pattern (Exa-principle) — see below.
4. *Design intent clear?* Not yet.

**Decision: DEFER.** When GEN-002 is specified, build a **provider-adapter pattern**
analogous to `ModelRegistry`:

```python
# core/research/contracts.py
class ResearchProvider(Protocol):
    async def search(self, query: str, *, max_results: int) -> list[SearchResult]: ...
    async def verify(self, claim: str) -> VerificationResult: ...

# core/research/_providers/exa.py    — requires exa-py + API key
# core/research/_providers/duckduckgo.py — local-first fallback (pydantic-ai native)
# core/research/_providers/registry.py — selects based on user config
```

This is the **Exa-principle generalised**: every paid/external capability needs a local
fallback. Evaluate at GEN-002 time:
- **Option A:** ADOPT Harness `ExaSearch` as the `ExaProvider` behind the adapter, with
  pydantic-ai native `WebSearch` (DuckDuckGo) as `DuckDuckGoProvider` fallback.
- **Option B:** BUILD both providers in-house (skip Harness Exa).

Default selection: DuckDuckGo (local-first). User opts into Exa via settings.

**Trigger:** GEN-002 Architecture session.
**Flag to Coordinator:** Task premise "Bestehend: WebSearch (DuckDuckGo)" was incorrect;
the evaluation proceeds against the true baseline (pydantic-ai native `WebSearch`).

---

### 8. Memory — **REJECT (different concern; mem0 + ADR-066 cover Narrare's needs)**

**Function need:** YES, but for a *different* concern than Harness Memory addresses.
ANAL-007 (Author Voice Profiling), ANAL-009 (Voice Drift Detection), ASSIST-001 (Plot
Consistency Check) need persistent cross-run context.

**Bestehend:**
- **mem0** (`packages/core/narrare_core/memory/`) — long-term user *preferences*
  (`PreferenceProvider`, `FeedbackCollector`, `SessionMemoryCollector`,
  `ConsistencyFeedbackCollector` protocols in `memory/protocols.py`). This is
  Narrare-controlled, best-effort, structurally-typed (never raw draft prose).
- **ADR-066 AgentContextStore** (`✅ Accepted`, implementation deferred) — session-scoped,
  typed, best-effort artifact sharing across invocations. This is the architectural seam
  for agent working memory.

**Harness advantage:** `Memory` capability + `MemoryToolset` — a *model-writable*
persistent notebook. The model gets `write`/`search`/`delete` tools; content persists
per agent name; stores include `FileStore`, `SqliteMemoryStore`, `PostgresMemoryStore`.

**Why this is the WRONG abstraction for Narrare:**
- **Unpredictable side-effects.** Giving the creative-writing model direct write access
  to a persistent notebook means it decides what to "remember". For user preferences,
  Narrare uses *explicit feedback signals* (thumbs up/down, accept/reject) processed
  through `PreferenceAnalysisAgent` — controlled, auditable, RULE-22-compliant. A
  model-writable notebook bypasses this discipline.
- **Privacy.** Narrare's mem0 layer records *structural metadata only* (never raw draft
  prose — see `ConsistencyFeedbackCollector` docstring). A model-writable notebook has
  no such guarantee — the model could persist anything.
- **Different scope.** Harness Memory is per-run/per-agent working memory. Narrare's
  needs are (a) cross-session user preferences (mem0) and (b) cross-invocation
  artifact sharing within a session (ADR-066 AgentContextStore). Both are already
  architected.

**Root Cause:** ANAL-007/009/ASSIST-001 need cross-run context. The architectural seam
for this is ADR-066 AgentContextStore (typed, governed) + mem0 (preferences), not a
model-writable notebook.

**Sustainability-Check:**
1. *Correct in 3 months?* Yes — ADR-066 + mem0 cover the needs without a new abstraction.
2. *Hard-to-undo coupling?* Rejecting avoids coupling entirely.
3. *Simplest correct solution?* Yes — reuse existing architectural seams.
4. *Design intent clear?* Yes — "agents don't write persistent state directly".

**Decision: REJECT.** Harness Memory solves a different problem (model-writable scratchpad)
than Narrare has (governed preference and artifact memory). ADR-066 AgentContextStore +
mem0 are the correct seams. Adopting Harness Memory would introduce an ungoverned,
model-controlled persistence path that violates RULE-22 (cross-feature coherence) and
Narrare's privacy discipline.

**Trigger:** None. This is an architectural decision, not a deferral.

---

### 9. ACP — **REJECT (wrong protocol)**

**Function need:** YES for A2A (INFRA-006, `📋 planned`; ADAPTER-002, `💡 idea`). But
ACP is the wrong protocol for Narrare's A2A requirements.

**Bestehend:** Nothing.

**Harness advantage:** `experimental/acp/` — serves a pydantic-ai Agent over the
[Agent Client Protocol](https://agentclientprotocol.com) via stdio JSON-RPC. Adapts
agents to editors like Zed and Toad: streamed text, diff-rendered edits, tool approval.

**Why this is the WRONG protocol:**
- **Target audience mismatch.** ACP is for *coding agents* driven by *coding editors*
  (Zed, Toad). Narrare is a creative-writing tool with its own WebUI; it has no
  integration target for ACP.
- **Protocol semantics mismatch.** ACP's primitives (diff-rendered edits, filesystem
  tools, terminal toolsets) are coding-agent concepts. Narrare's A2A needs are
  service-to-service (one Narrare instance talking to another, or to a remote agent
  service), not editor-to-agent.
- **Experimental status.** `experimental/acp/` emits `HarnessExperimentalWarning` and
  "may change or be removed in any release, without a deprecation period" (per its
  `__init__.py`). Adopting experimental APIs in production is forbidden by
  architectural-discipline.md §7 ("🔄 Proposed is not a contract you may depend on" —
  and experimental is even less stable than Proposed).

**Root Cause:** INFRA-006 A2A needs service-to-agent communication. ACP provides
editor-to-coding-agent communication. These are different problems.

**Sustainability-Check:**
1. *Correct in 3 months?* No — ACP does not solve Narrare's A2A problem.
2. *Hard-to-undo coupling?* Rejecting avoids coupling entirely.
3. *Simplest correct solution?* Yes — wait for INFRA-006 spec, evaluate actual A2A
   protocols (not ACP).
4. *Design intent clear?* Yes — "ACP is for editors, not for service-to-service A2A".

**Decision: REJECT.** ACP does not match Narrare's A2A requirements. It targets a
different domain (coding editors) with different semantics (diff/tool-approval) and
carries experimental-status risk. When INFRA-006 is specified, evaluate actual A2A
protocols (e.g., A2A protocol spec, MCP, or a Narrare-defined RPC).

**Trigger:** None. Protocol mismatch is an architectural fact, not a timing question.

---

## Summary: Capability Strategy

| # | Capability | Decision | Priority | ADR-058-Bezug | Dependencies / Trigger |
|---|-----------|----------|----------|---------------|------------------------|
| 1 | Compaction | **EXTEND** | High | Confirms ADR-058 | Implement ADR-058 as-is |
| 2 | Step Persistence | **DEFER** | Medium | N/A | WRITE-008 Architecture session |
| 3 | Overflowing Tool Output | **DEFER** | Low | N/A | First agent overflow (empirical) |
| 4 | Guardrails | **EXTEND** | Medium | N/A | CONS-002 or ANAL-006 session |
| 5 | Planning | **BUILD** | Medium | N/A | PLAN-001 / PLAN-002 session |
| 6 | Subagents | **DEFER** | Low | N/A | WRITE-013 spec defines delegation |
| 7 | Exa Search | **DEFER** | Medium | N/A | GEN-002 session (premise corrected) |
| 8 | Memory | **REJECT** | — | N/A | None (architectural) |
| 9 | ACP | **REJECT** | — | N/A | None (protocol mismatch) |

**Decision distribution:**
- **EXTEND (2):** Compaction, Guardrails — leverage existing code, no new dependency.
- **DEFER (4):** Step Persistence, Overflowing Tool Output, Subagents, Exa — wait for
  concrete specs, avoid premature 0.x coupling.
- **BUILD (1):** Planning — domain-specific, Harness too generic.
- **REJECT (2):** Memory, ACP — wrong abstraction / wrong protocol.

**Net Harness adoption: ZERO capabilities adopted at this time.**

This is not a verdict against Harness — it is a consequence of:
1. Harness 0.x/Alpha versioning (per-minor-bump migration cost).
2. Narrare's strict architectural discipline (RULE-03, RULE-07, local-first, sustainability).
3. The creative-writing domain (most Harness capabilities target coding agents).
4. Most relevant features are `📋 planned` without specs — adopting now is premature.

The highest-value Harness candidates to revisit at spec-time are:
1. **Step Persistence** (for WRITE-008 `fork_run`) — non-trivial subsystem, real ROI.
2. **Exa Search** (for GEN-002) — behind a provider adapter with DuckDuckGo fallback.

---

## Recommendations for Phase 3 (ADR)

The Phase 3 ADR should be structured as a **Harness Adoption Strategy** ADR, not a
single-capability ADR. Recommended scope:

### ADR-072 (suggested): pydantic-ai-harness Adoption Strategy

**Decision:** Do not adopt any Harness capability at this time. Adopt a "spec-triggered
re-evaluation" policy: each planned feature's Architecture session re-evaluates the
relevant Harness capability against the Build-vs-Buy framework.

**Rationale:**
- Harness 0.x/Alpha → adoption imposes per-minor-bump migration cost.
- No current unmet need justifies a 0.x dependency.
- Most relevant features (`📋 planned`) lack specs → premature to adopt now.
- Two capabilities (Memory, ACP) are architectural rejects, not timing questions.

**Consequences:**
- ADR-058 proceeds to implementation unchanged.
- A `NarrareGuardrails` capability is specified when CONS-002 or ANAL-006 begins.
- WRITE-008, GEN-002, WRITE-013 Architecture sessions each include a Harness
  Build-vs-Buy re-evaluation as a mandatory spec section.
- Harness stays as a `dev`/optional dependency (already installed in spike worktree);
  production `pyproject.toml` does not add it until a capability is adopted.

**Review triggers (cumulative):**
- Harness reaches 1.0 → re-evaluate all DEFER/REJECT-by-version decisions.
- Any DEFER's trigger fires → that capability gets a focused ADR.
- Annual review (2026-07-25 + 1 year) → re-evaluate the strategy.

### Alternative: per-capability ADRs

If the Coordinator prefers granularity, the Phase 3 ADR can be split:
- **ADR-072a:** Compaction — confirms ADR-058 (1 paragraph, references this eval).
- **ADR-072b:** Guardrails — specifies `NarrareGuardrails` capability.
- **ADR-072c–f:** DEFER records (one paragraph each, with triggers).
- **ADR-072g–h:** REJECT records (Memory, ACP — one paragraph each).

**Recommendation:** Single strategy ADR (ADR-072). Splitting adds ceremony without value
when the net decision is "adopt nothing now, re-evaluate per-spec".

---

## Open Questions for Coordinator

1. **Premise correction acknowledgement.** The task brief's "Bestehend: WebSearch
   (DuckDuckGo)" was incorrect (verified). Does the Coordinator want this flagged
   upstream to prevent recurrence, or is an in-document note (§Reality-Check) sufficient?

2. **Harness as dev/optional dependency.** The spike added `pydantic-ai-harness==0.11.0`
   to `packages/core/pyproject.toml`. Since no capability is adopted, should it:
   - (a) Stay as a production dependency (available for experimentation)?
   - (b) Move to `[dev]` / optional dependency (not installed by default)?
   - (c) Be removed entirely until a capability is adopted?
   **Recommendation: (b)** — keeps it available for spec-time evaluation without
   shipping it to production users.

3. **ADR-058 implementation timing.** This evaluation confirms ADR-058 but does not
   trigger its implementation. Should the Coordinator schedule ADR-058 implementation
   now (it unblocks long-session quality for CHAT-001), or wait for the Phase 3 ADR?

---

## Verification Evidence

| Claim | Verification |
|-------|-------------|
| ADR-058 is `🔄 Proposed`, not Implemented | `docs/architecture/decisions/INDEX.md:83` + ADR-058 Gate 12 unchecked |
| `ProcessHistory` has no sliding window | `packages/core/narrare_core/agents/process_history.py` (63 lines, `messages: list[Any]`, no `max_tokens`) |
| `chat_service.py` does not wire `input_tokens` | `apps/api/narrare/chat/chat_service.py:237` calls `history.add(event.new_messages)` without `input_tokens` |
| No `WebSearch` / DuckDuckGo in Narrare | graph + grep: 0 matches in `packages/core/` for WebSearch/duckduckgo (only skill references) |
| GEN-002 is `📋 planned`, no implementation | `docs/features/INDEX.md:178` + `docs/features/generation/GEN-002-research.md` (status: planned) |
| `pydantic-ai-harness` not imported anywhere | grep: 0 matches for `from pydantic_ai_harness` / `import pydantic_ai_harness` in source |
| Harness 0.11.0 is Alpha, 0.x versioning | `pydantic_ai_harness-0.11.0.dist-info/METADATA`: `Development Status :: 3 - Alpha` + §Version policy |
| Harness capability API surface | Introspected `pydantic_ai_harness/{cap}/__init__.py` for all 9 capabilities |
| WritingGraph is deterministic | `packages/core/narrare_core/agents/writing_graph.py` uses `pydantic_graph.GraphBuilder` with fixed `@g.step` nodes |
| Existing validators use `ModelRetry` | `worldbuilding_validators.py` (106 lines), verified pattern |
| mem0 protocols exist | `packages/core/narrare_core/memory/protocols.py` (185 lines, 5 Protocols) |
| ADR-066 AgentContextStore accepted | `docs/architecture/decisions/INDEX.md:91` (✅, implementation deferred) |

---

*End of Phase 2 Evaluation.*
