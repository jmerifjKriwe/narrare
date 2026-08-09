# Q-017 — Typed Session-Not-Found Exception in `SessionManager._load_or_raise` (ADR-052 follow-up)

> **Status:** ✅ Resolved (2026-08-08) — Option A (typed `SessionNotFoundError`)
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

## Resolution — Option A (typed `SessionNotFoundError`)

> **Status:** ✅ Resolved (2026-08-08) — **Option A** chosen.
> **Documentation:** Resolution in this question file. No full ADR (a typed domain
> exception within the existing `NotFoundError(NarrareError)` pattern in
> `shared/errors.py` — no new pattern/dependency/RULE-XX exception per the ADR-process
> trigger table). RULE-03 (contract first) + RULE-11 (no silent failures) apply.

### Root cause

The benign end_session race catch (`_ws_direction_stream.py:167` `except ValueError`)
does **not** merely rely on an implicit "only ValueError source" invariant — it
**actively swallows a real error class**. `_load_or_raise` → `_load` →
`deserialize_session_state`: a **corrupt cached session payload** raises
`json.JSONDecodeError`, which is a **`ValueError` subclass**. The bare `except
ValueError` would therefore treat cache corruption as a "benign session-ended race",
drop the assistant message, and log at info — a genuine silent-failure path (RULE-11).
A typed exception makes the catch structurally precise and lets corruption surface as
a real error (caught by the outer `except Exception` → logged at error).

A second conflation site was found during §7 verification:
`_ws_session_handlers.py:74` (`handle_save`) catches `ValueError` around
`save_to_chapter`, but `save_to_chapter` raises ValueError from **two** sources — its
own `"Prose buffer is empty"` (`session_manager.py:172`) **and** the propagated
`_load_or_raise` not-found. Today both surface as the same generic user-facing error
message; the typed exception disambiguates them.

### Alternatives considered

- **Option A — Typed exception (chosen).** Add `SessionNotFoundError` and raise it from
  `_load_or_raise`; narrow the catch sites. Precise, self-documenting, and closes the
  latent `JSONDecodeError`-swallow + the `handle_save` conflation.
- **Option B — Keep `ValueError` + comment.** *Rejected.* The comment-only approach
  preserves the latent silent-failure path (corruption swallowed) and the two-source
  conflation at `handle_save`. It is the implicit-invariant anti-pattern, not the
  simplest *correct* solution.

### Design decision (RULE-03 / RULE-06)

- **Reuse the existing pattern, not the existing dataclasses.** `SessionNotFound` /
  `SessionExpired` in `writing/requests.py` are **`ReattachOutcome` result dataclasses**
  (returned by `reattach_session`, discriminated by `kind`), **not exceptions**. They
  must NOT be overloaded into exceptions (RULE-06: one responsibility). Add a **new
  distinct exception** `SessionNotFoundError`.
- **Follow the domain-error pattern.** `shared/errors.py` already defines
  `NotFoundError(NarrareError)` (line 186) — domain errors subclass `NarrareError`,
  not Python builtins. `SessionNotFoundError(NotFoundError)` is the canonical shape.
  Home: `packages/core/narrare_core/shared/errors.py` (consistent with
  `NotFoundError`/`WritingError`), or a focused `writing/errors.py` if the Core
  specialist prefers domain cohesion — either is RULE-04/06-compliant; pick one and
  re-export from the writing package's public surface.
- **Do NOT subclass `ValueError`.** Subclassing for migration convenience would keep
  bare `except ValueError` sites silently catching the new type, defeating the
  precision we are adding. Migrate the call sites instead (blast radius below is small).

### §7-verified blast radius (migration scope)

Four `except ValueError` sites exist in `apps/api/narrare/writing/` — only the first
two are affected by this change:

1. `_ws_direction_stream.py:167` — **narrow** `except ValueError` →
   `except SessionNotFoundError` (the benign end_session race). Update the comment.
2. `_ws_session_handlers.py:74` (`handle_save`) — **split** the catch: handle
   `SessionNotFoundError` distinctly from the prose-empty `ValueError`. (Design call
   for the implementer: an evicted session on save is arguably a "session ended"
   outcome, not a hard error — mirror the stream tail's benign handling or send a
   typed "session_ended" message.)
3. `ws_message_router.py:172` — `UUID(raw_invocation)` parse. **Unrelated** (UUID
   format validation), unchanged.
4. `ws_message_router.py:214` — `UUID(raw_session_id)` parse. **Unrelated**, unchanged.

Plus: `_load_or_raise` callers (`add_message`, `append_prose`, `save_to_chapter`)
propagate — none catch internally. `save_to_chapter`'s own `"Prose buffer is empty"`
ValueError stays as-is (consider a follow-up `EmptyProseBufferError` for full
consistency, but that is out of scope here).

### Sustainability check

1. *Correct in 3 months?* Yes — standard domain-error pattern; corruption surfaces.
2. *Hard-to-undo coupling?* None — additive exception type.
3. *Simplest correct solution?* Yes — one new exception, one raise, two catch-site
   edits, test updates.
4. *Understandable to next dev?* Yes — `except SessionNotFoundError` is self-documenting;
   the "only ValueError source" comment + implicit invariant are retired.

### Implementation handoff → Core specialist

**RULE-03** (contract first — define `SessionNotFoundError` before changing the raise),
**RULE-06**, **RULE-11**.

1. `packages/core/narrare_core/shared/errors.py` — add `SessionNotFoundError(NotFoundError)`
   (or `writing/errors.py` + re-export).
2. `packages/core/narrare_core/writing/session_manager.py:273-278` — `_load_or_raise`
   raises `SessionNotFoundError(f"Session {session_id} not found or expired.")`.
3. `apps/api/narrare/writing/_ws_direction_stream.py:167` — narrow to
   `except SessionNotFoundError`; refresh the comment.
4. `apps/api/narrare/writing/_ws_session_handlers.py:74` — split the catch (see above).
5. Tests: `tests/unit/api/writing/test_ws_direction_dispatch_end_session.py` (currently
   documents/asserts the `ValueError` path — update to `SessionNotFoundError`);
   add a unit test that a corrupt cached payload (`JSONDecodeError`) is **not** swallowed
   as a benign race (regression guard for the latent bug this fixes); update any
   `session_manager` tests asserting `pytest.raises(ValueError)` for the not-found case.

**Test plan:** `just test` green; `just check` (architecture gate) green; pyright
strict green; the new corruption-regression test fails on the old code and passes on
the new (evidence the fix is real, per §7).

---

> **Status:** ✅ Resolved (2026-08-08) — **Option A**: typed `SessionNotFoundError`
> (subclassing the existing `NotFoundError`), raised from `_load_or_raise`, caught
> precisely in the stream success tail and split at `handle_save`. Closes a latent
> `JSONDecodeError`-swallow + a two-source ValueError conflation.
