# ADR-066 — Session-Scoped Agent Context Store for Cross-Invocation Artifact Sharing

> **Status:** ✅ Accepted
> **Date:** 2026-07-10
> **Deciders:** Architecture Specialist (review-03 architecture remediation)
> **Supersedes:** —
> **Finding:** review-03 §3 / `[AUFG-03-06]` — Cross-Agent-Kontext-Teilung für
> aufeinanderfolgende Werkzeug-Aufrufe
> **Related:** ADR-033 (mem0 preferences), ADR-034 (Conversational History Policy),
> ADR-038 (AI Invocation Adoption Contract), ADR-040 (KG/Voice SSOT),
> ADR-044 (Staged Consistency), ADR-048 (Non-Writing Invocation Adapter),
> ADR-050 (Cross-Feature Context Contracts), CONSTRAINTS.md RULE-03/RULE-06/RULE-11/RULE-22

---

## Context

### The finding

review-03 §3 observes that **context sharing between agents currently works only
within a single `WritingGraph` run or within a single chat `Session`**. If an
author wants to feed a Consistency-Check result into the next Co-Author run, or
chain *Consistency-Finding → Co-Author-Fix → Re-Check*, they must mediate
manually by copying outputs between tools. There is no "shared agent memory"
beyond mem0 user preferences (ADR-033). This limits workflow composition across
separate tool invocations.

### Root cause (verified against the code, graph-first where available)

1. **Symptom:** The structured *output* of one independently-invoked agent (e.g.
   a consistency issue list, a beta-read critique) is not carried forward as
   typed context into a subsequent, separately-invoked agent.
2. **Why?** Each agent invocation builds its own `PromptInvocationContext`
   (`ai_invocation/models.py:127`) from scratch — KB + chapters + preferences.
   The `InvocationPipeline` is **explicitly stateless and safe for concurrent
   use** (`ai_invocation/pipeline.py:15`); it holds no memory between calls.
3. **Why is there no cross-invocation carry-forward?** The existing carry
   mechanisms are each scoped to a single run/session and to the wrong data
   type:
   - `WritingGraph` threads a mutable `WritingState` *between graph steps*
     (`agents/writing_graph.py:113`–`285`) — but the state dies with the graph
     run and never reaches a separately-invoked agent.
   - `ProcessHistory` (`agents/process_history.py`) is an in-memory **opaque
     pydantic-ai message list**, gated to **conversational agents only** by
     `HistoryPolicy` (ADR-034). Task agents (consistency, beta-read, extraction)
     are **explicitly forbidden** ProcessHistory, and it is not persisted across
     independent tool invocations.
   - mem0 (ADR-033) is scoped to **user preferences**, not analysis artifacts.
4. **Why hasn't the enricher seam solved it already?** The invocation pipeline
   already has the right seam — `ContextEnricher` implementations inject
   `dynamic_inputs` into `PromptInvocationContext` (`pipeline.py:250`–`289`),
   and there is even a `KBConsistencyEnricher` (`enrichers/consistency.py`). But
   every enricher **pulls fresh from an authoritative data store** (mem0, KB);
   **none reads the structured output of a prior agent run**. Crucially,
   `KBConsistencyEnricher` runs a **live** KB structural-consistency check on
   each invocation and emits only a **status flag** (`consistent`/`inconsistent`
   + summary counts) — it does **not** surface the *issue substance* (the typed
   contradiction list a Co-Author fix run would actually need).
5. **Why does that matter?** Because there is no typed producer→consumer seam for
   *agent analysis artifacts*, the only path today is the author copy-pasting
   between tools — i.e. the user is the integration contract, which is
   unobservable, unversioned, and unverifiable.

**Conclusion: the gap is real and confirmed.** There is no store that captures a
structured agent output and re-injects it as context into a later, independent
invocation within the same novel/session scope.

---

## Decision Drivers

- **Workflow composition is a stated product direction.** Chaining
  *Consistency → Co-Author-Fix → Re-Check* and *Beta-Read → Revise* requires
  artifact carry-forward across separate tool calls.
- **Reuse the established seam.** `ContextEnricher` + `dynamic_inputs` is the
  canonical, already-tested injection path (ADR-038). A new carry-forward
  mechanism that bypasses it would duplicate governance, evidence, and budget
  wiring.
- **RULE-22 (cross-feature coherence).** Any producer→consumer agent boundary
  must identify the shared data, define change/supersede behaviour, and register
  the consumed prompt variable.
- **RULE-11 (no silent failures).** A new store must not become a hard
  single-point-of-failure; degradation must be observable.
- **ADR-034 boundary.** Task agents are forbidden `ProcessHistory`. The
  carry-forward mechanism must respect the task/conversational split — it is an
  *artifact* channel, not a *message* channel, and must not smuggle
  conversational state into task agents.
- **ADR-033 scope.** mem0 is for preferences. Analysis artifacts are a different
  concern and must not pollute the preference namespace.
- **Sustainability.** The mechanism must hold when WRITE-/CONS-/ANAL- features
  add more chained workflows, without per-workflow special-casing.

---

## Options Considered

### Option A — Session/novel-scoped Agent Context Store + `ContextEnricher` consumer  ✅ CHOSEN

Introduce a typed, best-effort `AgentContextStore` (Protocol, optional DI) keyed
by `(project_id/novel_id, optional session_id, artifact_kind)`. Producing agent
services (e.g. `ConsistencyOrchestrator`, a Beta-Read service) **publish** a
typed `AgentArtifact` after a run. A new `AgentArtifactEnricher` (implements the
existing `ContextEnricher`) reads the latest relevant artifacts for the
invocation's scope and injects them into `dynamic_inputs` — exactly as
`KBConsistencyEnricher` does today.

**Pros:**
- Reuses the existing `ContextEnricher` + `dynamic_inputs` seam — no new
  invocation mechanism, no bypass of evidence/budget/governance wiring.
- Typed artifacts (not opaque messages) → RULE-09 compliant, auditable.
- One-directional producer→store→consumer contract → RULE-22 natural fit.
- Graceful degradation is already the established pattern
  (`KBConsistencyEnricher` returns `not_applicable` when its check is `None`).
- Respects ADR-034: an *artifact* channel is distinct from a *message* channel;
  task agents receive artifacts as prompt context, not as ProcessHistory.
- Composable: every future chained workflow publishes/consumes the same way.

**Cons:**
- New store + lifecycle policy (supersession/TTL) to define and enforce.
- New Protocol + a prompt variable to register (RULE-22 §4, ADR-050 P1-D lesson).
- Must be carefully bounded against `KBConsistencyEnricher` to avoid
  double-storing what is already computed live (see *Boundary* below).

### Option B — Status quo: document user-driven manual handoff as a deliberate non-decision

Record that authors mediate by copying tool outputs between invocations, and
take no architectural action.

**Pros:**
- Zero new surface, zero implementation.

**Cons:**
- Does not address the root cause: the absence of a typed artifact seam. It
  treats the symptom ("the user can copy-paste") rather than the cause ("there
  is no machine-readable producer→consumer contract").
- Leaves workflow composition brittle and unobservable — the user is the
  integration contract. This is the exact anti-pattern RULE-22 exists to
  prevent.
- review-03 raised this precisely *because* the status quo limits composition.

### Option C — Reuse/extend mem0 or ProcessHistory to carry analysis artifacts

**C1 — mem0:** store consistency issues / critiques inside mem0.
- **Rejected:** mem0 is scoped to *user preferences* (ADR-033). Stuffing
  analysis artifacts into mem0 pollutes the preference namespace, loses type
  safety (mem0 is free-form untyped memory), and conflates "what the user likes"
  with "what the analysis found" — a RULE-22 §1 (shared-data identification)
  violation.

**C2 — ProcessHistory:** extend it to carry structured artifacts.
- **Rejected on three independent grounds:** (1) ProcessHistory holds **opaque
  pydantic-ai messages**, forcing a message-format encoding of structured data
  (a RULE-09 type-safety loss). (2) ADR-034 **forbids ProcessHistory for task
  agents** — precisely the agents that *produce* (consistency, beta-read) and
  *consume* (co-author fix) artifacts. Repurposing it breaks the
  task/conversational boundary. (3) ProcessHistory is an **in-memory per-session**
  object, not persisted across independent tool invocations — so it cannot bridge
  two separate tool calls in the first place.

**Cons (both variants):** wrong scope (C1), wrong type + wrong policy + wrong
lifetime (C2). Reuse here is forced-fit, not genuine reuse.

---

## Decision

**We choose Option A: a session/novel-scoped `AgentContextStore` consumed by a
new `AgentArtifactEnricher` through the existing invocation pipeline.**

Producing agent services publish typed `AgentArtifact`s to the store after a
run; the enricher reads the latest artifact(s) for the invocation scope and
injects them into `PromptInvocationContext.dynamic_inputs`, where prompt
templates consume them as registered variables. The store is **optional DI** —
when absent or empty, the enricher is a no-op and the agent runs without
carry-forward context (degraded quality, never a crash).

**Implementation is deferred to a follow-up.** This ADR is the *decision*: it
fixes the architectural seam, the RULE-22 integration-contract shape, the
prompt-variable registration requirement, and the graceful-degradation
contract. No production code, tests, or `contracts.py` files ship with this
ADR (RULE-03: the contract is *defined here*; implementation is a separate
task).

### Boundary vs. the existing `KBConsistencyEnricher` (no double-storage)

`KBConsistencyEnricher` keeps doing what it does: a **live** KB *structural*
consistency status (entity-type coverage, orphan refs, stale profiles) emitted
as a flag. The Agent Context Store carries a **different, richer** payload —
the *analysis substance* (the typed contradiction/issue list from
`ConsistencyOrchestrator.run_staged_check`, beta-read critique points,
fact-extractor findings) that a subsequent fix run actually needs. The two are
complementary: one is a live *status*, the other is a carried *substance*. The
ADR explicitly forbids the store from re-deriving or duplicating the live
structural status (RULE-22 §1: each shared datum has exactly one identified
producer).

---

## Rationale

The *purpose* of this decision is to give chained workflows a **typed,
observable, optional** artifact channel — not to add a new memory system. The
codebase already has the ideal seam: `ContextEnricher` → `dynamic_inputs`, with
`KBConsistencyEnricher` as a working precedent for both injection and graceful
degradation. Routing cross-invocation artifacts through that seam means they
inherit evidence recording (ADR-045), budget awareness, variable validation,
and prompt-surface governance (ADR-037/ADR-050) **for free** — instead of a
parallel mechanism that would have to re-establish all of that.

Option B is rejected because documenting a non-decision does not remove the
root cause; it merely makes the user responsible for a contract that ought to
be machine-enforceable. Option C is rejected because mem0 and ProcessHistory
are each scoped to the wrong concern (preferences / conversational messages)
and would be forced into a role their governing ADRs (033, 034) either do not
cover or explicitly forbid.

**Tradeoff accepted:** a new store with a lifecycle policy. We accept this
because the alternative (no carry-forward, or carry-forward through the wrong
mechanism) is worse on every axis the decision drivers name. The store is
bounded by supersession (a new artifact of the same `(scope, kind)` replaces
the prior) so it does **not** grow unbounded — the hard-delete lesson from
ADR-050 is honoured.

---

## Consequences

**Positive:**
- Chained workflows (Consistency → Fix → Re-Check, Beta-Read → Revise) gain a
  typed carry-forward path with no manual mediation.
- Artifacts inherit the full invocation governance (evidence, budget,
  validation, prompt-surface registration).
- The task/conversational boundary (ADR-034) is preserved: artifacts are a
  distinct channel from messages.
- Every future chained workflow reuses one contract — no per-workflow
  special-casing.

**Negative / Tradeoffs:**
- One new Protocol (`AgentContextStore`) + one new enricher
  (`AgentArtifactEnricher`) + one new value object (`AgentArtifact`).
- A store backend + lifecycle policy must be chosen at implementation time
  (Redis is the natural candidate given the existing stack; an in-memory impl
  suffices for tests).
- A new prompt variable (e.g. `prior_consistency_issues`) must be registered
  in the variable registry/taxonomy (RULE-22 §4) before any template consumes
  it — otherwise the adoption gate blocks.

**Constraints introduced:**
- RULE-22 — a producer→consumer agent boundary now exists; its contract is
  specified below.
- RULE-03 — `AgentContextStore` / `AgentArtifact` / `AgentArtifactEnricher`
  Protocols live in Core (`ai_invocation/`) **before** any Backend producer or
  consumer wiring.
- RULE-11 — store unavailability degrades gracefully and observably; the store
  is **never** a hard single-point-of-failure.

---

## Integration Contract (RULE-22)

The boundary is a one-directional producer→store→consumer chain:

```
producing service  --publish-->  AgentContextStore  --read-->  AgentArtifactEnricher
(ConsistencyOrchestrator,                                   (ContextEnricher)
 BetaRead, FactExtractor, ...)                                    |
                                                                  | inject
                                                                  v
                                              PromptInvocationContext.dynamic_inputs
                                                                  |
                                                                  v
                                                  prompt template variable
                                                  (e.g. {{prior_consistency_issues}})
```

**Shape (defined here; not yet implemented — RULE-03):**

- `AgentArtifact` (frozen value object): `kind: str` (the RULE-22 §1 shared-data
  identifier, e.g. `"consistency_issues"`, `"beta_read_critique"`),
  `scope_project_id`, optional `scope_session_id`, `produced_by_feature_id`,
  `produced_at`, `payload: str` (JSON-serialized structured artifact — matches
  the `dynamic_inputs: dict[str, str]` contract), and a content `digest` for
  provenance/evidence.
- `AgentContextStore` (Protocol, optional DI): `publish(artifact)`,
  `latest(*, project_id, kind, session_id=None) -> AgentArtifact | None`,
  `list_kinds(*, project_id, session_id=None)`.
- `AgentArtifactEnricher` (implements `ContextEnricher`): reads `latest` for the
  invocation's relevant `kind`s scoped by `context.project_id`, injects the
  payload into `dynamic_inputs` under a **registered** variable.

**RULE-22 obligations:**
- **§1 identification:** `AgentArtifact.kind` is the canonical shared-data
  identifier. Each kind has exactly one producer (no two agents publish the same
  kind) and a documented payload schema.
- **§2 change/supersede behaviour:** `publish` of a new artifact with the same
  `(scope, kind)` **supersedes** the prior (last-writer-wins). There is no
  unbounded append — this is the deliberate counterpoint to ADR-050's
  hard-delete/tombstone debate (we choose bounded supersession here).
- **§4 variable registration:** the consumed variable (e.g.
  `prior_consistency_issues`) is registered in the variable registry and
  classified in the taxonomy **before** any template references it (the
  ADR-050 P1-D lesson). An unregistered variable blocks the adoption gate.
- **§7 precedence:** when an artifact and a live enricher both speak to
  consistency, the *live structural status* (`KBConsistencyEnricher`) and the
  *carried issue substance* (this store) are distinct variables with distinct
  provenance; no silent override.

**Graceful degradation (RULE-11) — mandatory:**
- `AgentArtifactEnricher` accepts `store: AgentContextStore | None`.
- When the store is `None`, the invocation has no `project_id`, or no artifact
  of the requested kind exists, the enricher is a **no-op**: it returns the
  context unchanged and emits an observable structured log
  (`agent_artifact_enricher_noop` + reason). This mirrors
  `KBConsistencyEnricher`'s `_not_applicable_update` exactly.
- A store read/publish failure is **caught and logged** (never raised into the
  agent call path) — the agent proceeds without carry-forward context. Quality
  degrades; the system does not crash. This makes the store a soft dependency,
  not a single-point-of-failure.
- Degradation is reflected in invocation evidence so audit tooling can detect
  "ran without carry-forward" runs.

---

## Sustainability Check

1. **Correct in 3 months?** Yes. Every new chained workflow publishes/consumes
   via the same `kind`-keyed contract; no special cases. The enricher seam is
   stable (ADR-038) and already hosts three enrichers.
2. **Hard-to-undo coupling?** Minimal. Producer→store→consumer is
   one-directional; producers do not import consumers (or vice versa). The
   store is a Protocol; the backend is swappable. Removing the feature means
   dropping one enricher from the pipeline.
3. **Simplest correct solution?** Yes, versus the alternatives. mem0/ProcessHistory
   reuse is wrong-scope/wrong-type/wrong-policy; status quo solves nothing.
   Routing through the existing enricher seam is the smallest contract that
   closes the gap.
4. **Design intent clear?** Yes — it is a direct generalisation of
   `KBConsistencyEnricher` (read a source, inject `dynamic_inputs`, degrade
   gracefully), which is already the codebase's mental model for runtime
   context injection.

---

## RULE-XX Compliance

| Rule | Status | Notes |
|------|--------|-------|
| RULE-03 | ✅ | `AgentContextStore` / `AgentArtifact` / `AgentArtifactEnricher` Protocols defined in this ADR (in Core `ai_invocation/`) **before** any implementation. |
| RULE-06 | ✅ | Artifact carry-forward is its own concern (one enricher + one store Protocol), separate from KB CRUD, memory, and ProcessHistory. |
| RULE-07 | ✅ | Contracts in Core; producers/consumers wired in Backend; no Core→apps imports. |
| RULE-09 | ✅ | `AgentArtifact` is a typed frozen value object; payload is JSON-string only because `dynamic_inputs` is `dict[str, str]` (established contract), not `Any`. |
| RULE-11 | ✅ | Store unavailability degrades gracefully and observably (logged + evidence); never a hard failure. |
| RULE-22 | ✅ | Producer→consumer agent boundary contracted: shared-data identification (`kind`), supersede behaviour, variable registration, and live-vs-carried precedence all specified. |
| RULE-20 | ✅ | No half-implementation ships under this ADR; the Gate-12 checklist below gates `✅ Implemented`. |

---

## Implementation Notes

This ADR is a **decision only**. No production code, tests, or `contracts.py`
files are produced in this task (RULE-03: the contract is *defined above*; the
code is a separate follow-up).

**Phased implementation plan (for the follow-up task, not this ADR):**

1. **Core (contracts):** define `AgentArtifact`, `AgentContextStore` Protocol,
   and `AgentArtifactEnricher` in `packages/core/narrare_core/ai_invocation/`
   (new `agent_context.py` + enricher module). Unit-test Protocol structural
   compatibility and the no-op degradation path.
2. **Backend (producers):** have `ConsistencyOrchestrator.run_staged_check`
   (and, later, a Beta-Read service) publish their typed result as an
   `AgentArtifact` after a successful run.
3. **Backend (consumer wiring + variable registration):** register
   `prior_consistency_issues` (and siblings) in the variable registry/taxonomy;
   add `AgentArtifactEnricher` to the `InvocationPipeline` enricher sequence;
   add the variable to the relevant prompt templates.
4. **Backend (store backend):** provide a Redis-backed `AgentContextStore` impl
   + an in-memory fake for tests.
5. **Tests:** integration test asserting a published artifact is injected into a
   subsequent invocation's `dynamic_inputs`, and that the consumer run is
   unaffected when the store is absent (degradation).

**ADR Implementation Completeness Gate (Gate 12):** This ADR is `✅ Accepted`
(decision in effect); it reaches `✅ Implemented` only when all five phases
above land, the variable is registered and consumed by a real template, and
the degradation path has a test. See
`.opencode/context/narrare-dev/processes/quality-gates.md` for the full Gate-12
checklist.

---

## Review Trigger

- [ ] When the first producer/consumer pair (Consistency → Co-Author-Fix) is
      implemented — verify the published artifact reaches the consumer's
      `dynamic_inputs` and that the prompt variable is registered.
- [ ] When a second artifact `kind` (e.g. beta-read critique) is added — verify
      it reuses the contract without special-casing.
- [ ] When user feedback shows supersession (last-writer-wins) is too
      aggressive (e.g. an author wants to keep multiple rounds) — consider a
      follow-up ADR for bounded multi-version retention.
- [ ] If the store backend choice (Redis) proves operationally burdensome —
      re-evaluate the backend, not the contract.
- [ ] If an artifact kind is found to duplicate what `KBConsistencyEnricher`
      computes live — collapse the duplication (honour RULE-22 §1).

---

## Cross-References

* **ADR-033** — mem0 preference scope (why artifacts do **not** go in mem0).
* **ADR-034** — Conversational History Policy (why artifacts do **not** go in
  ProcessHistory; the task/conversational boundary this ADR respects).
* **ADR-038** — AI Invocation Adoption Contract (the `ContextEnricher` /
  `dynamic_inputs` seam this ADR reuses).
* **ADR-044** — Staged Consistency (the canonical *producer*: the typed
  `ConsistencyResponse` that a Co-Author fix run should consume).
* **ADR-048** — Non-Writing Invocation Adapter (every domain invokes through the
  same pipeline, so the enricher consumer applies uniformly).
* **ADR-050** — Cross-Feature Context Contracts (precedent: typed Protocols +
  variable registration + supersession/hard-delete reasoning).
* **review-03 §3** — triggering finding (`AUFG-03-06`).
