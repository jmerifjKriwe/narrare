# ADR-053 — AI Session Lifecycle Pattern (WebSocket)

> **Status:** ✅ Accepted
> **Date:** 2026-06-24
> **Deciders:** Architecture Specialist (drafted by Documentation Specialist)
> **Supersedes:** —
> **Related:** ADR-043 (`useAIOperation` — Review-Trigger #1, closed by this ADR), ADR-052 (Session Stop & WebSocket Recovery), ADR-024 (Free-Form Chat), §16 AI-Interaction Standards (`docs/development/ui-principles.md`)

---

## Context

ADR-043 defined `useAIOperation` — the shared React hook for the **SSE/REST
request–response** AI operation lifecycle (`idle → loading → streaming →
complete → error → connection_lost`). ADR-043 deliberately scoped WebSocket
flows out of `useAIOperation` and logged an explicit review trigger:

> *When a WebSocket-based AI flow needs lifecycle management → new `useAISession` ADR*

(ADR-043 §"Out of Scope", §Consequences #4, and Review-Trigger #1.)

That trigger has now fired. The interactive writing session
(`/writing/sessions/{chapter_id}`) is a **persistent-connection** AI surface
whose transport lifecycle is structurally different from the one-shot SSE
operations `useAIOperation` models:

| Concern | `useAIOperation` (SSE/REST) | WebSocket session |
|---------|------------------------------|-------------------|
| Connection | per-operation (open, stream, close) | persistent; survives many turns |
| Identity | none (stateless request) | `session_id`; reattachable after drop |
| Stop | client-side `AbortController` | server-side `asyncio.Task.cancel()` (ADR-052) |
| Recovery | restart the operation | reattach to the *same* session / turn (ADR-052) |
| Lifecycle owner | the **hook** owns the lifecycle | the **server** owns session/turn lifecycle; the hook reflects it |

CR-AUFG-07-21 (ADR-052) implemented session Stop/Recovery. Its frontend
companion is `useSessionSocket`, whose lifecycle signals were **intentionally
shaped to mirror `useAIOperation`'s state machine** so both surfaces present
the same §16 UX lifecycle to the user while remaining honest about their
different transports.

### Current State (code-grounded)

`useSessionSocket` lives at
`packages/web/components/studio/editor/useSessionSocket.ts` and exposes these
observable lifecycle signals:

| Signal | Type | Source |
|--------|------|--------|
| `isConnected` | `boolean` | transport open / closed |
| `isStreaming` | `boolean` | first `text_chunk` … `text_done` / `generation_stopped` |
| `recoveryState` | `"idle" \| "reconnecting" \| "recovered" \| "failed"` | recovery handshake |
| `saveNotification` | `string \| null` | `saved` / `generation_stopped` notifications |

Adjacent pieces (all verified on disk):

- `createSessionMessageHandler.ts` maps every inbound frame to lifecycle
  transitions (`connection_lost` → `reconnecting`; `session_recovered` →
  `recovered`; `recovery_failed` → `failed`; `text_chunk` → streaming; …).
- `SessionReconnectBanner.tsx` renders the `recoveryState`-driven banner with a
  retry affordance.
- `useSessionPanelActions.ts` dispatches `stop_generation` (server-side cancel,
  ADR-052 Decision 2).
- `sessionSocketMessages.ts` builds the `recover_session` / `stop_generation`
  client frames (reattach handshake + stop).

### Root Cause Analysis (2× "Why?")

**Symptom:** The project now has two AI-interaction lifecycle surfaces
(`useAIOperation` for SSE/REST; `useSessionSocket` for WebSocket) and no
decision stating how they relate — risking divergence or a forced, premature
unification.

**Why #1 — Why are there two hooks?** Because the two transports have
structurally different lifecycles (request/response vs persistent reattachable
session). `useAIOperation` is transport-agnostic for *one-shot* async
operations and owns the AbortController; the WebSocket session's lifecycle is
server-owned and reattachable (ADR-052).

**Why #2 (Root Cause):** There is no architectural record deciding *whether*
to unify them. Without one, the choice between (a) keeping `useSessionSocket`,
(b) building a generic `useAISession` that subsumes it, or (c) extending
`useAIOperation` to WebSocket is unguided. The correct fix is to make the
decision explicit and document the state mapping so both surfaces provably
follow the same §16 UX lifecycle.

---

## Decision Drivers

- **§16 compliance parity:** Both AI surfaces must present the same UX
  lifecycle (loading, streaming, cancel, error, connection-loss) to the user.
- **Architectural honesty:** Do not collapse two different transport paradigms
  into one abstraction that fits neither precisely.
- **RULE-06 (one responsibility per file) & RULE-04 (modularize, don't
  compress):** Avoid a god-hook that mixes SSE request/response semantics with
  persistent-session reattach semantics.
- **Stability:** `useSessionSocket` is implemented, tested
  (`useSessionSocket.recovery.test.tsx`, `SessionReconnectBanner.test.tsx`,
  `SessionPanel.test.tsx`), and in production; unnecessary churn is risk
  without user benefit.
- **ADR-043 closure:** Review-Trigger #1 must be resolved with a documented
  decision, not left open.
- **Sustainability (architectural-discipline §5):** If a third transport
  paradigm appears later, the decision must not preclude a future shared
  adapter, but must not build one speculatively now.

---

## Options Considered

### Option A — Build a generic `useAISession` that subsumes `useSessionSocket`

Create one hook that owns *both* the SSE/REST and WebSocket lifecycle by
adapting `useSessionSocket` underneath it.

**Pros:**
- Single import name for "AI session" across the app.
- One place to read the lifecycle.

**Cons:**
- **Premature / unneeded abstraction.** The two transports differ in who owns
  the lifecycle (client AbortController vs server `Task.cancel` + reattach). A
  unified hook would be a switch-on-transport wrapper with little shared body —
  abstraction without consolidation.
- **Refactoring risk with no user benefit.** `useSessionSocket` is tested and
  stable; wrapping it risks regressions for a naming nicety.
- **Violates the simplicity tenet of architectural-discipline §5** (simplest
  *correct* solution).

### Option B — Extend `useAIOperation` to support WebSocket sessions

Add WebSocket/session modes to `useAIOperation` (e.g. `notifyReattach`,
`session_id` options).

**Pros:**
- One hook for everything AI.

**Cons:**
- **Mixes two transport paradigms** in one responsibility — SSE stateless
  request/response vs WebSocket persistent reattachable session. This is the
  exact concern ADR-043 §"Out of Scope" called out.
- Forces `useAIOperation`'s client-owned AbortController lifecycle to also
  model a server-owned, reattachable lifecycle → the hook's invariants
  (`start` / `cancel` / `retry` own the controller) stop holding.
- Compromises RULE-06 / RULE-04: the hook's single responsibility
  ("one-shot AI operation lifecycle") gains a second responsibility
  ("persistent reattachable session").

### Option C — Keep `useSessionSocket` with a documented §16 state mapping (chosen)

Retain `useSessionSocket` as the **WebSocket-session specialist** and formally
document its UX-level mapping to `useAIOperation`'s state machine. Both hooks
follow §16; each owns the transport it actually models.

**Pros:**
- **Honest separation:** each hook models the lifecycle it genuinely owns.
- **Zero churn:** no refactor of stable, tested code.
- **§16 parity is explicit and verifiable** via the mapping below.
- **Future optionality preserved:** a shared adapter remains possible later
  without forcing it now.

**Cons:**
- Two hook names instead of one ("`useAISession`" never exists as a code
  symbol). This is acceptable — and correct — because the paradigms differ.

---

## Decision

**We choose Option C — keep `useSessionSocket` as the WebSocket-session hook;
do NOT build a separate `useAISession` hook.**

- `useSessionSocket` is the **WebSocket specialist**; `useAIOperation` is the
  **SSE/REST specialist**.
- Both follow the same §16 UX-lifecycle principles.
- The mapping below is the contract of their parity; it is documented here
  (not encoded in a shared abstraction) because the transports differ in who
  owns the lifecycle.
- The WebSocket-specific requirements that `useAIOperation` does **not** cover
  (server-side stop via `Task.cancel`, reattach handshake, recoverable session
  identity, `SessionReconnectBanner`) are fulfilled by `useSessionSocket` +
  ADR-052.

---

## State Mapping (§16 parity contract)

`useAIOperation`'s six lifecycle states map to `useSessionSocket`'s observable
signals as follows. The mapping is **UX-level (§16)**, not mechanical: the
transports differ in lifecycle ownership, so a few states have no exact
boolean in `useSessionSocket` (noted explicitly — no overstatement).

| `useAIOperation` state (§16) | `useSessionSocket` observable | Note |
|------------------------------|-------------------------------|------|
| `idle` | `recoveryState === "idle" && !isStreaming` | No turn in flight (session may be connected or not). |
| `loading` | per-turn window: after `user_direction` send, before first `text_chunk` (`isStreaming === false`) | `useSessionSocket` exposes **no explicit loading boolean**; the window is implicit. (Honest gap — see Trade-offs #2.) |
| `streaming` | `isStreaming === true` | Set on first `text_chunk`; cleared on `text_done` / `generation_stopped`. |
| `complete` | `isStreaming === false` after a turn, session active | Transcript updated; session persists. |
| `error` | `recoveryState === "failed"` **or** an `error` frame | `recovery_failed` → system message + disconnect; `error` → system message only. |
| `connection_lost` | `recoveryState === "reconnecting"` | Triggered by the `connection_lost` frame **or** a transport drop while a `session_id` exists; `SessionReconnectBanner` offers retry → `recover_session`. |

> **`loading` vs `connection_lost` are not conflated.** Both can read as "not
> streaming", but they are distinguishable: `connection_lost` / reconnect sets
> `recoveryState = "reconnecting"` with `isConnected = false`, whereas a
> per-turn `loading` window keeps `isConnected = true`. The banner renders on
> `recoveryState !== "idle"`, so the two never present identically.

---

## Rationale

ADR-043's own analysis treats WebSocket sessions as a separate concern
(§"Out of Scope", §Consequences #4): the one-shot, client-owned
AbortController lifecycle of `useAIOperation` does not model a persistent,
server-owned, reattachable session. Forcing unification (Options A/B) would
either produce a switch-on-transport wrapper (abstraction without
consolidation) or corrupt `useAIOperation`'s invariants (it owns the
controller; a WebSocket session does not). Option C keeps each hook honest
about the lifecycle it owns and makes their §16 parity explicit and auditable
via the mapping above — without churning tested, production code.

### Trade-offs Accepted

1. **No single `useAISession` symbol.** The name never exists in code. Accepted
   because the paradigms differ; a single name would obscure that.
2. **`useSessionSocket` has no explicit `loading` boolean** for the per-turn
   "sent, awaiting first chunk" window. Today this is implicit
   (`isStreaming === false` while `isConnected === true`). If per-turn loading
   UX (e.g. a spinner between send and first token) becomes a requirement,
   `useSessionSocket` should gain an explicit `isAwaitingFirstChunk` flag
   rather than this being treated as a `useAIOperation` gap. (Tracked under
   Review Triggers.)
3. **§16 parity is maintained by review + the mapping table above**, not by a
   shared primitive. Mitigated by making the mapping the explicit parity
   contract.

---

## Consequences

### Positive
- **Clear separation of transports:** SSE/REST (`useAIOperation`) vs WebSocket
  persistent session (`useSessionSocket`), each following §16.
- **No risky refactor:** stable, tested WebSocket code is untouched.
- **ADR-043 Review-Trigger #1 is closed** by a documented decision.
- **Future optionality:** a shared adapter remains possible if a third
  transport paradigm appears.

### Negative / Trade-offs
- **Two hook names** instead of a unified `useAISession` — acceptable because
  the paradigms differ.
- **§16 parity is maintained by documentation + review**, not enforced by a
  shared primitive (see mapping table).

### Neutral
- `useSessionSocket` already implements all WebSocket-specific requirements
  (server-side stop, reattach, recoverable identity, banner) on top of
  ADR-052; this ADR records the *decision*, not new code.

---

## RULE-XX Compliance

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-03 | ✅ | This ADR is the contract documenting the two-hook boundary and the §16 state mapping before any future change. No new Protocol needed — it ratifies existing, contract-backed code. |
| RULE-06 | ✅ | Each transport keeps its own single-responsibility hook; the decision explicitly rejects merging them into one responsibility. |
| RULE-20 | ✅ | WebSocket "stop" has a genuine transport effect (server `Task.cancel`, ADR-052 Decision 2), surfaced through `useSessionSocket` — not a UI-only flag flip. |

---

## Sustainability Check

1. **Correct in 3–6 months?** Yes. The decision is defined by the
   transport-paradigm separation, not by today's specific socket code.
2. **Hard-to-undo coupling?** No. It introduces no new coupling; it documents
   an existing boundary.
3. **Simplest correct solution?** Yes. Option C is the least-churn choice that
   preserves §16 parity and transport honesty; Options A/B add abstraction or
   corrupt invariants for no user benefit.
4. **Design intent clear?** Yes. SSE/REST and WebSocket each have the hook that
   owns their actual lifecycle; §16 parity is the documented mapping.

---

## Implementation Notes

- **No code change is required by this ADR.** It ratifies the existing
  `useSessionSocket` design and closes ADR-043 Review-Trigger #1.
- **§16 reference:** the UX-lifecycle principles both hooks follow live in
  `docs/development/ui-principles.md` §16 (established by ADR-043).
- **Transport boundary:** `useSessionSocket` reflects a **server-owned**
  lifecycle (ADR-052's `ActiveTurnRegistry`, `Task.cancel`, `?session_id=`
  reattach, `connection_lost` idle timeout). Do not add client-owned
  AbortController semantics to it.
- **If per-turn loading UX is later needed:** add an explicit
  `isAwaitingFirstChunk` flag to `useSessionSocket` (Trade-off #2); do **not**
  route WebSocket sessions through `useAIOperation`.

> **ADR Implementation Completeness Gate (Gate 12):** this ADR documents an
> existing design decision; there is no implementation surface to wire. Its
> "completeness" is the documented mapping plus the closed review trigger —
> both present in this file and in ADR-043.

---

## Review Triggers

- [ ] When a **third** transport paradigm for AI interaction appears
  (e.g. MCP / A2A streamed sessions) → re-evaluate a shared lifecycle adapter.
- [ ] When per-turn "loading" UX (spinner between send and first token) becomes
  a product requirement → add `isAwaitingFirstChunk` to `useSessionSocket`
  (Trade-off #2) and extend the mapping table.
- [ ] When `useAIOperation` and `useSessionSocket` §16 behavior visibly
  diverges → reconcile via the mapping table.
- [ ] After 6 months — verify both surfaces still satisfy §16 end-to-end.
