---
id: CR-AUFG-07-21
title: "SessionPanel Server-side Stop and WebSocket Recovery"
status: planned
area: ai-ux
mvp: false
ui_tooltip: "Stop writing-session generation on the server and recover safely after disconnects."
ui_help_short: |
  Interactive sessions will stop the server-side AI stream, preserve partial text,
  and reconnect to the same session state after connection loss when possible.
ui_help_long: |
  The feature hardens SessionPanel from UI-local cancellation to true transport and
  server behavior. Stopping generation reaches the backend stream, and reconnecting
  restores the existing session instead of silently starting over.
ui_available_in: [editor]
service: apps/api/narrare/writing/ws_session_control_service.py
contract: apps/api/narrare/writing/contracts.py#WritingSessionControlProtocol
router: apps/api/narrare/writing/router_sessions.py
prompt: ~
requires: [WRITE-005, ADR-043]
---

# CR-AUFG-07-21 — SessionPanel Server-side Stop and WebSocket Recovery

## Problem / Root cause

**Symptom:** SessionPanel’s “Stop Generation” currently clears local streaming UI state; existing WebSocket reconnection opens a connection again but does not prove same-session recovery or server stream cancellation.

**Warum 1?** Frontend `handleStopGeneration` moves partial text into local messages and sets `isStreaming=false`, but it does not send a stop command that cancels the backend `ModelRegistry.stream()` iterator.

**Warum 2?** The WebSocket route currently creates a new `SessionManager` with a per-route in-memory cache; reconnecting cannot reliably resume durable session state.

**Root cause:** Writing sessions treat WebSocket transport lifecycle as connection-local instead of a recoverable server session with cancellable active turns.

## User-facing behavior and acceptance criteria

- Stop sends a `stop_generation` message and the backend cancels the active turn.
- Server acknowledges with `generation_stopped` including preserved partial prose metadata.
- The session remains active after stop; the writer can continue sending directions.
- If the socket disconnects mid-stream, partial output remains visible and a localized reconnect banner appears.
- Reconnect reattaches to the same server session when the session is still active; it does not create a new session silently.
- If recovery is impossible, the UI explains why and preserves local unsaved prose.

## Architecture fit and layer ownership

| Layer | Ownership |
|-------|-----------|
| Core | Extends `SessionManagerProtocol` only for transport-agnostic session state if needed; core remains HTTP/WebSocket-free. |
| Backend | Owns cancellable active-turn registry, session reattach protocol, message schemas, and Redis-backed session cache injection. |
| Frontend | Owns WebSocket client recovery state, reconnect banner, stop command UI, and partial-output preservation. |
| Platform | Adds WebSocket/session tests and inventory fields for stop/recovery semantics. |
| Docs | Updates WRITE-005 constraints that disconnect no longer always loses unsaved prose. |

## API/contract implications

Contract-first backend additions:

- `WritingSessionControlProtocol.stop_generation(session_id, invocation_id) -> StopGenerationResult`
- `WritingSessionControlProtocol.reattach_session(session_id, user_id, project_id) -> ReattachSessionResult`
- Typed WebSocket messages: `stop_generation`, `generation_stopped`, `recover_session`, `session_recovered`, `recovery_failed`, `connection_lost`.

Frontend `SessionResponse` and `WritingSessionSocket` types must match backend message fields in the same change.

## Data model/migration implications

- No SQL migration expected.
- Session cache state must store `session_id`, `active_invocation_id`, `stream_status`, partial prose buffer, and last sequence number.
- The route must use an injected shared cache implementation rather than a per-connection `InMemorySessionCache` for recovery-capable sessions.

## i18n requirements

- DE/EN/FR keys for reconnecting, recovered, recovery failed, generation stopped, server stop failed, and preserve-local-copy guidance.
- Stop/retry buttons use `studio.aiActions.stop`, `studio.aiActions.retry`, and `studio.aiActions.connectionLostRetry`.

## AI-UX lifecycle requirements

- Loading and streaming states remain visible.
- Cancel/stop must reach server-side stream cancellation; UI-only cancellation is non-compliant.
- Connection loss preserves partial output and offers retry/reconnect per §16.7.
- Errors are actionable and mapped to i18n; no raw WebSocket errors.

## Tests/enforcement gates required

- Backend unit tests for active-turn cancellation and reattach authorization.
- WebSocket integration tests for stop acknowledgement, disconnect/reconnect, sequence replay, and expired-session failure.
- Frontend tests for stop message dispatch, partial output preservation, reconnect banner, and recovery failure copy.
- AI Operation Inventory entry for `writing.session` or expanded WRITE-005 operation fields.

## Alternatives considered

1. **Keep UI-only stop.** Rejected: violates CR-07 guidance and RULE-20 because the server continues work.
2. **Replace WebSocket with SSE.** Rejected: WRITE-005 is bidirectional conversation; transport replacement is larger than the root cause.
3. **Recoverable WebSocket session with server-side stop (chosen).** Best fit: preserves the established transport while fixing true lifecycle semantics.

## Explicit out-of-scope

- Permanent session history beyond existing TTL.
- Multi-device collaborative session editing.
- Changing WRITE-005 prompt semantics.

## Dependencies/order constraints

- Can proceed after CR-AUFG-07-18/24 or independently if prioritized for resilience.
- Must complete before slash commands expose session stop/reconnect commands.
