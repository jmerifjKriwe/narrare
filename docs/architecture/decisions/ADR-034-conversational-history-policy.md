# ADR-034 — Conversational History Policy for Narrare Agents

> **Status:** ✅ Implemented
> **Date:** 2026-06-04
> **Deciders:** User, Architecture Agent
> **Supersedes:** —
> **Related:** ADR-015, ADR-016, ADR-024, ADR-026, ADR-027, ADR-033

> **Implementation Note:** Implemented as `HistoryPolicy` enum (NONE, CONVERSATIONAL)
> on `NarrareAgent` base class. Default is NONE (task agents). No agent currently
> uses CONVERSATIONAL — Chat remains a non-agent streaming service. When Chat migrates
> to a NarrareAgent, it will declare `history_policy=HistoryPolicy.CONVERSATIONAL`.

---

## Context

Pydantic AI supports `ProcessHistory`, but Narrare has both conversational agents and task agents. Applying process history globally would mix unrelated state into extraction, analysis, rewrite, and selection tasks.

Root cause chain:

1. **Symptom:** History handling risks becoming a global agent concern.
2. **Why:** A single `NarrareAgent` abstraction can hide whether the agent is conversational or task-based.
3. **Why:** The architecture lacks an explicit policy boundary for history ownership.
4. **Design:** Separate conversational history from task execution through dedicated agent types or an equivalent `HistoryPolicy` contract.

---

## Decision Drivers

- Task agents need deterministic, bounded context.
- Conversational agents need continuity and user-visible memory of the conversation.
- History must not leak between tasks, users, projects, or agent roles.
- RULE-13 streaming/non-streaming interfaces must remain unified.
- Free-Form Chat, Interactive Writing, and Co-Author sessions have different history semantics than KB extraction or rewrite selection.

---

## Options Considered

### Option A — Split TaskNarrareAgent and ConversationalNarrareAgent or equivalent HistoryPolicy (chosen)

Represent history as an explicit policy. Task agents default to no process history. Conversational agents opt in.

**Pros:**
- Clear architectural boundary.
- Prevents accidental state leakage.
- Supports future chat/session features.
- Testable through contracts and evals.

**Cons:**
- Requires class/policy design before implementation.
- Existing agents must be classified.

### Option B — Use ProcessHistory globally

Attach process history to all Narrare agents.

**Pros:**
- Simple configuration.
- Conversational continuity available everywhere.

**Cons:**
- Pollutes task agents with irrelevant state.
- Makes extraction/rewrite results less deterministic.
- Creates hidden coupling between unrelated invocations.

### Option C — No ProcessHistory anywhere

Handle all history manually through prompt/context assembly.

**Pros:**
- Maximum explicitness.

**Cons:**
- Conversational features rebuild a standard history mechanism.
- Higher risk of inconsistent chat behavior.

### Option D — Per-call ad hoc history flags

Let each caller decide whether to pass history.

**Pros:**
- Flexible.

**Cons:**
- Turns history into caller discipline instead of architecture.
- Easy to forget or misuse.
- Violates no-workaround discipline.

---

## Decision

**We choose Option A: history is governed by an explicit conversational-history policy.**

Implementation may realize this as separate `TaskNarrareAgent` / `ConversationalNarrareAgent` classes or as an equivalent `HistoryPolicy` contract. The architectural requirement is the same:

- **Task agents:** no `ProcessHistory` by default.
- **Conversational agents:** may use `ProcessHistory` through the approved policy.

Conversational candidates:

- Free-Form Chat.
- Interactive Writing.
- Co-Author Session where turns are user-visible conversation.

Task-based agents where ProcessHistory is forbidden by default:

- KB extraction.
- Preference analysis.
- Rewrite selection/generation.
- Consistency/timeline analysis.
- Summarization/extraction jobs.

Forbidden steady states:

- Global ProcessHistory enabled for all agents.
- Call-site ad hoc history decisions without a policy.
- Hidden history persistence that users cannot reason about.

---

## Rationale

History is product semantics, not a convenience flag. A conversation needs continuity; an extraction or rewrite task needs deterministic input isolation. Keeping those semantics separate prevents a future class of subtle quality bugs where old conversational turns influence task outputs.

The policy approach is more sustainable than a global switch and more disciplined than caller-managed flags.

---

## Consequences

**Positive:**
- Prevents context contamination for task agents.
- Makes conversational continuity explicit.
- Provides a clear classification step for future agents.

**Negative / Tradeoffs:**
- Requires auditing existing agents.
- New agent specs must state their history policy.

**Constraints introduced:**
- Every new agent architecture/spec must declare `HistoryPolicy`.
- Any task agent using ProcessHistory requires an ADR-level exception.

---

## Implementation Plan / Migration Plan

1. Define `HistoryPolicy` contract or split agent classes before implementation.
2. Classify existing agents as task or conversational.
3. Apply `ProcessHistory` only to conversational agents.
4. Add tests/evals verifying task agents do not receive previous-turn state.
5. Document history policy in agent-creation guidance during Docs Gate.

---

## RULE-XX Compliance

| Rule | Status | Nachweis |
|------|--------|----------|
| RULE-01b | ✅ | Policy applies inside approved agent architecture. |
| RULE-02 | ✅ | History is runtime data, not prompt-template assembly. |
| RULE-03 | ✅ | Policy/agent contracts precede implementation. |
| RULE-06 | ✅ | History policy is a distinct responsibility. |
| RULE-07 | ✅ | Core agent policy does not depend on API/UI. |
| RULE-13 | ✅ | Streaming and non-streaming use the same history policy. |
| RULE-20 | ✅ | No global shortcut or ad hoc call-site workaround. |

---

## Sustainability Check

- Correct in 3 months: yes; new agents can be classified consistently.
- Hard-to-undo coupling: reduced by removing hidden global history.
- Simplest correct solution: yes; explicit policy boundary.
- Design intent clear: yes; conversational continuity only where semantically required.

---

## Review Triggers

- A task agent demonstrably requires multi-turn memory for correctness.
- Pydantic AI changes ProcessHistory APIs materially.
- New product sessions blur task/conversation boundaries and need reclassification.
