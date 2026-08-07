# ADR-036 — Durable Execution Boundary

> **Status:** ✅ Accepted (amended 2026-08-07)
> **Date:** 2026-06-04
> **Deciders:** User, Architecture Agent
> **Supersedes:** —
> **Related:** ADR-007, ADR-012, ADR-031, ADR-032, ADR-034, ADR-080
> **Amended by:** [ADR-080](ADR-080-remove-redis-taskiq-in-process-execution.md)
> (2026-08-07) — substrate references only (TaskIQ → in-process asyncio
> execution boundary); the durable-execution gate **policy** (Option A: block a
> second workflow stack behind a dedicated ADR) is unchanged.

> ⚠️ **Amended 2026-08-07 by [ADR-080](ADR-080-remove-redis-taskiq-in-process-execution.md).**
> The execution *substrate* referenced throughout this ADR (TaskIQ as "the only
> execution substrate") is updated to the **in-process asyncio execution
> boundary** defined by ADR-080. The gate *policy* (block durable execution
> behind a dedicated ADR; no second workflow stack) is **unchanged**. Read this
> ADR's Options A/B/C as referencing the current substrate (in-process per
> ADR-080), not TaskIQ. The execution *boundary* that this ADR exists to govern
> is exactly what ADR-080 relocates (cross-process Redis-queue → process-lifetime).

---

## Context

AI runtime modernization raises the question of durable execution for long-running or resumable AI workflows. Narrare already has TaskIQ for background tasks and Redis Pub/Sub for event-driven dispatch. Introducing another workflow engine without a replacement/integration decision would create a second infrastructure stack.

Root cause chain:

1. **Symptom:** Durable execution is attractive for agent workflows but undefined relative to TaskIQ.
2. **Why:** Some AI operations may need retry, resume, visibility, and idempotency beyond simple request/response.
3. **Why:** The current architecture has background execution but no accepted durable workflow boundary for AI sessions.
4. **Design:** Do not implement durable execution until Architecture decides whether it replaces, extends, or is rejected in favor of TaskIQ.

---

## Decision Drivers

- No second workflow infrastructure without a complete decision.
- TaskIQ is already accepted by ADR-007 and integrated with events by ADR-012.
- Durable execution affects service contracts, persistence, idempotency, observability, and retries.
- Local-first deployment remains mandatory.
- Agent history policy and output validation must be stable before durable workflows are designed.

---

## Options Considered

### Option A — Defer durable execution behind an architecture gate (chosen)

Make durable execution explicitly out of scope for Phase 0 implementation until a dedicated decision compares it to TaskIQ.

**Pros:**
- Prevents parallel workflow stacks.
- Protects ADR-007/ADR-012 coherence.
- Allows requirements to be defined from actual workflow needs.

**Cons:**
- No immediate durable workflow features.

### Option B — Add durable execution alongside TaskIQ now

Introduce a workflow engine for AI tasks while retaining TaskIQ.

**Pros:**
- More capabilities quickly.

**Cons:**
- Violates no-parallel-stack rule.
- Duplicates retry, visibility, scheduling, and persistence concepts.
- Hard to undo once workflows depend on both.

### Option C — Replace TaskIQ immediately

Select a durable execution engine and migrate all background work.

**Pros:**
- One infrastructure stack if completed.

**Cons:**
- Too large for Phase 0 without a full requirements and migration analysis.
- Risks destabilizing existing event/task architecture.

### Option D — Use only synchronous request flows

Avoid durable execution and background tasks for AI runtime modernization.

**Pros:**
- Simple.

**Cons:**
- Does not fit long-running extraction, eval, consistency, or generation workflows.

---

## Decision

**We choose Option A: durable execution is blocked behind a dedicated Architecture Gate.**

Phase 0 does not approve implementation of a durable execution engine. Future work must first produce an ADR deciding one of:

1. TaskIQ remains the only execution substrate and gains required patterns.
2. A durable execution engine replaces TaskIQ with a full migration plan.
3. A durable execution engine extends TaskIQ with explicitly separated responsibilities and no duplicated workflow ownership.

Forbidden steady states:

- TaskIQ plus a durable workflow engine both owning retries/scheduling for the same workflow class.
- Durable execution introduced only for one feature without global execution architecture.
- A workflow engine chosen because it is convenient for one agent without local-first validation.

---

## Rationale

Durable execution is infrastructure, not a feature-level implementation detail. If introduced incorrectly, it creates one of the hardest forms of technical debt: duplicated workflow ownership. The correct Phase 0 decision is to block implementation until TaskIQ replacement/extension/rejection is explicitly decided.

---

## Consequences

**Positive:**
- Prevents accidental second workflow stack.
- Keeps existing TaskIQ/event architecture coherent.
- Forces future durable-execution work to define idempotency, persistence, retries, and observability up front.

**Negative / Tradeoffs:**
- Durable/resumable agent workflows are not part of this modernization phase.
- Future features that truly require durable execution must wait for an ADR.

**Constraints introduced:**
- No durable execution dependency or module may be added without a dedicated ADR.
- Any future proposal must include migration/integration with ADR-007 and ADR-012.

---

## Implementation Plan / Migration Plan

No implementation in Phase 0.

Future ADR must include:

1. Workflow taxonomy: request-bound, TaskIQ background, event-driven, conversational session, durable workflow.
2. TaskIQ impact analysis: replace, extend, or keep separate with non-overlapping ownership.
3. Persistence/idempotency model.
4. OTel span model per ADR-031.
5. Local-first deployment and dependency analysis.
6. Migration plan with no half-implemented workflow states.

---

## RULE-XX Compliance

| Rule | Status | Nachweis |
|------|--------|----------|
| RULE-03 | ✅ | Future workflow contracts required before implementation. |
| RULE-05 | ✅ | Execution substrate ownership must be defined before modules are added. |
| RULE-07 | ✅ | Future workflow dependencies must preserve service → task/event direction. |
| RULE-08 | ✅ | Any external workflow engine requires an adapter and ADR. |
| RULE-12 | ✅ | Clients continue to call services, not workflow engines. |
| RULE-20 | ✅ | No partial second infrastructure stack. |
| RULE-21 | ✅ | Any material execution-plan change requires re-review. |

---

## Sustainability Check

- Correct in 3 months: yes; it prevents premature infrastructure coupling.
- Hard-to-undo coupling: avoided by not introducing a second workflow stack.
- Simplest correct solution: yes; block until the replacement/extension decision exists.
- Design intent clear: yes; durable execution is architecture-gated.

---

## Review Triggers

- A feature requires resumable multi-step execution that TaskIQ cannot model.
- TaskIQ limitations block AI runtime requirements.
- A durable execution engine is proposed as a new dependency.
