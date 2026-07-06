# CR-AUFG-07-21 — SessionPanel Server-side Stop and WebSocket Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Commit policy:** This plan contains **NO commit steps** per coordinator instruction. Each task ends with a `Checkpoint` (tests green, ready for review). The coordinator decides when/whether to commit at the end of the whole plan.

**Goal:** Convert SessionPanel's UI-only stop into a real server-side stream cancellation, and turn WebSocket reconnect into same-session recovery (reattach to live session state, preserve partial prose, surface failure honestly) instead of silently creating a new session.

**Architecture:** Three architectural moves, all contract-first:

1. **Decouple streaming from the request task** — `WritingDirectionDispatcher.dispatch` spawns the streaming turn as an `asyncio.Task` registered in an `ActiveTurnRegistry`, then returns immediately. A `WebSocketSink` adapter satisfies a transport-agnostic `SessionTransportSink` Protocol so the streaming task does not own the receive loop.
2. **Server-side cancellation** — `WritingSessionControlService.stop_generation` looks up the active turn by `(session_id, invocation_id)` in the registry, calls `Task.cancel()` (which propagates `asyncio.CancelledError` into `ModelRegistry.stream()` and aborts the underlying LLM stream), reads the partial prose via `SessionTurnStateStore.cancel_active_turn`, and emits `generation_stopped` with the preserved partial text.
3. **Recovery via shared cache + URL-param reattach** — the route receives an injected, app-singleton `SessionCacheProtocol` (no more per-connection `InMemorySessionCache`); a `?session_id=...` query param triggers `WritingSessionControlService.reattach_session`, which delegates to `SessionManager.reattach_session` for ownership/expiry validation and returns either `session_recovered` with the live `SessionState` (incl. active turn + partial prose) or `recovery_failed` with a typed reason. `ws_handler` no longer auto-ends the session on disconnect; idle timeout emits `connection_lost` so the client can recover.

**Tech Stack:** Python 3.14 + FastAPI + Pydantic v2 + asyncio (backend); Next.js 16 + React 19 + TypeScript strict + next-intl (frontend); pytest + Vitest + Testing Library (tests).

**Reference spec:** `docs/features/ai-ux/CR-AUFG-07-21-session-stop-websocket-recovery.md`
**Reference ADR (authored in Pre-Task):** `docs/architecture/decisions/ADR-052-session-stop-recovery.md`

---

## Spec → Plan traceability

| Spec requirement (CR-AUFG-07-21) | Task(s) |
|----------------------------------|---------|
| Stop sends `stop_generation`; backend cancels active turn | 6, 8, 10, 11, 15 |
| Server acks with `generation_stopped` + preserved partial prose metadata | 4, 8, 16 |
| Session stays active after stop; writer can keep directing | 10, 15, 17 |
| Disconnect mid-stream keeps partial output + localized reconnect banner | 29, 31, 32, 33 |
| Reconnect reattaches to same session when still active (no silent new session) | 19, 21, 22, 23, 26, 29 |
| If recovery is impossible, UI explains why + preserves local unsaved prose | 19, 21, 22, 29, 31, 32 |
| Contract: `WritingSessionControlProtocol.stop_generation` + `reattach_session` | 7, 19, 21 |
| Typed WS messages: stop/stopped/recover/recovered/failed/connection_lost | 13, 14, 16, 24, 27, 31 |
| `SessionResponse` + `WritingSessionSocket` types match backend fields | 13, 14, 29, 38 |
| Session cache state: session_id, active_invocation_id, stream_status, partial prose, last sequence | 1, 2, 3, 4 |
| Route uses injected shared cache (not per-connection `InMemorySessionCache`) | 21, 23, 26 |
| DE/EN/FR keys: reconnecting, recovered, recovery failed, generation stopped, server stop failed, preserve-local-copy | 17, 33 |
| Stop/retry buttons use `studio.aiActions.stop`, `.retry`, `.connectionLostRetry` | 17, 33 |
| Backend unit tests for active-turn cancellation + reattach authorization | 5, 8, 12, 19, 20, 27 |
| WebSocket integration tests: stop ack, disconnect/reconnect, sequence replay, expired-session | 35 |
| Frontend tests: stop dispatch, partial preservation, reconnect banner, failure copy | 18, 34 |
| AI Operation Inventory entry for `writing.session` | 37 |
| WRITE-005 update: disconnect no longer always loses unsaved prose | 40 |
| ADR-043 Review-Trigger #1 (WebSocket flow needs lifecycle ADR) fulfilled | Pre-Task |

---

## File structure (decomposition)

### ADR (Pre-Task)
- **Create:** `docs/architecture/decisions/ADR-052-session-stop-recovery.md` — Accepted ADR documenting the three architectural moves.
- **Modify:** `docs/architecture/decisions/INDEX.md` — add ADR-052 row.

### Core (`packages/core/narrare_core/writing/`)
- **Modify:** `_enums.py` — add `StreamStatus`, `ConnectionState` StrEnums.
- **Modify:** `requests.py` — extend `SessionState` with `active_invocation_id`, `stream_status`, `last_sequence`, `active_partial_prose`, `connection_state`.
- **Create:** `session_state_codec.py` — extracted serialize/deserialize helpers (RULE-04: `session_manager.py` is 246 lines; new methods push it over the limit).
- **Create:** `session_turn_state.py` — `SessionTurnStateStore` + `ActiveTurnSnapshot` (in-process registry of the active turn per session).
- **Modify:** `session_manager.py` — delegate serialization to codec; add `reattach_session` (Phase 2).
- **Modify:** `contracts.py` — extend `SessionManagerProtocol` with `reattach_session`.
- **Tests:** `tests/unit/core/writing/test_enums.py` (extend), `test_session_state_codec.py` (NEW), `test_session_turn_state.py` (NEW), `test_session_manager.py` (extend).

### Backend (`apps/api/narrare/writing/`)
- **Create:** `ws_active_turn_registry.py` — `SessionTransportSink` Protocol + `ActiveTurnRegistry` + `ActiveTurn` + `CancelResult` + `NullSessionTransportSink`.
- **Modify:** `contracts.py` — add `WritingSessionControlProtocol`, `StopGenerationStatus`, `ReattachOutcomeKind`.
- **Create:** `ws_session_control_service.py` — `WritingSessionControlService` (stop + reattach).
- **Create:** `ws_sink.py` — `WebSocketSink` adapter (satisfies `SessionTransportSink`).
- **Modify:** `ws_direction_dispatch.py` — spawn streaming as background task, register in registry, busy-guard.
- **Modify:** `ws_streaming.py` — add `StreamChunkRecorder` to forward chunks into `SessionTurnStateStore`.
- **Modify:** `ws_message_router.py` — route `stop_generation` and `recover_session`.
- **Modify:** `ws_handler.py` — accept `session_id` query param, branch create vs. reattach; replace auto-`end_session` in `finally` with `mark_disconnected`; timeout emits `connection_lost`.
- **Modify:** `router_sessions.py` — replace per-connection cache with `deps_ws` accessors; accept `session_id` query param.
- **Modify:** `deps_ws.py` — add `get_session_cache`, `get_session_manager`, `get_active_turn_registry`, `get_turn_state`, `get_session_control_service`.
- **Modify:** `ws_factory.py` — pass `ActiveTurnRegistry` + `turn_state` + `control_service` to dispatcher/router/handler.
- **Modify:** `_app/lifespan.py` — instantiate shared singletons on `app.state`.
- **Tests:** `tests/unit/api/writing/test_ws_active_turn_registry.py`, `test_ws_session_control_service.py`, `test_ws_sink.py`, `test_ws_direction_dispatch_stop.py`, `test_ws_message_router_stop.py`, `test_ws_message_router_recover.py`, `test_writing_contracts_protocol.py` (all NEW); extend `tests/integration/writing/test_session_lifecycle.py`.

### Frontend (`packages/web/`)
- **Modify:** `lib/api/generation.ts` — extend `SessionResponse` type; `WritingSessionSocket` captures `sessionId` from greeting, includes `session_id` in reconnect URL, sends `recover_session` as first message on reconnect.
- **Modify:** `components/studio/editor/useSessionSocket.ts` — add `stop_generation` + `recover_session` to `sendMessage` union; expose `recoveryState`.
- **Modify:** `components/studio/editor/createSessionMessageHandler.ts` — handle `generation_stopped`, `session_recovered`, `recovery_failed`, `connection_lost`; capture `session_id` from greeting.
- **Modify:** `components/studio/editor/SessionPanel.tsx` — `handleStopGeneration` sends `stop_generation`; render reconnect banner with local prose preservation.
- **Create:** `components/studio/editor/SessionReconnectBanner.tsx` — extracted banner (RULE-04).
- **Tests:** `components/studio/editor/__tests__/useSessionSocket.recovery.test.tsx`, `__tests__/createSessionMessageHandler.test.tsx`, `__tests__/SessionReconnectBanner.test.tsx` (NEW); extend `__tests__/SessionPanel.test.tsx`.

### Platform / governance
- **Create:** `tests/integration/writing/test_session_stop_and_recovery.py` — end-to-end stop + recovery.
- **Modify:** `scripts/checks/ai_operation_inventory.yaml` — add `writing.session` operation.
- **Create:** `tests/integration/writing/test_session_message_schema_parity.py` — RULE-17 cross-layer contract test.

### Docs / i18n
- **Modify:** `packages/i18n/messages/{de,en,fr}/studio.json` — add `sessionPanel.reconnecting`, `.recovered`, `.recoveryFailed`, `.generationStopped`, `.serverStopFailed`, `.preserveLocalCopy`, `.connectionLost`; `aiActions.retry`, `aiActions.connectionLostRetry` if missing.
- **Modify:** `docs/features/writing/WRITE-005-interactive-session.md` — update "Constraints & Edge Cases".
- **Modify:** `docs/architecture/governance/aufg-registry.md` — mark CR-AUFG-07-21 `resolved` with exit evidence.

---

## RULE-XX Compliance

| Rule | Status | Evidence in plan |
|------|--------|------------------|
| RULE-01b | PASS | No new LLM imports; `WritingTurnService` keeps using `ModelRegistry.stream()` |
| RULE-02/02a/02b | PASS | No prompt changes; stop/recovery are transport-layer concerns |
| RULE-03 | PASS | `SessionTransportSink`/`WritingSessionControlProtocol` (Tasks 5, 7) BEFORE service (Task 8); `SessionManagerProtocol.reattach_session` (Task 19) before impl |
| RULE-04 | PASS | Each new file has one responsibility; `session_state_codec.py`, `session_turn_state.py`, `ws_active_turn_registry.py`, `ws_session_control_service.py`, `ws_sink.py`, `SessionReconnectBanner.tsx` |
| RULE-05 | PASS | Core (`session_turn_state`) -> Backend (`ws_active_turn_registry`, control service); arrows never reverse |
| RULE-06 | PASS | `WritingSessionControlService` owns stop/reattach; `ActiveTurnRegistry` owns task lifecycle; `WebSocketSink` owns transport adaptation |
| RULE-07 | PASS | router -> control service -> session manager + turn registry -> cache; `core/` imports nothing from `apps/` |
| RULE-08 | PASS | `SessionCacheProtocol` injected; core never imports Redis |
| RULE-09 | PASS | Full type annotations on every Protocol and service method; TS types fully typed |
| RULE-10 | PASS | Every task has a TDD RED-GREEN step with exact command + expected output; integration test (Task 35) covers cross-layer invariants |
| RULE-11 | PASS | Stop without active turn -> typed `StopGenerationStatus.NO_ACTIVE_TURN`; reattach failures -> typed `ReattachOutcomeKind`; no bare `except: pass` |
| RULE-12 | PASS | `WritingSessionControlService` is the single service-layer entry; WS handler delegates to it |
| RULE-13 | PASS | Streaming and stop share `WritingSessionControlProtocol`; non-streaming recovery lives in the same interface |
| RULE-16 | PASS | All new user-facing strings use `studio.sessionPanel.*` / `studio.aiActions.*` keys in DE/EN/FR (Tasks 17, 33) |
| RULE-17 | PASS | Task 38 asserts TS `SessionResponse` <-> Python WS message `type` literals are the same set |
| RULE-20 | PASS | Phase 1 (stop) and Phase 2 (recovery) both ship complete: contracts + service + transport + UI + i18n + tests |
| RULE-22 | PASS | ADR-052 documents the decision and is referenced from code via `# See ADR-052` |
| ADR-043 RT#1 | PASS | ADR-052 is the WebSocket-lifecycle ADR that ADR-043 Review-Trigger #1 explicitly calls for |

---

# Pre-Task: ADR-052 authoring

**Files:**
- Create: `docs/architecture/decisions/ADR-052-session-stop-recovery.md`
- Modify: `docs/architecture/decisions/INDEX.md`

- [ ] **Step 1: Author ADR-052**

Create `docs/architecture/decisions/ADR-052-session-stop-recovery.md` with Status `Accepted`, Date `2026-06-22`, Deciders `Architecture Specialist`. The body MUST cover:

- **Context:** CR-AUFG-07-21 symptom (UI-only stop, per-connection cache -> reconnect starts fresh) -> 2x "Warum?" -> root cause (transport lifecycle treated as connection-local instead of recoverable server session with cancellable active turns). Cite ADR-043 Review-Trigger #1 (WebSocket flow needs its own lifecycle ADR) and ADR-045 Decision 6 (turn-service/transport split).
- **Decision drivers:** RULE-03, RULE-04, RULE-11, RULE-12, RULE-17, RULE-20, Section 16.2/16.7, ADR-043 RT#1.
- **Options considered (minimum 3):**
  1. Keep UI-only stop + accept silent reconnect. Rejected: violates Section 16.2 + RULE-20.
  2. Replace WebSocket with SSE + REST stop. Rejected: WRITE-005 is bidirectional; transport swap is bigger than the root cause.
  3. Decoupled streaming task + swappable sink + shared cache + URL-param reattach (chosen).
- **Decision:** Option 3. Three architectural moves (decoupled streaming task; server-side cancellation via `Task.cancel` + `ActiveTurnRegistry`; shared cache + `?session_id=` reattach).
- **Rationale:** Why Option 3 over Option 2 (preserves bidirectional transport, fixes true lifecycle); trade-offs accepted (in-process `ActiveTurnRegistry` is single-process; document as future Redis-backed enhancement).
- **Consequences:** Positive (real cancellation, durable recovery, swappable sink enables MCP/SSE adapter later); Negative (registry is in-process - multi-worker deployments need Redis-backed registry; called out in Review Trigger).
- **Constraints introduced:** References RULE-03, RULE-04, RULE-11, RULE-12, RULE-17, RULE-20; cross-links ADR-043 RT#1, ADR-045.
- **Implementation notes:** Point at `ws_active_turn_registry.py`, `ws_session_control_service.py`, `ws_sink.py`, `session_turn_state.py`, `router_sessions.py` (`?session_id=`), `ws_handler.py` (reattach branch).
- **Review Trigger:**
  - [ ] When the API runs with >1 worker process (-> Redis-backed `ActiveTurnRegistry`).
  - [ ] When a non-WebSocket client (MCP, CLI) needs writing-session lifecycle (-> reuse `WritingSessionControlProtocol` via new adapter).
  - [ ] After 3 months - verify stop reaches the LLM provider's stream-cancel endpoint.

- [ ] **Step 2: Add ADR-052 to INDEX.md**

Append after the ADR-051 row in the Decision Log table:

```markdown
| [ADR-052](ADR-052-session-stop-recovery.md) | SessionPanel Server-side Stop and WebSocket Recovery | PASS-Accepted | 2026-06-22 | `apps/api/narrare/writing/ws_*`, `packages/core/narrare_core/writing/session_*`, `packages/web/components/studio/editor/*`, WRITE-005, CR-AUFG-07-21, ADR-043 RT#1 |
```

- [ ] **Step 3: Checkpoint**

Verify: `grep -n "ADR-052" docs/architecture/decisions/INDEX.md` returns the new row. ADR-052 file exists and contains all required sections.

---

# Phase 1 - Server-side Stop

## Task 1: Core - `StreamStatus` + `ConnectionState` enums

**Files:**
- Modify: `packages/core/narrare_core/writing/_enums.py`
- Test: `tests/unit/core/writing/test_enums.py` (extend)

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/core/writing/test_enums.py`:

```python
from narrare_core.writing._enums import ConnectionState, StreamStatus


class TestStreamStatus:
    def test_members(self) -> None:
        assert {m.value for m in StreamStatus} == {
            "idle", "streaming", "stopped", "completed", "failed",
        }

    def test_round_trip(self) -> None:
        for m in StreamStatus:
            assert StreamStatus(m.value) is m


class TestConnectionState:
    def test_members(self) -> None:
        assert {m.value for m in ConnectionState} == {
            "connected", "disconnected", "reattaching", "expired",
        }

    def test_round_trip(self) -> None:
        for m in ConnectionState:
            assert ConnectionState(m.value) is m
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/unit/core/writing/test_enums.py::TestStreamStatus -v`
Expected: FAIL - `ImportError: cannot import name 'StreamStatus'`.

- [ ] **Step 3: Write the minimal implementation**

Append to `packages/core/narrare_core/writing/_enums.py`:

```python
class StreamStatus(StrEnum):
    """Lifecycle of a single streaming turn within a writing session.

    Transitions: idle -> streaming -> completed | stopped | failed
    """

    IDLE = "idle"
    STREAMING = "streaming"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"


class ConnectionState(StrEnum):
    """Transport connection state for a writing session (ADR-052).

    A reattach request is only valid when the cached state is ``connected``
    or ``disconnected`` (not ``expired``).
    """

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    REATTACHING = "reattaching"
    EXPIRED = "expired"
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/unit/core/writing/test_enums.py -v`
Expected: PASS.

- [ ] **Step 5: Checkpoint**

Core enum layer done.

---

## Task 2: Core - extend `SessionState` with recovery fields

**Files:**
- Modify: `packages/core/narrare_core/writing/requests.py`
- Test: `tests/unit/core/writing/test_session_manager.py` (extend `TestSerialization`)

- [ ] **Step 1: Write the failing tests**

Append to the `TestSerialization` class in `tests/unit/core/writing/test_session_manager.py`:

```python
    async def test_new_recovery_fields_default_correctly(self, manager: SessionManager) -> None:
        chapter_id, project_id, user_id = _uuids()
        session_id = await manager.create_session(chapter_id, project_id, user_id)

        state = await manager.get_session(session_id)
        assert state is not None
        assert state.active_invocation_id is None
        assert state.stream_status.value == "idle"
        assert state.last_sequence == 0
        assert state.active_partial_prose == ""
        assert state.connection_state.value == "connected"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/unit/core/writing/test_session_manager.py::TestSerialization::test_new_recovery_fields_default_correctly -v`
Expected: FAIL - `AttributeError`.

- [ ] **Step 3: Extend `SessionState`**

In `packages/core/narrare_core/writing/requests.py`, add `StreamStatus`/`ConnectionState` to the TYPE_CHECKING import block, and append fields to `SessionState`:

```python
@dataclass(slots=True)
class SessionState:
    """State of an interactive writing session.

    Recovery fields (ADR-052) are populated by the backend control service
    during streaming/stop/reattach; core treats them as opaque state.
    """

    session_id: UUID
    chapter_id: UUID
    project_id: UUID
    user_id: UUID
    conversation_history: list[dict[str, str]] = field(
        default_factory=list[dict[str, str]],
    )
    prose_buffer: str = ""
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_activity: datetime = field(default_factory=lambda: datetime.now(UTC))
    is_active: bool = True

    # --- ADR-052 recovery fields ---
    active_invocation_id: UUID | None = None
    stream_status: StreamStatus = field(default_factory=lambda: _default_stream_status())
    last_sequence: int = 0
    active_partial_prose: str = ""
    connection_state: ConnectionState = field(
        default_factory=lambda: _default_connection_state(),
    )


def _default_stream_status() -> StreamStatus:
    from narrare_core.writing._enums import StreamStatus
    return StreamStatus.IDLE


def _default_connection_state() -> ConnectionState:
    from narrare_core.writing._enums import ConnectionState
    return ConnectionState.CONNECTED
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/unit/core/writing/test_session_manager.py::TestSerialization::test_new_recovery_fields_default_correctly -v`
Expected: PASS. (Round-trip of new fields is fixed in Task 3.)

- [ ] **Step 5: Checkpoint**

Default-fields test green. Codec extraction (Task 3) handles serialization round-trip.

---

## Task 3: Core - extract `session_state_codec.py` and teach it the new fields

**Files:**
- Create: `packages/core/narrare_core/writing/session_state_codec.py`
- Modify: `packages/core/narrare_core/writing/session_manager.py` (delegate `_serialize`/`_deserialize` to codec)
- Test: `tests/unit/core/writing/test_session_state_codec.py` (NEW)

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/core/writing/test_session_state_codec.py`. The suite must cover: (a) serialize includes recovery fields, (b) round-trip preserves all fields, (c) legacy payloads without recovery fields deserialize with defaults (back-compat), (d) `SessionStateCodec` object form works. Pattern follows the existing `test_session_manager.py::TestSerialization` style. Use `_make_state(**overrides)` helper that builds a `SessionState` with random UUIDs.

Key assertions for the round-trip test:

```python
def test_round_trip_preserves_all_fields(self) -> None:
    invocation = uuid4()
    original = _make_state(
        active_invocation_id=invocation,
        stream_status=StreamStatus.STREAMING,
        last_sequence=9,
        active_partial_prose="abc",
        connection_state=ConnectionState.DISCONNECTED,
    )
    round_tripped = deserialize_session_state(serialize_session_state(original))
    assert round_tripped.active_invocation_id == invocation
    assert round_tripped.stream_status is StreamStatus.STREAMING
    assert round_tripped.last_sequence == 9
    assert round_tripped.active_partial_prose == "abc"
    assert round_tripped.connection_state is ConnectionState.DISCONNECTED
```

Legacy test: build a dict WITHOUT the recovery keys, `json.dumps` it, call `deserialize_session_state`, assert all recovery fields defaulted.

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/unit/core/writing/test_session_state_codec.py -v`
Expected: FAIL - `ImportError`.

- [ ] **Step 3: Implement the codec**

Create `packages/core/narrare_core/writing/session_state_codec.py` with:

- `serialize_session_state(state) -> str` - JSON-encodes all fields including the five ADR-052 recovery fields. `active_invocation_id` becomes `null` or its string form; `stream_status`/`connection_state` are stored as their `.value` strings.
- `deserialize_session_state(raw) -> SessionState` - uses `data.get(key, default)` for every recovery field so legacy payloads work.
- `class SessionStateCodec` - object form with `serialize`/`deserialize` delegating to the functions.

Internal helpers `_state_to_dict(state)` and `_dict_to_state(data)` carry the field mapping. Imports of `SessionState`, `StreamStatus`, `ConnectionState` happen inside the functions (or under TYPE_CHECKING) to avoid module-load cycles.

- [ ] **Step 4: Delegate `SessionManager` serialization to the codec**

In `packages/core/narrare_core/writing/session_manager.py`, replace the bodies of `_serialize` and `_deserialize`:

```python
    def _serialize(self, state: SessionState) -> str:
        from narrare_core.writing.session_state_codec import serialize_session_state
        return serialize_session_state(state)

    def _deserialize(self, raw: str) -> SessionState:
        from narrare_core.writing.session_state_codec import deserialize_session_state
        return deserialize_session_state(raw)
```

Remove now-unused top-level imports (`json`, and `datetime`/`UTC` if no longer referenced elsewhere in the file - verify with `grep`). Keep `UUID`/`uuid4` if still used by `create_session`.

- [ ] **Step 5: Run all core tests to verify the refactor**

Run: `pytest tests/unit/core/writing/test_session_state_codec.py tests/unit/core/writing/test_session_manager.py -v`
Expected: PASS (all new codec tests + all pre-existing `test_session_manager.py` tests including the round-trip from Task 2).

- [ ] **Step 6: Checkpoint**

Codec extraction keeps `session_manager.py` under its RULE-04 budget and the round-trip works for both legacy and ADR-052 payloads.

---

## Task 4: Core - `SessionTurnStateStore` for active-turn partial prose

**Files:**
- Create: `packages/core/narrare_core/writing/session_turn_state.py`
- Test: `tests/unit/core/writing/test_session_turn_state.py` (NEW)

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/core/writing/test_session_turn_state.py` with three test classes:

- `TestRegisterAndRecord`: `register_active_turn` returns snapshot with `sequence=0`, empty `partial_prose`; `record_chunk` appends text and increments `sequence`; `record_chunk` with no active turn is a no-op.
- `TestFinalizeAndCancel`: `finalize_turn` clears the turn and returns full prose; `cancel_active_turn` clears and returns partial prose; both return empty string when no active turn exists.
- `TestGetActivePartial`: returns current partial prose; returns empty string when no active turn.

Use `session_id`/`invocation_id` as strings (UUIDs stringified).

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/unit/core/writing/test_session_turn_state.py -v`
Expected: FAIL - `ImportError`.

- [ ] **Step 3: Implement `SessionTurnStateStore`**

Create `packages/core/narrare_core/writing/session_turn_state.py`:

- `@dataclass(slots=True) class ActiveTurnSnapshot` with `invocation_id: str`, `sequence: int`, `partial_prose: str`.
- `class SessionTurnStateStore` with async methods: `register_active_turn(session_id, invocation_id) -> ActiveTurnSnapshot`, `record_chunk(session_id, text) -> None`, `finalize_turn(session_id) -> str`, `cancel_active_turn(session_id) -> str`, `get_active_partial(session_id) -> str`, `get_active_snapshot(session_id) -> ActiveTurnSnapshot | None`. All async so a future Redis-backed impl satisfies the same surface.

Module docstring must call out: in-process by design; multi-worker follow-up is ADR-052 Review Trigger #1.

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/unit/core/writing/test_session_turn_state.py -v`
Expected: PASS (10 tests).

- [ ] **Step 5: Checkpoint**

Core Phase-1 work complete: enums, extended `SessionState`, codec, turn-state store.

---

## Task 5: Backend - `SessionTransportSink` Protocol + `ActiveTurnRegistry`

**Files:**
- Create: `apps/api/narrare/writing/ws_active_turn_registry.py`
- Test: `tests/unit/api/writing/test_ws_active_turn_registry.py` (NEW)

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/api/writing/test_ws_active_turn_registry.py`. The suite covers:

- `RecordingSink` (with `async send_json`) and `NullSessionTransportSink` both satisfy the `SessionTransportSink` Protocol (`isinstance(x, SessionTransportSink)` returns True - the Protocol is `@runtime_checkable`).
- `register(session_id, invocation_id, task=..., sink=...)` stores the turn; `get(session_id)` returns the `ActiveTurn` with the stored `task` and `sink`; `get_sink(session_id)` returns the sink.
- `cancel(session_id, partial_prose=...)` pops the turn, calls `task.cancel()`, returns `CancelResult(cancelled=True, partial_prose=...)`. The underlying `asyncio.Task` actually receives `CancelledError` (assert via an `asyncio.Event` set in a `try/except asyncio.CancelledError` inside the task body).
- `cancel(session_id, ...)` with no active turn returns `CancelResult(cancelled=False, partial_prose="")`.
- `unregister(session_id)` removes a completed turn without cancelling.

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/unit/api/writing/test_ws_active_turn_registry.py -v`
Expected: FAIL - `ImportError`.

- [ ] **Step 3: Implement the registry + sink Protocol**

Create `apps/api/narrare/writing/ws_active_turn_registry.py`:

- `@runtime_checkable class SessionTransportSink(Protocol)` with `async def send_json(self, data: dict[str, object]) -> None`.
- `class NullSessionTransportSink` - discards sends (used in tests / when client is gone).
- `@dataclass(slots=True) class ActiveTurn` with `invocation_id: str`, `task: asyncio.Task[str | None]`, `sink: SessionTransportSink`.
- `@dataclass(slots=True, frozen=True) class CancelResult` with `cancelled: bool`, `partial_prose: str`.
- `class ActiveTurnRegistry` with `register`, `get`, `get_sink`, `cancel(session_id, *, partial_prose) -> CancelResult`, `unregister`. Single-process by design (ADR-052 RT#1 covers the Redis-backed follow-up).

Module docstring explains the cancellation propagation into `ModelRegistry.stream()` via `CancelledError`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/unit/api/writing/test_ws_active_turn_registry.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Checkpoint**

Backend transport-agnostic primitives (sink Protocol, registry) ready for the control service.

---

## Task 6: Backend - verify direct imports resolve

**Files:** (no file changes - verification only)

- [ ] **Step 1: Verify imports**

Run: `python -c "from narrare.writing.ws_active_turn_registry import SessionTransportSink, ActiveTurnRegistry, ActiveTurn, CancelResult, NullSessionTransportSink; print('ok')"`
Expected: prints `ok`.

If the writing module `__init__.py` re-exports contracts, optionally add the new symbols; otherwise direct imports suffice. Read `apps/api/narrare/writing/__init__.py` first and follow its convention.

- [ ] **Step 2: Checkpoint**

Call-sites in Tasks 8, 10 can import directly from `ws_active_turn_registry`.

---

## Task 7: Backend - `WritingSessionControlProtocol` (contract first, RULE-03)

**Files:**
- Modify: `apps/api/narrare/writing/contracts.py`
- Test: `tests/unit/api/writing/test_writing_contracts_protocol.py` (NEW)

- [ ] **Step 1: Write the failing test (structural Protocol check)**

Create `tests/unit/api/writing/test_writing_contracts_protocol.py`. Two classes - one with both `stop_generation` and `reattach_session` async methods (satisfies the Protocol), one missing `reattach_session` (does NOT satisfy). Assert via `isinstance`.

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/unit/api/writing/test_writing_contracts_protocol.py -v`
Expected: FAIL - `ImportError`.

- [ ] **Step 3: Add the Protocol + status vocabularies**

In `apps/api/narrare/writing/contracts.py`, append:

```python
class StopGenerationStatus:
    STOPPED = "stopped"
    NO_ACTIVE_TURN = "no_active_turn"


class ReattachOutcomeKind:
    RECOVERED = "recovered"
    NOT_FOUND = "not_found"
    EXPIRED = "expired"
    OWNERSHIP_MISMATCH = "ownership_mismatch"


@runtime_checkable
class WritingSessionControlProtocol(Protocol):
    """Service-layer control surface for writing sessions (ADR-052)."""

    async def stop_generation(
        self,
        session_id: UUID,
        invocation_id: UUID,
    ) -> dict[str, object]: ...

    async def reattach_session(
        self,
        session_id: UUID,
        user_id: UUID,
        project_id: UUID,
    ) -> dict[str, object]: ...
```

Docstrings must specify the shape of the returned dicts (`status`, `partial_prose`, `invocation_id` for stop; `kind` discriminator + state snapshot fields for reattach).

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/unit/api/writing/test_writing_contracts_protocol.py -v`
Expected: PASS.

- [ ] **Step 5: Checkpoint**

Contract on disk BEFORE the service (Task 8) - RULE-03 satisfied.

---

## Task 8: Backend - `WritingSessionControlService` implementation

**Files:**
- Create: `apps/api/narrare/writing/ws_session_control_service.py`
- Test: `tests/unit/api/writing/test_ws_session_control_service.py` (NEW)

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/api/writing/test_ws_session_control_service.py`. Reuse the `InMemoryCache` helper from `tests/unit/core/writing/test_session_manager.py` (import it). Fixtures: `cache`, `session_manager`, `turn_state`, `registry`, `service`. `_seed_session(session_manager)` helper creates a session and returns `(session_id_str, project_id_str, user_id_str)`.

Test classes:

- `TestStopGeneration::test_stop_with_active_turn_returns_stopped_and_partial` - register a fake streaming task that sleeps (so it can be cancelled); call `service.stop_generation`; assert `status == "stopped"`, `partial_prose` matches the chunks recorded in `turn_state`, task is cancelled or done, turn state is cleared.
- `TestStopGeneration::test_stop_without_active_turn_returns_no_active_turn` - call stop on a session with no active turn; assert `status == "no_active_turn"`, `partial_prose == ""`.
- `TestReattachSession::test_reattach_live_session_returns_recovered` - assert `kind == "recovered"` and `session_id` matches.
- `TestReattachSession::test_reattach_missing_session_returns_not_found` - random UUID; assert `kind == "not_found"`.
- `TestReattachSession::test_reattach_wrong_user_returns_ownership_mismatch` - assert `kind == "ownership_mismatch"`.
- `TestReattachSession::test_reattach_inactive_session_returns_expired` - flip `is_active=False` in the cache JSON; assert `kind == "expired"`.

> Implementation note: at this stage `WritingSessionControlService.reattach_session` can read the cache directly via `self._session_manager._cache.get(self._session_manager._cache_key(session_id))` (private access) to distinguish not-found vs expired. Task 19 replaces this with a clean public `SessionManager.reattach_session` delegation. The tests assert on `kind` only, so they keep passing after Task 19.

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/unit/api/writing/test_ws_session_control_service.py -v`
Expected: FAIL - `ImportError`.

- [ ] **Step 3: Implement the service**

Create `apps/api/narrare/writing/ws_session_control_service.py`:

- `class WritingSessionControlService(WritingSessionControlProtocol)` with `__init__(*, session_manager, turn_state, registry)`.
- `async def stop_generation(session_id, invocation_id) -> dict[str, object]`:
  1. `partial = await self._turn_state.cancel_active_turn(str(session_id))`
  2. `result = self._registry.cancel(str(session_id), partial_prose=partial)`
  3. If `result.cancelled`: return `{"status": "stopped", "partial_prose": partial, "invocation_id": str(invocation_id)}` and log `stop_generation_cancelled`.
  4. Else: return `{"status": "no_active_turn", "partial_prose": "", "invocation_id": str(invocation_id)}` and log `stop_generation_no_active_turn`.
- `async def reattach_session(session_id, user_id, project_id) -> dict[str, object]`:
  1. `state = await self._session_manager.get_session(session_id)`
  2. If `state is None`: load raw cache payload via the private helpers; if raw is None return `not_found`, else return `expired`.
  3. If `state.user_id != user_id or state.project_id != project_id`: log + return `ownership_mismatch`.
  4. Else: read `turn_state.get_active_snapshot` for the `has_active_turn` flag; return the `recovered` dict with all state snapshot fields.
- Private helper `_load_raw_or_none(session_id)` performs the cache-keyed read.

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/unit/api/writing/test_ws_session_control_service.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Checkpoint**

Service layer complete. Task 19 cleans up the private cache access by delegating to `SessionManager.reattach_session`.

---

## Task 9: Backend - `WebSocketSink` adapter

**Files:**
- Create: `apps/api/narrare/writing/ws_sink.py`
- Test: `tests/unit/api/writing/test_ws_sink.py` (NEW)

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/api/writing/test_ws_sink.py`. `FakeWebSocket` with `async send_json` (appends to a list) and `async close`. Tests:
- `WebSocketSink(FakeWebSocket())` satisfies `SessionTransportSink` Protocol.
- `send_json` delegates to the underlying websocket.
- `send_json` swallows transport errors (a `BrokenSocket` whose `send_json` raises does not propagate - disconnects are expected during stop/cancel).

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/unit/api/writing/test_ws_sink.py -v`
Expected: FAIL - `ImportError`.

- [ ] **Step 3: Implement the adapter**

Create `apps/api/narrare/writing/ws_sink.py`:

- `_WebSocketLike(Protocol)` with `async def send_json`.
- `class WebSocketSink`: `__init__(websocket)`, `async def send_json(data)` wraps the call in `try/except Exception` and logs at debug level on failure (the registry handles cancellation; transport errors here are expected).

Module docstring explains: the sink keeps the streaming code transport-agnostic so a future SSE/MCP adapter can satisfy `SessionTransportSink` without changing the dispatcher.

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/unit/api/writing/test_ws_sink.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Checkpoint**

Transport adapter complete.

---

## Task 10: Backend - refactor `WritingDirectionDispatcher.dispatch` to spawn a decoupled streaming task

**Files:**
- Modify: `apps/api/narrare/writing/ws_direction_dispatch.py`
- Modify: `apps/api/narrare/writing/ws_streaming.py` (add `StreamChunkRecorder`)
- Modify: `apps/api/narrare/writing/ws_factory.py` (wire new dependencies)
- Test: `tests/unit/api/writing/test_ws_direction_dispatch_stop.py` (NEW)

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/api/writing/test_ws_direction_dispatch_stop.py`. `_FakeTurnService.stream_turn(**kwargs)` returns an async iterator yielding two `StreamChunk(text=...)` values then awaiting `asyncio.sleep(10)` (so the task can be cancelled). Fixtures: `session_manager` (real `SessionManager` with `InMemoryCache`), `turn_state`, `registry`, `dispatcher` (constructed with the new `turn_state` + `registry` parameters).

Tests:
- `test_dispatch_registers_active_turn_and_streams_into_sink`: after `dispatch` returns the invocation_id, the registry has an active turn for the session, and `turn_state.get_active_partial` matches the yielded chunks. Cleanup cancels the background task.
- `test_dispatch_rejects_concurrent_direction`: a second `dispatch` while one is streaming sends an error message to the sink mentioning "already" and does NOT register a second task.

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/unit/api/writing/test_ws_direction_dispatch_stop.py -v`
Expected: FAIL - `WritingDirectionDispatcher.__init__` does not accept `turn_state`/`registry`; `dispatch` does not return an invocation_id.

- [ ] **Step 3: Add `StreamChunkRecorder` to `ws_streaming.py`**

Read `apps/api/narrare/writing/ws_streaming.py` first to understand the existing `send_stream_chunks` signature and `StreamSender` alias. Append a class:

```python
class StreamChunkRecorder:
    """Wraps an AsyncIterator[StreamChunk] and records each chunk's text into
    the SessionTurnStateStore (ADR-052)."""

    def __init__(self, turn_state: SessionTurnStateStore, session_id: str) -> None:
        self._turn_state = turn_state
        self._session_id = session_id

    def wrap(self, upstream: AsyncIterator[StreamChunk]) -> AsyncIterator[StreamChunk]:
        return self._record(upstream)

    async def _record(self, upstream):
        async for chunk in upstream:
            if chunk.text:
                await self._turn_state.record_chunk(self._session_id, chunk.text)
            yield chunk
```

Add the needed TYPE_CHECKING imports.

- [ ] **Step 4: Refactor `WritingDirectionDispatcher`**

Rewrite `apps/api/narrare/writing/ws_direction_dispatch.py`. The new class:

- `__init__(session_manager, turn_state, registry, turn_service, api_key=None, base_url=None)`.
- `async def dispatch(websocket, context, content) -> UUID | None`:
  1. Busy guard: if `self._registry.get(session_id_str)` is not None, send an error mentioning "already in progress" and return None.
  2. `await self._session_manager.add_message(context.session_id, "user", content)`.
  3. `invocation_id = uuid4()`.
  4. `await self._turn_state.register_active_turn(session_id_str, str(invocation_id))`.
  5. `await self._mark_stream_status(context.session_id, StreamStatus.STREAMING)`.
  6. `task = asyncio.ensure_future(self._run_stream(websocket, context, content, invocation_id))`.
  7. `self._registry.register(session_id_str, str(invocation_id), task=task, sink=WebSocketSink(websocket))`.
  8. Return `invocation_id`.
- `async def _run_stream(websocket, context, content, invocation_id) -> str | None`: wraps `_stream_into_sink` in `try/except`. On `asyncio.CancelledError`: mark `StreamStatus.STOPPED`, log, re-raise. On `WritingError`/`Exception`: mark `StreamStatus.FAILED`, finalize turn, unregister, send error. On success: finalize turn, unregister, mark `StreamStatus.COMPLETED`, add assistant message, send `text_done`.
- `async def _stream_into_sink(websocket, context, content)`: build a `StreamChunkRecorder`, wrap the `turn_service.stream_turn(...)` iterator, delegate to `send_stream_chunks`.
- `async def _mark_stream_status(session_id, status)`: best-effort load -> mutate `stream_status` -> persist via `self._session_manager._persist(state)` (same-layer access; logged at debug if it fails).

Module helpers: `_safe_send(websocket, data)`, `_adapt_sink(websocket)` returning `WebSocketSink(websocket)`.

- [ ] **Step 5: Update `ws_factory.py`**

In `apps/api/narrare/writing/ws_factory.py`, extend `build_writing_session_handler` to accept `registry`, `turn_state`, `control_service` keyword arguments and pass them through to `WritingDirectionDispatcher`, `WritingSessionMessageRouter`, and `WritingSessionHandler`. Update TYPE_CHECKING imports accordingly. The router accepts the new `control_service` parameter (Task 11); the handler accepts `control_service` (Task 22).

- [ ] **Step 6: Run the test to verify it passes**

Run: `pytest tests/unit/api/writing/test_ws_direction_dispatch_stop.py -v`
Expected: PASS (2 tests).

- [ ] **Step 7: Run all writing tests**

Run: `pytest tests/unit/api/writing/ tests/integration/writing/test_session_lifecycle.py -v`
Expected: PASS. If `test_session_lifecycle.py` calls `build_writing_session_handler` directly, update its call-site to pass the new arguments; if it uses the TestClient (no direct factory call), it should still pass because the router is wired via the new `deps_ws` accessors (Task 23) - but those land in Task 21+23. For now, if integration tests fail because the factory signature changed, defer them to Task 27 (Phase 2 sweep).

- [ ] **Step 8: Checkpoint**

Stop pipeline plumbing complete: dispatcher spawns decoupled task + records chunks; factory wires the new dependencies.

---

## Task 11: Backend - route `stop_generation` in `WritingSessionMessageRouter`

**Files:**
- Modify: `apps/api/narrare/writing/ws_message_router.py`
- Test: `tests/unit/api/writing/test_ws_message_router_stop.py` (NEW)

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/api/writing/test_ws_message_router_stop.py`. Stub classes:
- `_RecordingSocket` with `async send_json`.
- `_StubControl` implementing `WritingSessionControlProtocol`: `stop_generation` returns a configured result dict and captures the invocation_id; `reattach_session` returns `{"kind": "not_found"}`.
- `_DummySessionManager`, `_DummyDispatcher`.
- `_make_router(control)` constructs `WritingSessionMessageRouter` with the new `control_service` parameter (and dummy values for the others).

Tests:
- `test_route_stop_generation_calls_control_and_emits_generation_stopped`: send `{"type": "stop_generation", "invocation_id": "i-1"}`; assert `control.received_invocation == "i-1"` and the socket received `{"type": "generation_stopped", "status": ..., "partial_prose": ..., "invocation_id": "i-1"}`.
- `test_route_stop_generation_with_missing_invocation_sends_error`: send `{"type": "stop_generation"}`; assert an error message was sent.

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/unit/api/writing/test_ws_message_router_stop.py -v`
Expected: FAIL - `WritingSessionMessageRouter.__init__` does not accept `control_service`.

- [ ] **Step 3: Update `WritingSessionMessageRouter`**

In `apps/api/narrare/writing/ws_message_router.py`:

1. Add `control_service: WritingSessionControlProtocol` to `__init__` (right after `direction_dispatcher`). Store as `self._control_service`. Add the TYPE_CHECKING import.
2. In `route()`, add a branch before the final `else`:

```python
        elif msg_type == "stop_generation":
            await self._route_stop_generation(websocket, context, data)
```

3. Add `_route_stop_generation`:
   - Validate `data["invocation_id"]` is a string and parses as UUID; otherwise send an error and return.
   - Call `self._control_service.stop_generation(context.session_id, invocation_id)`.
   - Send `{"type": "generation_stopped", "status": result.get("status"), "partial_prose": result.get("partial_prose", ""), "invocation_id": result.get("invocation_id", invocation_id_raw)}`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/unit/api/writing/test_ws_message_router_stop.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Checkpoint**

Phase-1 backend stop pipeline complete end-to-end (router -> control service -> registry/turn-state -> cancel). The receive loop is no longer blocked by streaming.

---

## Task 12: Backend - Phase 1 unit test sweep

- [ ] **Step 1: Run the full Phase-1 backend test suite**

Run: `pytest tests/unit/api/writing/test_ws_active_turn_registry.py tests/unit/api/writing/test_ws_session_control_service.py tests/unit/api/writing/test_ws_sink.py tests/unit/api/writing/test_ws_direction_dispatch_stop.py tests/unit/api/writing/test_ws_message_router_stop.py tests/unit/api/writing/test_writing_contracts_protocol.py -v`
Expected: PASS (all).

- [ ] **Step 2: Run `just check-architecture`**

Run: `just check-architecture`
Expected: PASS. Verify new files stay under RULE-04 size limits (each ~250 lines).

- [ ] **Step 3: Checkpoint**

Phase-1 backend done. Stop pipeline is contract-complete, tested, and RULE-compliant.

---

## Task 13: Frontend - extend `SessionResponse` type with stop/recovery messages

**Files:**
- Modify: `packages/web/lib/api/generation.ts`

- [ ] **Step 1: Extend the type union**

In `packages/web/lib/api/generation.ts`, replace the `SessionResponse` interface so the `type` union includes `"generation_stopped" | "session_recovered" | "recovery_failed" | "connection_lost"`. Add optional fields: `status?: "stopped" | "no_active_turn"`, `partial_prose?: string`, `invocation_id?: string`, `session_id?: string`, `kind?: "recovered" | "not_found" | "expired" | "ownership_mismatch"`, `last_sequence?: number`, `active_partial_prose?: string`.

- [ ] **Step 2: Verify type-check**

Run: `cd packages/web && npx tsc --noEmit`
Expected: PASS.

- [ ] **Step 3: Checkpoint**

Type extended.

---

## Task 14: Frontend - add `stop_generation` + `recover_session` to `sendMessage`

**Files:**
- Modify: `packages/web/components/studio/editor/useSessionSocket.ts`

- [ ] **Step 1: Extend the `sendMessage` type union and body**

Add `"stop_generation" | "recover_session"` to the type union. Add an optional `extra?: { readonly invocation_id?: string; readonly session_id?: string }` third argument. In the body: `stop_generation` sends `{type, invocation_id: extra?.invocation_id}`; `recover_session` sends `{type, session_id: extra?.session_id}`.

- [ ] **Step 2: Run the existing test**

Run: `cd packages/web && npx vitest run components/studio/editor/__tests__/useSessionSocket.test.tsx`
Expected: PASS (no behaviour change yet).

- [ ] **Step 3: Checkpoint**

Outbound API extended.

---

## Task 15: Frontend - `handleStopGeneration` sends `stop_generation`

**Files:**
- Modify: `packages/web/components/studio/editor/SessionPanel.tsx`

- [ ] **Step 1: Update `handleStopGeneration`**

Keep the optimistic local clear (move partial prose into messages, clear streaming state, set `isStreaming=false`). Add `sendMessage("stop_generation")` at the end of the callback. Update the `useCallback` dependency array to include `sendMessage`.

Docstring: "Sends stop_generation to the server (ADR-052). Optimistic local clear; the server ack (generation_stopped) is reconciled in createSessionMessageHandler."

- [ ] **Step 2: Run the SessionPanel test**

Run: `cd packages/web && npx vitest run __tests__/SessionPanel.test.tsx`
Expected: PASS. If the existing test asserted `sendMessage` was NOT called on stop, update the assertion to expect `stop_generation`.

- [ ] **Step 3: Checkpoint**

Stop dispatch wired.

---

## Task 16: Frontend - handle `generation_stopped` in `createSessionMessageHandler`

**Files:**
- Modify: `packages/web/components/studio/editor/createSessionMessageHandler.ts`

- [ ] **Step 1: Add the `generation_stopped` case**

In the `switch (msg.type)` block, before `case "error":`:

```typescript
      case "generation_stopped": {
        const serverPartial = msg.partial_prose ?? "";
        streamingTextRef.current = "";
        setStreamingText("");
        setIsStreaming(false);
        if (serverPartial) {
          setMessages((prev) => [
            ...prev,
            { id: createMessageId(), role: "assistant", content: "", prose: serverPartial },
          ]);
        }
        break;
      }
```

- [ ] **Step 2: Checkpoint**

Test for this case is added in Task 18 (`createSessionMessageHandler.test.tsx`).

---

## Task 17: i18n - Phase 1 stop keys (DE/EN/FR)

**Files:**
- Modify: `packages/i18n/messages/{de,en,fr}/studio.json`

- [ ] **Step 1: Add the new keys**

In each locale, inside the existing `"sessionPanel": { ... }` object, add:

| key | DE | EN | FR |
|-----|----|----|----|
| `sessionPanel.generationStopped` | Generation gestoppt. | Generation stopped. | Generation interrompue. |
| `sessionPanel.serverStopFailed` | Stoppen fehlgeschlagen - bitte erneut versuchen. | Stop failed - please retry. | Echec de l'arret - veuillez reessayer. |

If `studio.aiActions.retry` is missing, add it (`Erneut versuchen` / `Retry` / `Reessayer`). `studio.aiActions.stop` already exists per the inventory.

- [ ] **Step 2: Run the i18n validation gate**

Run: `just validate-i18n` (or `cd packages/web && npx tsx scripts/validate-i18n.ts`)
Expected: PASS - DE/EN/FR parity for all new keys.

- [ ] **Step 3: Checkpoint**

Phase-1 i18n complete. Phase-2 recovery keys land in Task 33.

---

## Task 18: Frontend tests - Phase 1 stop dispatch + reconciliation

**Files:**
- Test: `packages/web/components/studio/editor/__tests__/createSessionMessageHandler.test.tsx` (NEW)

- [ ] **Step 1: Write the test suite**

Create `packages/web/components/studio/editor/__tests__/createSessionMessageHandler.test.tsx`. `makeHandlers()` returns vi.fn stubs for `setMessages`, `setStreamingText`, `setIsStreaming`, `setIsConnected`, `setSaveNotification`, and a `streamingTextRef: { current: "" }`.

Tests:
- `generation_stopped` clears streaming state and surfaces server-reported partial prose (preset `streamingTextRef.current = "in-flight"`, call handler with `{type: "generation_stopped", status: "stopped", partial_prose: "server partial", invocation_id: "i-1"}`; assert `setIsStreaming(false)`, `setStreamingText("")`, `streamingTextRef.current === ""`, `setMessages` called).
- `generation_stopped` with empty partial still clears streaming state.

- [ ] **Step 2: Run the test**

Run: `cd packages/web && npx vitest run components/studio/editor/__tests__/createSessionMessageHandler.test.tsx`
Expected: PASS.

- [ ] **Step 3: Run the full frontend Phase-1 sweep**

Run: `cd packages/web && npx vitest run __tests__/SessionPanel.test.tsx components/studio/editor/__tests__/`
Expected: PASS.

- [ ] **Step 4: Checkpoint**

Phase 1 (server-side stop) fully shipped: backend cancel pipeline + frontend dispatch/reconciliation + i18n.

---

# Phase 2 - WebSocket Recovery

## Task 19: Core - `SessionManagerProtocol.reattach_session` + `SessionManager.reattach_session`

**Files:**
- Modify: `packages/core/narrare_core/writing/contracts.py`
- Modify: `packages/core/narrare_core/writing/session_manager.py`
- Modify: `apps/api/narrare/writing/ws_session_control_service.py` (delegate reattach to manager)
- Test: `tests/unit/core/writing/test_session_manager.py` (extend)

- [ ] **Step 1: Write the failing tests**

Append `class TestReattachSession` to `tests/unit/core/writing/test_session_manager.py`. Tests:
- `test_reattach_live_session_returns_recovered`: assert `kind == "recovered"` and `session_id` matches.
- `test_reattach_missing_session_returns_not_found`: random UUID.
- `test_reattach_inactive_session_returns_expired`: flip `is_active=False` in the cache JSON.
- `test_reattach_wrong_user_returns_ownership_mismatch`.
- `test_reattach_wrong_project_returns_ownership_mismatch`.

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/unit/core/writing/test_session_manager.py::TestReattachSession -v`
Expected: FAIL - `AttributeError`.

- [ ] **Step 3: Add the contract method**

In `packages/core/narrare_core/writing/contracts.py`, add to `SessionManagerProtocol`:

```python
    async def reattach_session(
        self,
        session_id: UUID,
        user_id: UUID,
        project_id: UUID,
    ) -> dict[str, object]:
        """Reattach to an existing session after a transport reconnect (ADR-052).

        Returns a dict with ``kind`` in {``recovered``, ``not_found``,
        ``expired``, ``ownership_mismatch``}.
        """
        ...
```

- [ ] **Step 4: Implement `SessionManager.reattach_session`**

In `packages/core/narrare_core/writing/session_manager.py`, add the method. Logic:
1. `state = await self._load(session_id)`.
2. If None: return `{"kind": "not_found", "session_id": str(session_id)}`.
3. If `not state.is_active`: return `{"kind": "expired", ...}`.
4. If `state.user_id != user_id or state.project_id != project_id`: return `{"kind": "ownership_mismatch", ...}`.
5. Set `state.connection_state = ConnectionState.REATTACHING` (local import to avoid cycle), persist, return the `recovered` dict with all snapshot fields.

- [ ] **Step 5: Delegate control-service reattach to the manager**

In `apps/api/narrare/writing/ws_session_control_service.py`, replace the `reattach_session` body with `return await self._session_manager.reattach_session(session_id, user_id, project_id)`. Remove the `_load_raw_or_none` private helper.

- [ ] **Step 6: Run the test to verify it passes**

Run: `pytest tests/unit/core/writing/test_session_manager.py::TestReattachSession tests/unit/api/writing/test_ws_session_control_service.py::TestReattachSession -v`
Expected: PASS. (The control-service tests from Task 8 keep passing because they assert on `kind` only.)

- [ ] **Step 7: Checkpoint**

Core reattach contract is the single source of truth.

---

## Task 20: Backend - reattach test sweep

- [ ] **Step 1: Run control-service + manager reattach tests**

Run: `pytest tests/unit/api/writing/test_ws_session_control_service.py tests/unit/core/writing/test_session_manager.py::TestReattachSession -v`
Expected: PASS.

- [ ] **Step 2: Checkpoint**

Reattach logic lives in core; service delegates.

---

## Task 21: Backend - `router_sessions.py` uses shared cache via `deps_ws` accessors + `session_id` query param

**Files:**
- Modify: `apps/api/narrare/writing/router_sessions.py`

- [ ] **Step 1: Refactor the router**

Re-read `apps/api/narrare/writing/router_sessions.py` (current per-connection cache construction is at lines 32-78). Replace:
- The `cache = InMemorySessionCache()` / `session_manager = SessionManager(cache=cache)` block with `deps_ws` accessor calls.
- Add `session_id: UUID | None = None` parameter to the route signature (FastAPI reads it from the query string).
- Build the handler via `build_writing_session_handler(session_manager=session_manager, registry=..., turn_state=..., control_service=..., model_registry=..., composer=..., config=config, invocation_pipeline=..., run_limit_resolver=..., mode=mode, ws_idle_timeout=limits.ws_timeout)`.
- Call `await handler.handle(websocket, chapter_id, user_id, project_id, session_id=session_id)`.

Sketch (origin validation and rate-limit blocks unchanged):

```python
@router.websocket("/writing/sessions/{chapter_id}")
async def interactive_session(
    websocket: WebSocket,
    chapter_id: UUID,
    user_id: str = "",
    project_id: UUID | None = None,
    mode: str = "interactive_session",
    session_id: UUID | None = None,
) -> None:
    """..."""
    from narrare.writing.deps_ws import (
        get_active_turn_registry,
        get_session_control_service,
        get_session_manager,
        get_turn_state,
    )
    # ... origin validation, rate-limit unchanged ...

    session_manager = get_session_manager()
    registry = get_active_turn_registry()
    turn_state = get_turn_state()
    control_service = get_session_control_service(
        session_manager=session_manager, registry=registry, turn_state=turn_state
    )
    # ... token limits / model config resolution unchanged ...
    handler = build_writing_session_handler(
        session_manager=session_manager,
        registry=registry,
        turn_state=turn_state,
        control_service=control_service,
        model_registry=get_model_registry(),
        composer=get_composer(),
        config=config,
        invocation_pipeline=get_invocation_pipeline(),
        run_limit_resolver=DefaultRunLimitResolver(),
        mode=mode,
        ws_idle_timeout=limits.ws_timeout,
    )
    await handler.handle(websocket, chapter_id, user_id, project_id, session_id=session_id)
```

- [ ] **Step 2: Run the session lifecycle integration test**

Run: `pytest tests/integration/writing/test_session_lifecycle.py -v`
Expected: PASS once Tasks 23 + 26 (deps_ws accessors + lifespan binding) land. If they have not landed yet, this test fails on `AttributeError: app.state has no attribute 'session_manager'` - defer to Task 27.

- [ ] **Step 3: Checkpoint**

Per-connection cache replaced by the shared singleton.

---

## Task 22: Backend - `ws_handler.py` reattach branch + `connection_lost` on timeout + no auto-end

**Files:**
- Modify: `apps/api/narrare/writing/ws_handler.py`

- [ ] **Step 1: Update the handler**

In `apps/api/narrare/writing/ws_handler.py`:

1. Add `control_service: WritingSessionControlProtocol` to `__init__` (store as `self._control_service`). Add the TYPE_CHECKING import.
2. Replace `handle()` so it:
   - Accepts `*, session_id: UUID | None = None`.
   - If `session_id is not None`: call `self._control_service.reattach_session(session_id, user_uuid, project_id)`. On `kind == "recovered"`: set `active_session_id = UUID(outcome["session_id"])`, send `session_recovered` with snapshot fields, skip greeting. Else: send `recovery_failed` with `kind`, close with code 4404, return.
   - Else: create session as before and send greeting.
   - Build `WritingSessionContext` with `active_session_id`.
   - Enter the receive loop as before.
   - On `WebSocketDisconnect`: log, call `await self._mark_disconnected(active_session_id)` - DO NOT call `end_session`.
   - On `TimeoutError`: call `_handle_timeout` which now sends `{"type": "connection_lost", "message": ...}` and then `_mark_disconnected`.
   - On other `Exception`: existing error-send behaviour.
   - `finally`: empty body - no `end_session` (the session stays in the cache for reattach; TTL handles expiry).
3. Add helpers `_handle_timeout(websocket, session_id)` and `_mark_disconnected(session_id)` (load state, set `ConnectionState.DISCONNECTED`, persist; best-effort, logged at debug).

- [ ] **Step 2: Update `ws_factory.py` to pass `control_service` to `WritingSessionHandler`**

If not already done in Task 10 Step 5, add `control_service=control_service` to the `WritingSessionHandler(...)` constructor call.

- [ ] **Step 3: Run the session lifecycle integration test**

Run: `pytest tests/integration/writing/test_session_lifecycle.py -v`
Expected: PASS once Tasks 23 + 26 land (the test connects without a `session_id`, so it goes through the create branch). Update assertions that expected `end_session` on disconnect - they should now expect the session to remain recoverable.

- [ ] **Step 4: Checkpoint**

Reattach branch wired. Disconnect no longer ends the session. Timeout emits `connection_lost`.

---

## Task 23: Backend - `deps_ws.py` accessors for shared singletons

**Files:**
- Modify: `apps/api/narrare/writing/deps_ws.py`

- [ ] **Step 1: Add the accessors**

In `apps/api/narrare/writing/deps_ws.py`, append accessors that read from `app.state`:

```python
from narrare._app.main import app  # module-level singleton


def get_session_cache():
    return app.state.session_cache


def get_session_manager() -> SessionManager:
    return app.state.session_manager


def get_active_turn_registry() -> ActiveTurnRegistry:
    return app.state.active_turn_registry


def get_turn_state() -> SessionTurnStateStore:
    return app.state.turn_state


def get_session_control_service(
    *,
    session_manager: SessionManager | None = None,
    registry: ActiveTurnRegistry | None = None,
    turn_state: SessionTurnStateStore | None = None,
) -> WritingSessionControlService:
    existing = getattr(app.state, "writing_session_control_service", None)
    if existing is not None and session_manager is None:
        return existing
    from narrare.writing.ws_session_control_service import WritingSessionControlService
    return WritingSessionControlService(
        session_manager=session_manager or get_session_manager(),
        turn_state=turn_state or get_turn_state(),
        registry=registry or get_active_turn_registry(),
    )
```

Add the TYPE_CHECKING imports for `ActiveTurnRegistry`, `WritingSessionControlService`, `SessionManager`, `SessionTurnStateStore`. Module docstring explains: singletons bound on `app.state` in `_app/lifespan.py`; test isolation resets the cache between tests via a fixture (Task 36).

- [ ] **Step 2: Verify imports resolve**

Run: `python -c "from narrare.writing.deps_ws import get_session_manager, get_session_control_service; print('ok')"`
Expected: prints `ok` (after Task 26 binds `app.state.session_cache` etc.).

- [ ] **Step 3: Checkpoint**

Accessors ready. Task 26 binds the singletons.

---

## Task 24: Backend - route `recover_session` in `WritingSessionMessageRouter`

**Files:**
- Modify: `apps/api/narrare/writing/ws_message_router.py`
- Test: `tests/unit/api/writing/test_ws_message_router_recover.py` (NEW)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/api/writing/test_ws_message_router_recover.py`. Stub classes mirror Task 11. `_StubControl.reattach_session` returns a configured `outcome` dict. Test:

- `test_route_recover_session_emits_session_recovered`: send `{"type": "recover_session", "session_id": "<uuid>"}`; assert the socket received `{"type": "session_recovered", "session_id": ..., "kind": "recovered", "last_sequence": ..., "active_partial_prose": ..., "active_invocation_id": ...}`.

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/unit/api/writing/test_ws_message_router_recover.py -v`
Expected: FAIL - `recover_session` not routed.

- [ ] **Step 3: Add the routing branch**

In `apps/api/narrare/writing/ws_message_router.py`, add `elif msg_type == "recover_session": await self._route_recover_session(websocket, context, data)`. Implement `_route_recover_session`:
- Validate `session_id` is a string and parses as UUID.
- Call `self._control_service.reattach_session(session_id, context.user_id, context.project_id)`.
- On `kind == "recovered"`: send `session_recovered` with snapshot fields.
- Else: send `recovery_failed` with `kind` and `session_id`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/unit/api/writing/test_ws_message_router_recover.py -v`
Expected: PASS.

- [ ] **Step 5: Checkpoint**

Mid-session `recover_session` message routed (for in-flight reconnects via the same connection).

---

## Task 25: Backend - verify `ws_factory.py` wiring (complete)

**Files:** (verification only)

- [ ] **Step 1: Verify factory signature**

Open `apps/api/narrare/writing/ws_factory.py` and confirm `build_writing_session_handler` accepts `registry`, `turn_state`, `control_service`, and passes them to `WritingDirectionDispatcher`, `WritingSessionMessageRouter`, `WritingSessionHandler`. If anything is missing, add it per the snippets in Tasks 10 and 22.

- [ ] **Step 2: Run unit tests**

Run: `pytest tests/unit/api/writing/ -v`
Expected: PASS.

- [ ] **Step 3: Checkpoint**

Factory wiring verified end-to-end.

---

## Task 26: Backend - bind shared singletons on `app.state` in `lifespan.py`

**Files:**
- Modify: `apps/api/narrare/_app/lifespan.py`

- [ ] **Step 1: Add the singleton instantiation in startup**

In `apps/api/narrare/_app/lifespan.py`, inside `lifespan()` startup (after the wiki event listeners block, before the cleanup task), add a try/except block that:
- Imports `InMemorySessionCache`, `ActiveTurnRegistry`, `WritingSessionControlService`, `SessionManager`, `SessionTurnStateStore`.
- Instantiates them: `session_cache`, `session_manager = SessionManager(cache=session_cache)`, `turn_state`, `active_turn_registry`, `control_service = WritingSessionControlService(session_manager=session_manager, turn_state=turn_state, registry=active_turn_registry)`.
- Binds each on `app.state`: `session_cache`, `session_manager`, `turn_state`, `active_turn_registry`, `writing_session_control_service`.
- Logs `writing_session_singletons_bound` on success; logs and re-raises on failure.

> Production note: `InMemorySessionCache` is used here for parity with the current per-connection behaviour. The recovery semantics only kick in when the cache survives across connections - which it now does, because it is bound to `app.state`. For multi-worker deployments, swap to a Redis-backed `SessionCacheProtocol` implementation (ADR-052 Review Trigger #1). The registry and turn state are also process-local; multi-worker needs Redis there too.

- [ ] **Step 2: Run the integration test**

Run: `pytest tests/integration/writing/test_session_lifecycle.py -v`
Expected: PASS - the TestClient's lifespan now binds the singletons on `app.state`.

- [ ] **Step 3: Checkpoint**

Singletons bound. The router (Task 21) reads them via `deps_ws` accessors (Task 23).

---

## Task 27: Backend - Phase 2 test sweep

- [ ] **Step 1: Run all backend tests**

Run: `pytest tests/unit/api/writing/ tests/unit/core/writing/ tests/integration/writing/ -v`
Expected: PASS (all).

- [ ] **Step 2: Run `just check-architecture`**

Run: `just check-architecture`
Expected: PASS - all new files under size limits, dependency direction preserved.

- [ ] **Step 3: Checkpoint**

Phase-2 backend complete.

---

## Task 28: Frontend - `WritingSessionSocket` captures `sessionId`, includes it in reconnect URL, sends `recover_session`

**Files:**
- Modify: `packages/web/lib/api/generation.ts`
- Test: `packages/web/components/studio/editor/__tests__/useSessionSocket.recovery.test.tsx` (NEW, first half)

- [ ] **Step 1: Extend `WritingSessionSocket`**

In `packages/web/lib/api/generation.ts`:

1. Add `private sessionId: string | undefined` to the class.
2. Constructor accepts an optional `initialSessionId?: string` as the last parameter; assign it to `this.sessionId`.
3. In the `onmessage` handler, before dispatching to `this.onMessage`, inspect the parsed message: if `msg.type === "greeting"` or `msg.type === "session_recovered"` and `msg.session_id` is set, capture `this.sessionId = msg.session_id`.
4. In `connect()`, after the existing `user_id`, `project_id`, `mode` params, add `if (this.sessionId) params.set("session_id", this.sessionId)` so reconnect URLs include the session id.
5. In `onclose`, before scheduling a reconnect, if `this.sessionId` is set, schedule a `recover_session` send after the reconnect succeeds. Implementation: add a `private pendingRecover: boolean = false` flag set in `onclose` when there is a session id; in `connect()` after `this.ws.onopen = () => { if (this.pendingRecover) { this.send({type: "recover_session", session_id: this.sessionId}); this.pendingRecover = false; } }`. (Wire `onopen` alongside the existing `onmessage`/`onerror`/`onclose`.)

- [ ] **Step 2: Write the first half of the recovery test**

Create `packages/web/components/studio/editor/__tests__/useSessionSocket.recovery.test.tsx`. Mirror the mock-WebSocket pattern from `useSessionSocket.test.tsx` (lines 116-197). Tests:
- After receiving a `greeting` with `session_id`, the next reconnect URL includes `session_id=...`.
- On `onclose` (when a session id is known), the next successful reconnect sends `{"type": "recover_session", "session_id": "..."}` as the first message.

- [ ] **Step 3: Run the test**

Run: `cd packages/web && npx vitest run components/studio/editor/__tests__/useSessionSocket.recovery.test.tsx`
Expected: PASS.

- [ ] **Step 4: Checkpoint**

Socket captures session id and reattaches on reconnect.

---

## Task 29: Frontend - `useSessionSocket` exposes `recoveryState` + sends `recover_session`

**Files:**
- Modify: `packages/web/components/studio/editor/useSessionSocket.ts`
- Test: extend `packages/web/components/studio/editor/__tests__/useSessionSocket.recovery.test.tsx`

- [ ] **Step 1: Add `recoveryState`**

In `packages/web/components/studio/editor/useSessionSocket.ts`:
- Add `const [recoveryState, setRecoveryState] = useState<"idle" | "reconnecting" | "recovered" | "failed">("idle")`.
- In the `onError` callback (`() => setIsConnected(false)`), also call `setRecoveryState("reconnecting")` when there is a known session id (track via a `sessionIdRef` updated from the message handler).
- Return `recoveryState` and `setRecoveryState` in the hook output so the message handler can drive transitions.

- [ ] **Step 2: Extend the recovery test**

Add tests:
- On disconnect (onError fires), `recoveryState` transitions to `"reconnecting"`.
- After the socket receives `session_recovered`, `recoveryState` transitions to `"recovered"`.
- After the socket receives `recovery_failed`, `recoveryState` transitions to `"failed"`.

These require the message handler (Task 31) to call `setRecoveryState`; wire the transitions in Task 31 and verify here.

- [ ] **Step 3: Run the test**

Run: `cd packages/web && npx vitest run components/studio/editor/__tests__/useSessionSocket.recovery.test.tsx`
Expected: PASS (after Task 31 lands the handler transitions).

- [ ] **Step 4: Checkpoint**

Recovery state surfaced to consumers.

---

## Task 30: Frontend - create `SessionReconnectBanner.tsx`

**Files:**
- Create: `packages/web/components/studio/editor/SessionReconnectBanner.tsx`
- Test: `packages/web/components/studio/editor/__tests__/SessionReconnectBanner.test.tsx` (NEW)

- [ ] **Step 1: Write the failing tests**

Create `packages/web/components/studio/editor/__tests__/SessionReconnectBanner.test.tsx`. The component takes `recoveryState`, `reconnectingLabel`, `recoveredLabel`, `recoveryFailedLabel`, `connectionLostLabel`, `preserveLocalCopyLabel`, `localProse`, `onRetry` props. Tests:
- When `recoveryState === "idle"`, the banner renders nothing.
- When `recoveryState === "reconnecting"`, the banner shows the reconnecting label.
- When `recoveryState === "recovered"`, the banner shows the recovered label.
- When `recoveryState === "failed"`, the banner shows the failure label, the preserve-local-copy label, and a Retry button that calls `onRetry`.

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd packages/web && npx vitest run components/studio/editor/__tests__/SessionReconnectBanner.test.tsx`
Expected: FAIL - component does not exist.

- [ ] **Step 3: Implement the banner**

Create `packages/web/components/studio/editor/SessionReconnectBanner.tsx`. A small presentational component that switches on `recoveryState` and renders the appropriate localized label. For `"failed"`, also render the `preserveLocalCopyLabel` and a Retry button (`onRetry`). The component must be under ~80 lines (RULE-04). Use the same Tailwind class style as the existing `saveNotification` banner in `SessionPanel.tsx`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd packages/web && npx vitest run components/studio/editor/__tests__/SessionReconnectBanner.test.tsx`
Expected: PASS.

- [ ] **Step 5: Checkpoint**

Banner component ready for adoption in `SessionPanel.tsx` (Task 32).

---

## Task 31: Frontend - handle `session_recovered`, `recovery_failed`, `connection_lost` in `createSessionMessageHandler`

**Files:**
- Modify: `packages/web/components/studio/editor/createSessionMessageHandler.ts`
- Modify: `packages/web/components/studio/editor/__tests__/createSessionMessageHandler.test.tsx` (extend)

- [ ] **Step 1: Add the new cases**

Extend `MessageHandlerCallbacks` with optional `setRecoveryState?: (state) => void`. In the `switch`:
- `case "session_recovered"`: call `setRecoveryState?.("recovered")`; if `msg.active_partial_prose`, push it into `messages` as an assistant prose bubble; set `setIsConnected(true)`.
- `case "recovery_failed"`: call `setRecoveryState?.("failed")`; push a system message with `msg.message ?? recoveryFailedLabel` (the handler needs a new optional `recoveryFailedLabel` in callbacks); set `setIsConnected(false)`.
- `case "connection_lost"`: call `setRecoveryState?.("reconnecting")` (the UI shows the banner; user clicks retry to reconnect); set `setIsConnected(false)`.

- [ ] **Step 2: Extend the handler test**

Add cases to `createSessionMessageHandler.test.tsx`:
- `session_recovered` with `active_partial_prose` surfaces the prose and sets recovery state to `recovered`.
- `recovery_failed` with `kind: "expired"` sets recovery state to `failed` and pushes a system message.
- `connection_lost` sets recovery state to `reconnecting`.

- [ ] **Step 3: Run the test**

Run: `cd packages/web && npx vitest run components/studio/editor/__tests__/createSessionMessageHandler.test.tsx`
Expected: PASS.

- [ ] **Step 4: Checkpoint**

All recovery messages handled.

---

## Task 32: Frontend - reconnect banner + local prose preservation in `SessionPanel`

**Files:**
- Modify: `packages/web/components/studio/editor/SessionPanel.tsx`
- Modify: `packages/web/components/studio/editor/useSessionSocket.ts` (pass `setRecoveryState` into the handler)

- [ ] **Step 1: Wire `setRecoveryState` into the handler**

In `useSessionSocket.ts`, pass `setRecoveryState` into `createSessionMessageHandler({...})` so the new cases can drive the recovery state.

- [ ] **Step 2: Render the banner in `SessionPanel.tsx`**

In `packages/web/components/studio/editor/SessionPanel.tsx`:
- Pull `recoveryState` out of `useSessionSocket(...)`.
- Capture `streamingTextRef.current` into a `preservedProse` state whenever `connection_lost` fires (use an effect on `recoveryState === "reconnecting"`).
- Render `<SessionReconnectBanner>` above the messages list, passing the localized labels (`t("sessionPanel.reconnecting")`, etc.), `localProse={preservedProse}`, and `onRetry={() => sendMessage("recover_session", undefined, { session_id: sessionIdRef.current })}`.
- Import `SessionReconnectBanner`.

- [ ] **Step 3: Extend `SessionPanel.test.tsx`**

Add tests:
- When `recoveryState === "failed"`, the banner renders with the preserve-local-copy label and the local prose is visible.
- When the Retry button is clicked, `sendMessage` is called with `"recover_session"`.

- [ ] **Step 4: Run the tests**

Run: `cd packages/web && npx vitest run __tests__/SessionPanel.test.tsx components/studio/editor/__tests__/`
Expected: PASS.

- [ ] **Step 5: Checkpoint**

Phase-2 frontend complete: recovery state, reconnect banner, local prose preservation.

---

## Task 33: i18n - Phase 2 recovery keys (DE/EN/FR)

**Files:**
- Modify: `packages/i18n/messages/{de,en,fr}/studio.json`

- [ ] **Step 1: Add the new keys**

In each locale, inside `"sessionPanel": { ... }`, add:

| key | DE | EN | FR |
|-----|----|----|----|
| `sessionPanel.reconnecting` | Verbindung wird wiederhergestellt... | Reconnecting... | Reconnexion... |
| `sessionPanel.recovered` | Sitzung wiederhergestellt. | Session recovered. | Session restauree. |
| `sessionPanel.recoveryFailed` | Wiederherstellung fehlgeschlagen. | Recovery failed. | Echec de la recuperation. |
| `sessionPanel.connectionLost` | Verbindung verloren. | Connection lost. | Connexion perdue. |
| `sessionPanel.preserveLocalCopy` | Dein lokaler Text wurde erhalten. | Your local text has been preserved. | Votre texte local a ete conserve. |

In `aiActions`:
| `aiActions.connectionLostRetry` | Erneut verbinden | Reconnect | Reconnecter |
(if `aiActions.retry` was not added in Task 17, add it here.)

- [ ] **Step 2: Run the i18n validation gate**

Run: `just validate-i18n`
Expected: PASS.

- [ ] **Step 3: Checkpoint**

Phase-2 i18n complete.

---

## Task 34: Frontend tests - Phase 2 recovery sweep

- [ ] **Step 1: Run all frontend tests**

Run: `cd packages/web && npx vitest run`
Expected: PASS.

- [ ] **Step 2: Run `just check-frontend-size`**

Run: `just check-frontend-size`
Expected: PASS - `SessionReconnectBanner.tsx` is under limits; `SessionPanel.tsx` stays under limits thanks to the banner extraction.

- [ ] **Step 3: Checkpoint**

Phase-2 frontend complete.

---

# Platform / Governance

## Task 35: Integration test - stop + recovery end-to-end

**Files:**
- Create: `tests/integration/writing/test_session_stop_and_recovery.py`

- [ ] **Step 1: Write the integration test**

Create `tests/integration/writing/test_session_stop_and_recovery.py`. Reuse the `ws_env` fixture pattern from `tests/integration/writing/test_session_lifecycle.py` (FakeModelRegistry + patched composer + TestClient). Tests:

1. `test_stop_generation_mid_stream_cancels_and_returns_partial`: connect, send `user_direction`, send `stop_generation` while streaming, assert a `generation_stopped` message arrives with `status: "stopped"` and non-empty `partial_prose`. Assert the underlying fake stream task was cancelled.
2. `test_disconnect_then_reconnect_reattaches_to_same_session`: connect (capture `session_id` from greeting), send a direction, simulate disconnect, reconnect with `?session_id=...`, assert `session_recovered` with the captured session id.
3. `test_reconnect_to_expired_session_returns_recovery_failed`: connect, force-expire the session (flip `is_active=False` in the shared cache), reconnect with `?session_id=...`, assert `recovery_failed` with `kind: "expired"`.
4. `test_reconnect_with_wrong_user_returns_ownership_mismatch`: connect as user A, reconnect as user B with A's session id, assert `recovery_failed` with `kind: "ownership_mismatch"`.
5. `test_idle_timeout_emits_connection_lost`: connect, trigger idle timeout (mock `asyncio.wait_for` to raise `TimeoutError`), assert a `connection_lost` message is sent and the session remains in the cache (recoverable).
6. `test_shared_cache_invariant`: two sequential connections (without `session_id`) for the same chapter create two distinct sessions; one connection with `?session_id=<first>` reattaches to the first session (the shared cache survives across connections).

- [ ] **Step 2: Run the test**

Run: `pytest tests/integration/writing/test_session_stop_and_recovery.py -v`
Expected: PASS (6 tests).

- [ ] **Step 3: Checkpoint**

End-to-end stop + recovery verified.

---

## Task 36: Test isolation fixture - reset shared cache between tests

**Files:**
- Modify: `tests/integration/writing/conftest.py`

- [ ] **Step 1: Add an autouse fixture**

In `tests/integration/writing/conftest.py`, add an autouse fixture that resets `app.state.session_cache`, `app.state.session_manager`, `app.state.turn_state`, `app.state.active_turn_registry`, `app.state.writing_session_control_service` between tests so cross-test state does not leak. Pattern:

```python
@pytest.fixture(autouse=True)
def reset_shared_session_singletons():
    """Reset ADR-052 shared singletons between integration tests."""
    from narrare._app.main import app
    # Snapshot
    saved = {k: getattr(app.state, k, None) for k in (
        "session_cache", "session_manager", "turn_state",
        "active_turn_registry", "writing_session_control_service",
    )}
    # Fresh singletons for this test
    from narrare.writing._ws_cache import InMemorySessionCache
    from narrare.writing.ws_active_turn_registry import ActiveTurnRegistry
    from narrare.writing.ws_session_control_service import WritingSessionControlService
    from narrare_core.writing.session_manager import SessionManager
    from narrare_core.writing.session_turn_state import SessionTurnStateStore

    cache = InMemorySessionCache()
    manager = SessionManager(cache=cache)
    turn_state = SessionTurnStateStore()
    registry = ActiveTurnRegistry()
    app.state.session_cache = cache
    app.state.session_manager = manager
    app.state.turn_state = turn_state
    app.state.active_turn_registry = registry
    app.state.writing_session_control_service = WritingSessionControlService(
        session_manager=manager, turn_state=turn_state, registry=registry,
    )
    yield
    # Restore (defensive - the next test will overwrite anyway)
    for k, v in saved.items():
        setattr(app.state, k, v)
```

- [ ] **Step 2: Re-run the integration suite**

Run: `pytest tests/integration/writing/ -v`
Expected: PASS (no cross-test leakage).

- [ ] **Step 3: Checkpoint**

Test isolation guaranteed.

---

## Task 37: AI Operation Inventory - `writing.session` entry

**Files:**
- Modify: `scripts/checks/ai_operation_inventory.yaml`

- [ ] **Step 1: Add the operation entry**

Append to `scripts/checks/ai_operation_inventory.yaml` (in the Writing flows section):

```yaml
  - operation_id: writing.session
    feature: Writing - Interactive Session (WebSocket)
    entry_points:
      - packages/web/components/studio/editor/SessionPanel.tsx
      - packages/web/components/studio/editor/useSessionSocket.ts
      - packages/web/lib/api/generation.ts (WritingSessionSocket)
      - apps/api/narrare/writing/router_sessions.py
      - apps/api/narrare/writing/ws_session_control_service.py
    transport: websocket
    lifecycle_owner: governed_exception
    loading_feedback: "isStreaming at useSessionSocket.ts (text_chunk accumulation)"
    cancel_ui: "handleStopGeneration sends stop_generation to backend (ADR-052); not UI-only"
    signal_propagation: "server-side Task.cancel via ActiveTurnRegistry (ADR-052)"
    error_mapping: "generation_stopped + recovery_failed + connection_lost typed messages mapped to studio.sessionPanel.* i18n"
    partial_output: "partial_prose preserved on stop and on disconnect (SessionTurnStateStore + optimistic local clear)"
    stop_generation: "POST over WebSocket: {type: 'stop_generation', invocation_id}; server cancels active turn (ADR-052)"
    recover_session: "WebSocket reconnect includes ?session_id=...; recover_session sent as first message (ADR-052)"
    ai_action_i18n: studio.aiActions.stop / .retry / .connectionLostRetry
    deprecated_key_usage: "No deprecated aliases in use"
    keyboard: "Escape stops generation when streaming; Escape ends session otherwise (KEYBOARD-001)"
    tests:
      - tests/integration/writing/test_session_stop_and_recovery.py
      - packages/web/components/studio/editor/__tests__/useSessionSocket.recovery.test.tsx
      - packages/web/__tests__/SessionPanel.test.tsx
    aufg_id: CR-AUFG-07-21
    exclude_entry: none
    status: compliant
```

- [ ] **Step 2: Run `just check-ai-ux`**

Run: `just check-ai-ux`
Expected: PASS - 0 violations, 0 stale excludes. The new inventory entry satisfies Check 10.

- [ ] **Step 3: Checkpoint**

Inventory complete.

---

## Task 38: RULE-17 cross-layer contract test - TS `SessionResponse` <-> Python WS message schemas

**Files:**
- Create: `tests/integration/writing/test_session_message_schema_parity.py`

- [ ] **Step 1: Write the parity test**

Create `tests/integration/writing/test_session_message_schema_parity.py`. The test asserts that the set of `type` literals in the TS `SessionResponse` interface (read from `packages/web/lib/api/generation.ts` via a regex/AST scan) matches the set of `type` values emitted by the Python backend (enumerated from `ws_message_router.py` + `ws_handler.py` + `ws_session_control_service.py` - collect the literal strings in `{"type": "..."}` payloads).

Sketch:

```python
def test_session_response_type_literals_match_backend() -> None:
    ts_types = _extract_ts_type_literals("packages/web/lib/api/generation.ts")
    py_types = _extract_py_type_literals([
        "apps/api/narrare/writing/ws_message_router.py",
        "apps/api/narrare/writing/ws_handler.py",
        "apps/api/narrare/writing/ws_session_control_service.py",
    ])
    assert ts_types == py_types, (
        f"SessionResponse type mismatch. TS only: {ts_types - py_types}; "
        f"PY only: {py_types - ts_types}"
    )
```

The helper functions scan for `"| \"<word>\""` patterns in the TS union and `{"type": "<word>"` / `"type": "<word>"` patterns in the Python sources.

- [ ] **Step 2: Run the test**

Run: `pytest tests/integration/writing/test_session_message_schema_parity.py -v`
Expected: PASS.

- [ ] **Step 3: Checkpoint**

Cross-layer schema parity is CI-gated.

---

## Task 39: Final gates

- [ ] **Step 1: Full backend gate**

Run: `just check-architecture && pytest tests/unit/api/writing/ tests/unit/core/writing/ tests/integration/writing/ -v`
Expected: PASS.

- [ ] **Step 2: Full frontend gate**

Run: `cd packages/web && npx tsc --noEmit && npx biome check . && npx vitest run`
Expected: PASS.

- [ ] **Step 3: i18n + AI-UX + size gates**

Run: `just validate-i18n && just check-ai-ux && just check-frontend-size`
Expected: PASS.

- [ ] **Step 4: Checkpoint**

All gates green. CR-AUFG-07-21 implementation complete and ready for coordinator review.

---

# Docs

## Task 40: Update WRITE-005 constraints

**Files:**
- Modify: `docs/features/writing/WRITE-005-interactive-session.md`

- [ ] **Step 1: Update the Constraints & Edge Cases section**

Replace the line `- Requires stable connection — disconnects lose unsaved prose` with:

```markdown
- Disconnect no longer always loses unsaved prose: ADR-052 introduces server-side stop + WebSocket recovery. Partial prose is preserved via SessionTurnStateStore on stop, and a `?session_id=` reattach restores the live session when the connection drops. Local unsaved prose is also preserved in the UI (SessionReconnectBanner). If recovery is impossible (expired session, ownership mismatch), the UI surfaces the reason and keeps the local copy.
```

Also add to the "Session persistence" subsection a note that the route now uses an injected shared `SessionCacheProtocol` (no per-connection cache), and reference ADR-052.

- [ ] **Step 2: Checkpoint**

WRITE-005 reflects the new recovery semantics.

---

## Task 41: Update `aufg-registry.md` - CR-AUFG-07-21 resolved

**Files:**
- Modify: `docs/architecture/governance/aufg-registry.md`

- [ ] **Step 1: Update the CR-AUFG-07-21 row**

In the CR-07 Follow-up v3 work-items table, change CR-AUFG-07-21's Status from `open` to `resolved` and replace the Acceptance summary with:

```markdown
| CR-AUFG-07-21 | C | SessionPanel server-side stop and WebSocket recovery | `resolved` | P2 | Stop reaches server-side session state via `WritingSessionControlService.stop_generation` + `ActiveTurnRegistry` (Task.cancel); connection-loss recovery preserves partial state via `SessionTurnStateStore` + shared cache + `?session_id=` reattach (`reattach_session`); ADR-052 accepted; integration + cross-layer tests green. |
```

Add an exit-evidence sub-section (mirroring the CR-AUFG-07-24 pattern) listing: ADR-052 accepted; implementation paths (`ws_active_turn_registry.py`, `ws_session_control_service.py`, `ws_sink.py`, `ws_direction_dispatch.py`, `ws_message_router.py`, `ws_handler.py`, `router_sessions.py`, `deps_ws.py`, `_app/lifespan.py`, `session_turn_state.py`, `session_state_codec.py`, `SessionReconnectBanner.tsx`, `useSessionSocket.ts`); enforcement (`tests/integration/writing/test_session_stop_and_recovery.py`, `tests/integration/writing/test_session_message_schema_parity.py`, `scripts/checks/ai_operation_inventory.yaml` `writing.session` entry, `just check-ai-ux`); validation (`just check-architecture`, `just validate-i18n`, full pytest + vitest).

- [ ] **Step 2: Checkpoint**

Registry reflects the resolved lifecycle state.

---

## Task 42: LEARN/INFRA docs (if affected)

**Files:**
- Verify: any LEARN-001 / INFRA docs that reference WRITE-005 disconnect behaviour.

- [ ] **Step 1: Grep for stale claims**

Run: `grep -rn "disconnects lose unsaved prose\|UI-only stop\|per-connection cache" docs/`
Expected: only the WRITE-005 line (now updated in Task 40) and possibly ADR-052 itself.

- [ ] **Step 2: Update any stale docs**

If any LEARN/INFRA doc repeats the old "disconnects lose unsaved prose" claim, update it to reference ADR-052. If none exist, this task is a no-op.

- [ ] **Step 3: Checkpoint**

Docs are consistent with the new semantics.

---

# Self-Review Checklist

## Task 43: Spec coverage matrix

- [ ] **Step 1: Walk the spec line by line**

Open `docs/features/ai-ux/CR-AUFG-07-21-session-stop-websocket-recovery.md`. For each acceptance criterion in "User-facing behavior and acceptance criteria" (lines 36-42) and each item in "Tests/enforcement gates required" (lines 82-87), confirm a task implements it:

| Spec line | Implementing task(s) |
|-----------|----------------------|
| Stop sends `stop_generation` + backend cancels | 8, 10, 11, 15 |
| Server acks with `generation_stopped` + partial prose | 8, 11, 16 |
| Session stays active after stop | 10 (busy guard + status), 22 (no auto-end) |
| Disconnect mid-stream keeps partial output + reconnect banner | 22, 29, 30, 31, 32, 33 |
| Reconnect reattaches to same session (no silent new) | 19, 21, 22, 26, 28 |
| Recovery impossible -> UI explains + preserves local prose | 19, 22, 31, 32 |
| Contract: stop_generation + reattach_session signatures | 7, 19 |
| Typed WS messages | 13, 16, 24, 31 |
| SessionResponse + WritingSessionSocket types match | 13, 28, 38 |
| Session cache state fields | 1, 2, 3, 4 |
| Route uses injected shared cache | 21, 23, 26 |
| DE/EN/FR keys | 17, 33 |
| Stop/retry buttons use aiActions.* | 17, 33 |
| Backend unit tests | 5, 8, 12, 19, 20, 27 |
| WebSocket integration tests | 35 |
| Frontend tests | 18, 34 |
| AI Operation Inventory entry | 37 |

If any gap is found, add a task before declaring the plan complete.

- [ ] **Step 2: Checkpoint**

Spec coverage verified - no gaps.

---

## Task 44: Final verification commands

- [ ] **Step 1: Backend full sweep**

Run: `just check-architecture && pytest tests/unit/core/writing/ tests/unit/api/writing/ tests/integration/writing/ -v --tb=short`
Expected: all PASS.

- [ ] **Step 2: Frontend full sweep**

Run: `cd packages/web && npx tsc --noEmit && npx biome check . && npx vitest run`
Expected: all PASS.

- [ ] **Step 3: Governance gates**

Run: `just validate-i18n && just check-ai-ux && just check-frontend-size`
Expected: all PASS.

- [ ] **Step 4: Spec/plan/archive cross-reference**

Run: `grep -n "ADR-052" docs/architecture/decisions/INDEX.md docs/features/ai-ux/CR-AUFG-07-21-session-stop-websocket-recovery.md docs/architecture/governance/aufg-registry.md docs/features/writing/WRITE-005-interactive-session.md 2>/dev/null`
Expected: ADR-052 referenced from INDEX, aufg-registry, and WRITE-005. The spec frontmatter (`requires: [WRITE-005, ADR-043]`) may optionally be extended to include ADR-052.

- [ ] **Step 5: Final checkpoint - ready for coordinator**

Plan executed end-to-end. All gates green. CR-AUFG-07-21 implementation is contract-complete, tested, RULE-compliant, and documented. Coordinator decides on commit timing.
