# ADR-052 — Session Stop and WebSocket Recovery

> **Status:** ✅ Accepted
> **Date:** 2026-06-22
> **Deciders:** Architecture Specialist
> **Supersedes:** —
> **Related:** ADR-043 (Review-Trigger #1 — WebSocket lifecycle management), ADR-045 (invocation contract preserved), WRITE-005, CONSTRAINTS.md RULE-03/RULE-06/RULE-08/RULE-20

---

## Context

The interactive writing-session WebSocket (`/writing/sessions/{chapter_id}`) is
the primary real-time AI surface in Narrare. The CR-AUFG-07-21 audit found that
two user-visible guarantees were broken on this surface:

1. **Stop did not stop.** The `SessionPanel` stop control was UI-only. Pressing
   it closed or hid the client UI, but the backend turn kept streaming to
   completion. There was no server-side handle to the active turn, so a cancel
   request could not reach the in-flight `await __anext__()`.
2. **Reconnect created a new session.** A dropped WebSocket (network blip, tab
   refresh, laptop sleep) always produced a brand-new session id and a fresh
   transcript cache. In-flight turns were lost and could not be reattached.

### Current State (code-grounded)

The WebSocket session stack was modularized by ADR-045 (Slice 3) into focused
modules. The transport-level shape after that split is:

| File | Responsibility |
|------|----------------|
| `router_sessions.py` | Endpoint: origin/rate checks, model/limit resolution, handler build. |
| `ws_handler.py` | `accept()` → `create_session()` → receive loop → `end_session()` in `finally`. |
| `ws_message_router.py` | Branches on `type` (`user_direction`, `end_session`, …) and delegates. |
| `ws_direction_dispatch.py` | Stores user message, streams turn-service chunks, persists assistant text. |
| `ws_turn_service.py` | Transport-agnostic turn orchestration (invocation contract). |
| `ws_streaming.py` | `StreamSender` Protocol + `send_stream_chunks()` DTO adapter. |
| `ws_session_context.py` | Frozen `WritingSessionContext` value object. |

The invocation contract (ADR-045) is correct and **preserved unchanged** by this
ADR. The defect is strictly in the **transport/session lifecycle** layered on
top of it. Three concrete facts make stop impossible and recovery impossible:

**Fact 1 — The active turn is not registered anywhere.**
`WritingDirectionDispatcher.dispatch()` runs the stream inline:

```python
result = await send_stream_chunks(
    websocket,
    self._turn_service.stream_turn(...),
)
```

There is no `ActiveTurnRegistry` and no `asyncio.Task` handle retained (grep for
`ActiveTurnRegistry`/`Task.cancel` in `apps/api` returns no matches). A stop
message therefore has nothing to cancel.

**Fact 2 — The receive loop is synchronous/blocking.**
`WritingSessionHandler.handle()` loops:

```python
while True:
    data = await asyncio.wait_for(websocket.receive_json(), timeout=...)
    await self._message_router.route(websocket, context, data)
```

`route()` is awaited inline, and a `user_direction` turn streams **inside**
`route()`. While the turn streams, the loop cannot call `receive_json()` again.
A `stop` message sent mid-stream is queued in the socket buffer and only
processed after the turn finishes — by which point stopping is meaningless.

**Fact 3 — Session state is per-connection and torn down on disconnect.**
`router_sessions.py` creates `cache = InMemorySessionCache()` **per connection**
inside the endpoint, and `ws_handler.py` calls `end_session(session_id)`
unconditionally in `finally`. A reconnect therefore gets a new session id and an
empty cache; there is no `?session_id=` reattach path and no shared cache to
recover from.

### Root Cause Analysis (2× "Why?")

**Symptom:** Stop is UI-only; reconnect loses the session and any in-flight turn.

**Why #1 — Why can't the backend stop the stream?**
Because the active turn runs inline inside the receive loop and is never
registered as a cancellable handle. Cancellation has no target.

**Why #2 (Root Cause) — Why is the turn inline and unregistered?**
Because the writing session treats the **WebSocket transport lifecycle as the
session lifecycle**. The transport connection owns the session id, the cache,
and the turn execution. This conflates three distinct concerns — *connection*,
*session*, and *active turn* — into one synchronous loop. The model that
correctly describes an interactive AI session is **a recoverable server session
with at most one cancellable active turn, reached over a possibly-reconnecting
transport**, not "one connection = one turn = one session".

**Additional finding.** Even if a handle existed, the synchronous receive loop
(Fact 2) would prevent the stop message from being received until the turn
finished. Decoupling execution from the receive loop is therefore a
**prerequisite** for cancellation, not an optimization.

---

## Decision Drivers

- **RULE-03 (Contract first):** New boundaries (`ActiveTurnRegistry`,
  `SessionTransportSink`) must be executable Protocols before implementation.
- **RULE-06 (One responsibility per file):** Connection acceptance, session
  lifecycle, turn registration, and streaming must stay in separate modules.
- **RULE-08 (Core is infra-free):** The active-turn registry and transport sink
  are transport/session infrastructure and live in the Backend, not in Core.
  Core's invocation contract is untouched.
- **RULE-20 (Cancel has a transport effect):** A cancel must propagate into the
  blocked `await __anext__()` of the in-flight stream — a half-implementation
  that only flips a UI flag is explicitly rejected.
- **RULE-12/RULE-13 (One invocation policy, run + stream):** The turn service
  and its invocation/evidence/budget contract (ADR-045) are preserved; this ADR
  changes only how the turn is scheduled, cancelled, and reattached.
- **Recoverability:** A transient disconnect must not destroy an in-flight or
  recently-active turn or force the user to start over.
- **Correctness over cleverness:** The chosen mechanisms (`asyncio.Task.cancel`,
  app-state singletons, URL-param reattach) are boring, well-understood, and
  testable over novel abstractions.

---

## Options Considered

### Active-turn registry — where does the live turn handle live?

#### Option A — Backend in-memory registry (chosen)

A process-local `ActiveTurnRegistry` keyed by `session_id` holds the
`asyncio.Task` for the in-flight turn.

**Pros:**
- `asyncio.Task` handles are live objects that genuinely support `.cancel()`;
  they cannot be serialized, so in-process storage is the natural fit.
- Simple, fast, dependency-free; trivially testable with a fake registry.
- Registry is transport-agnostic (turns are `asyncio.Task`s, not WebSocket
  objects), so SSE/MCP transports can reuse it later.

**Cons:**
- Handles do not survive a server restart. (Mitigated by Decision 7: lazy
  cold-start reconciliation.)
- One active turn per session (concurrent directions rejected with `busy`).

#### Option B — Redis-backed registry

Store turn metadata in Redis.

**Pros:**
- Survives some restarts; works across multiple workers if added later.

**Cons:**
- `asyncio.Task` objects are **not serializable**. Redis could store *metadata*
  (status, invocation id) but never the live cancellable handle. The cancel path
  would still need an in-process map, making Redis a redundant second store with
  two sources of truth.
- Adds operational complexity (TTL management, cross-worker signalling) for a
  problem that is inherently single-process (the streaming task runs here).

#### Option C — Core registry

Put the registry in `packages/core/`.

**Pros:**
- Central, reusable.

**Cons:**
- **Violates RULE-08.** Core is infrastructure-free; an `asyncio.Task`/transport
  registry is transport/runtime infrastructure. It would force Core to depend on
  streaming-task lifetimes it must not know about. Rejected.

**Decision: Option A.**

### Cancellation mechanism — how does stop reach the blocked await?

#### Option A — `asyncio.Task.cancel()` (chosen)

The registered turn `Task` is cancelled; `CancelledError` propagates into the
blocked `await __anext__()` of the model stream, terminating it promptly.

**Pros:**
- Interrupts a genuinely in-flight `await` — the only mechanism that satisfies
  RULE-20. The stream stops at the next await point, not at stream end.
- Idiomatic, zero new dependencies, well-defined semantics.
- Composes cleanly with the existing `StreamSender`/`send_stream_chunks` adapter
  (the `async for` loop simply stops iterating).

**Cons:**
- `CancelledError` must be handled cleanly in the dispatcher so partial output
  is persisted or discarded deliberately, never silently (RULE-11).
- Requires `asyncio.Task` registration (depends on the registry decision).

#### Option B — Cooperative flag / `asyncio.Event`

A flag the turn loop polls between chunks.

**Pros:**
- Simple, no exception machinery.

**Cons:**
- **Cannot interrupt an in-flight `await __anext__()`** that blocks on the model
  provider (which is where streams actually stall). The turn would only stop at
  the *next chunk boundary* — which, for a slow provider, is exactly the case the
  user is trying to stop. This is the status quo dressed up as a fix and fails
  RULE-20.

#### Option C — httpx connection abort

Abort the underlying httpx connection.

**Pros:**
- For provider transport, very direct.

**Cons:**
- Much larger surface (depends on httpx internals, provider connection pools,
  retry layers). Couples session cancellation to LLM transport implementation
  details rather than to the turn abstraction. Brittle and over-scoped.

**Decision: Option A.**

### Shared session cache — how does a reconnect see prior state?

#### Option A — `app.state` singleton cache (chosen)

A single `SessionCacheProtocol`-conforming cache is created once at startup and
stored on `app.state`. All connections for a session read/write the same cache.

**Pros:**
- Genuine sharing: a reattaching connection sees the transcript and status left
  by the previous connection.
- DI-friendly, swappable (Redis-backed implementation can replace the in-memory
  one without code changes — the Protocol already exists).
- Locatable: every handler resolves the same instance from `app.state`.

**Cons:**
- In-memory instance is process-local (does not survive restart; see Decision 6
  TTL + Decision 7 reconciliation). Production deployment should back it with
  Redis, which the Protocol already permits.

#### Option B — Per-request factory (status quo)

`cache = InMemorySessionCache()` inside the endpoint, as today.

**Pros:**
- No change.

**Cons:**
- **Defeats sharing.** Each connection gets an isolated cache; a reconnect
  cannot recover state. This is precisely Fact 3 / the root defect.

#### Option C — Module-global cache

A module-level `_CACHE` variable.

**Pros:**
- Shared across connections.

**Cons:**
- **Untestable** (global mutable state, no injection seam) and violates the DI
  pattern used everywhere else in the WebSocket stack. Rejected.

**Decision: Option A.**

### Reattach identity — how does a reconnect claim the same session?

#### Option A — URL query param `?session_id=...` (chosen)

The client stores the session id after the greeting and reconnects to
`/writing/sessions/{chapter_id}?session_id=...`. The endpoint resolves reattach
vs. fresh-start from the param.

**Pros:**
- Resolved at connection acceptance — before the message loop — so the session
  is bound to the right identity from the first frame.
- Works for the very first message (no bootstrap round-trip), survives tab
  refresh, and is visible in logs/metrics.
- Aligns with the existing greeting, which already echoes `session_id` to the
  client.

**Cons:**
- The id travels in the URL; must be treated as untrusted and validated (the
  server verifies the id exists, belongs to the user/project, and is within TTL
  before adopting it).

#### Option B — First-message handshake

Client sends `{"type":"reattach","session_id":...}` as the first frame.

**Pros:**
- Keeps session id out of the URL.

**Cons:**
- Adds a round-trip and a "pre-session" window before the session is bound,
  complicating the greeting and error handling.

**Decision: Option A as primary; Option B may be used supplementary later** if
extra handshake metadata is needed, but it is not required for recovery.

### Disconnect behavior — what happens to the session on drop?

#### Option A — No auto-`end_session`; idle TTL + recovery window (chosen)

On disconnect, the session is **not** ended. The turn keeps running (bound to
the registry), the cache persists, and an idle timeout emits a `connection_lost`
event. The session remains recoverable until the cache TTL expires, after which
lazy reconciliation (Decision 7) finalizes it.

**Pros:**
- A transient drop is fully recoverable: the client reattaches and resumes.
- The active turn is not orphaned by a transport hiccup.

**Cons:**
- Sessions occupy cache/registry memory until TTL; requires a sensible TTL and
  the reconciliation sweep.

#### Option B — `end_session` on disconnect (status quo)

End the session in `finally`, as today.

**Pros:**
- Simple, eager cleanup.

**Cons:**
- **Makes recovery impossible** by design — this is the defect.

**Decision: Option A.**

---

## Decisions

### 1. Decouple streaming execution from the receive loop

`user_direction` turns are executed as a spawned `asyncio.Task`, registered in
the `ActiveTurnRegistry`, rather than awaited inline inside `route()`. The
receive loop remains free to accept the next message (including `stop`)
immediately. This decoupling is the **prerequisite** for both stop and
concurrent message handling.

### 2. Server-side cancellation via `asyncio.Task.cancel()`

A `stop` message cancels the registered turn `Task`. `CancelledError`
propagates into the blocked `await __anext__()` of the model stream and the turn
ends at the next await point. Partial output is handled deliberately in the
dispatcher (persisted-as-stopped or discarded per session policy), never
silently swallowed (RULE-11). This is the only mechanism that satisfies
RULE-20.

### 3. Swappable transport sink (`SessionTransportSink` Protocol)

Introduce a `SessionTransportSink` Protocol (distinct from, and wrapping, the
existing connection-bound `StreamSender`). The sink is **session-scoped, not
connection-scoped**: the active turn writes to the sink, and the sink can be
**rebound** to a new WebSocket on reattach without restarting the turn. This is
what lets an in-flight turn survive a reconnect.

### 4. Shared-cache injection via `app.state` singleton

Replace the per-connection `cache = InMemorySessionCache()` in
`router_sessions.py` with a single cache resolved from `app.state` (the
Protocol already supports a Redis-backed drop-in). All connections for a session
share one cache, so reattach sees prior transcript and status.

### 5. URL-param reattach via `?session_id=...`

The client reattaches by reconnecting with the prior session id as a query
param. The endpoint validates the id (exists, belongs to the user/project,
within TTL) before adopting it; otherwise it falls back to a fresh session. The
greeting already advertises the id, so no protocol addition is needed for the
client to learn it.

### 6. No auto-`end_session` on disconnect; idle timeout emits `connection_lost`

Disconnect no longer ends the session. The turn continues (bound to the
registry), the cache persists, and an idle timeout emits a `connection_lost`
event. The session remains recoverable until the cache TTL expires. The
unconditional `end_session` in `ws_handler.py`'s `finally` is removed/replaced
by this TTL-gated lifecycle.

### 7. Lazy cold-start reconciliation

`asyncio.Task` handles do not survive a server restart. On a cold start (or
when a reattach finds `status=streaming` but no live task handle in the
registry), the handler reconciles lazily: it marks the turn `stopped`, persists
the partial output as a stopped turn, and lets the client resume from there.
This keeps the registry in-process-only (Option A) without ever presenting a
stale "still streaming" state to a reattached client.

### Concurrency policy

One active turn per session. A second `user_direction` arriving while a turn is
active is rejected with a `busy` message rather than queued. (A future
enhancement may add a turn queue; out of scope here.)

---

## Explicit end_session semantics

The deletion point for a session is the explicit `end_session` message: the WS
router calls `SessionManager.end_session()`, which deletes the cached entry
(`cache.delete`). Transport disconnects never delete (Decision 6 — reattach
survives until the cache TTL expires). ADR-080 wired `end_session` into the WS
router as the explicit eviction point; the semantics below were sharpened by the
PR #157 review follow-up.

### Race with an in-flight stream

Because the receive loop stays live while a turn streams (Decision 1), an
`end_session` can arrive while the turn task is still running. When the
stream's success tail then calls `add_message`, the session is already evicted
and `_load_or_raise` raises `ValueError` ("Session ... not found or expired.").
The race is **benign by design**:

- The final `ValueError` is deliberately dropped: the assistant message is not
  persisted — no transcript is written for a session after explicit end — and
  the `text_done` frame is skipped. The race is logged at info as
  `direction_stream_session_ended`.
- The turn is **always unregistered**: the success tail runs `unregister` in a
  `finally`, and a last-resort done-callback attached at the dispatch site
  (`direction_stream_task_failed` at error) guarantees registry cleanup even if
  an exception escapes the task body.

### Non-decision (flagged, not resolved)

Explicit `end_session` does **not** cancel in-flight generation. The stream is
allowed to finish at bounded LLM cost; `stop_generation` remains the
cancellation path. Cancelling on `end_session` is listed as a future
consideration, not resolved here.

---

## Rationale

The common thread across all seven decisions is **separating three concerns
that were conflated**: the *connection* (WebSocket accept/close), the *session*
(recoverable, cache-backed, TTL-bounded), and the *active turn* (cancellable
`asyncio.Task`, rebindable sink). ADR-045 already separated *turn orchestration*
(prompt/budget/evidence) from transport; this ADR completes the separation at
the transport/session layer without touching the invocation contract.

The rejected options share a failure mode: they keep the turn coupled to the
connection (inline await, cooperative flag, per-connection cache, eager
`end_session`). Any solution that leaves that coupling intact cannot deliver
true stop or true recovery — it can only improve the illusion. That is why each
chosen option is the boring mechanism that actually breaks the coupling
(`Task.cancel`, `app.state` singleton, URL rebind, TTL-gated lifecycle).

### Trade-offs Accepted

1. **Handles are non-durable.** `asyncio.Task` handles vanish on restart. We
   accept this because serialization is impossible and lazy reconciliation
   (Decision 7) provides the correct fallback without a redundant durable store.

2. **One active turn per session.** Concurrent directions are rejected as
   `busy`. Accepted as a clear, honest contract; a queue is a future enhancement.

3. **In-memory cache is process-local until Redis is wired.** Accepted because
   the `SessionCacheProtocol` already permits the Redis drop-in, and the TTL +
   reconciliation design does not depend on cross-process sharing to be correct.

---

## Consequences

### Positive

- **True server-side stop:** cancel reaches the in-flight `await __anext__()`,
  ending the stream promptly (RULE-20).
- **Reliable recovery:** a dropped connection reattaches to the same session,
  same cache, and — if still streaming — the same turn (rebound sink).
- **Clean separation of concerns:** connection, session, and active turn are
  independently testable, consistent with RULE-06 and the ADR-045 module split.
- **Transport-agnostic reuse:** the registry and sink are WebSocket-agnostic;
  future SSE/MCP/A2A transports can adopt the same primitives (RULE-12/RULE-13).
- **No invocation-contract churn:** ADR-045's turn service, evidence, and budget
  enforcement are preserved unchanged.

### Negative / Trade-offs

- **`asyncio.Task` handles don't survive server restart.** Mitigated by lazy
  cold-start reconciliation (Decision 7); never surfaces as a stale state.
- **Memory footprint until TTL.** Sessions occupy cache/registry memory until
  TTL; requires a sensible TTL and the reconciliation sweep.
- **One active turn per session** (concurrent rejected as `busy`).

### Neutral

- **Reattach identity in the URL.** The session id travels as a query param; it
  is validated server-side and is not sensitive (it is already echoed in the
  greeting).

---

## RULE-XX Compliance

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-03 | ✅ | New boundaries (`ActiveTurnRegistry`, `SessionTransportSink`) are defined as executable Protocols before implementation. |
| RULE-06 | ✅ | Each new concern is a separate module: turn registry, transport sink, reattach resolution. No responsibility is compressed into an existing file. |
| RULE-08 | ✅ | The registry and sink are transport/session infrastructure and live in the Backend (`apps/api`), not in Core. Core's invocation contract is untouched. |
| RULE-11 | ✅ | `CancelledError` and reattach failures are handled deliberately (partial output persisted-as-stopped or discarded per policy); never silently swallowed. |
| RULE-12/RULE-13 | ✅ | Turn scheduling/cancellation/recovery are transport-agnostic; run and stream share one policy. The ADR-045 invocation contract is preserved. |
| RULE-20 | ✅ | Cancel propagates into the blocked `await __anext__()` — a genuine transport effect, not a UI flag flip. |

---

## Sustainability Check

1. **Correct in 3 months?** Yes. The decisions are defined by the
   connection/session/turn separation, not by today's specific socket code.
2. **Hard-to-undo coupling?** No. The registry and sink are Backend-internal
   Protocols; the invocation contract and Core are untouched.
3. **Simplest correct solution?** Yes. Each chosen option is the boring
   mechanism (`Task.cancel`, `app.state` singleton, URL rebind, TTL lifecycle)
   that actually breaks the connection/turn coupling, rather than a novel
   abstraction that would need its own maintenance.
4. **Design intent clear?** Yes. Stop stops; reconnect recovers; restart
   reconciles.

---

## Review Triggers

- [ ] When a turn queue is needed (concurrent directions beyond `busy`).
- [ ] When multi-worker / multi-process deployment requires cross-process turn
      coordination (→ revisit Redis-backed registry/cache; live cancel would
      need an in-process map regardless).
- [ ] When an SSE/MCP/A2A transport adopts these primitives — verify the
      Protocol seam holds.
- [ ] After 3 months — verify stop reliably interrupts slow-provider streams and
      reattach recovers in-field.
