# Q-017 — Typed Session-Not-Found Exception in `SessionManager._load_or_raise` (ADR-052 follow-up)

> **Status:** 🟡 Open
> **Blocks:** Nothing (the benign catch in the stream success tail is verified correct today)
> **Raised:** 2026-08-08
> **Source:** ADR-052 follow-up — end_session ↔ in-flight stream race fix

---

## Question

`SessionManager._load_or_raise` in
`packages/core/narrare_core/writing/session_manager.py` raises a bare
`ValueError("Session ... not found or expired.")` when a session is missing
from the cache. Should it raise a typed `SessionNotFoundError` instead, so the
benign end_session race in the stream success tail can catch precisely that
exception instead of all `ValueError`s?

## Context

ADR-052 defines the explicit `end_session` semantics: `SessionManager.end_session`
deletes the cached entry (`cache.delete`), and an in-flight stream may race
with that deletion. The stream's success tail calls `add_message`, whose
`_load_or_raise` raises `ValueError` when the session is already evicted; the
stream treats that as a benign race — the assistant message is dropped and
logged at info as `direction_stream_session_ended`.

Today the catch is `except ValueError` with a comment stating this is the only
`ValueError` source in that path (verified against `session_manager.py`). A
typed exception would make the benign catch structurally precise instead of
relying on the "only ValueError source" invariant.

Note: `SessionNotFound` / `SessionExpired` already exist in
`packages/core/narrare_core/writing/requests.py`, but they are used by the
reattach path (`reattach_session`), not by `_load_or_raise`.

## Options

- **A — Typed exception:** add `SessionNotFoundError` (shared errors) and raise
  it from `_load_or_raise`; catch it specifically in the stream success tail.
  Precise and self-documenting; requires updating the other `_load_or_raise`
  callers that may rely on `ValueError` today (e.g. `add_message` and the
  prose-buffer path) and their tests.
- **B — Keep `ValueError`:** the current catch is verified correct; add only a
  code comment. No churn, but the invariant stays implicit.

## Affected Areas

- `packages/core/narrare_core/writing/session_manager.py` — `_load_or_raise` (line 273)
- `apps/api/narrare/writing/_ws_direction_stream.py` — benign catch in the success tail
- `packages/core/narrare_core/writing/requests.py` — existing `SessionNotFound` / `SessionExpired` (reattach path)
- Tests for `session_manager` and the direction-stream success tail

## Related

- ADR-052 — Session Stop and WebSocket Recovery ("Explicit end_session semantics")
- `apps/api/narrare/writing/_ws_direction_stream.py` — `direction_stream_session_ended`

---

> **Status:** 🟡 Open — follow-up to ADR-052; blocks nothing while the benign catch is verified correct
