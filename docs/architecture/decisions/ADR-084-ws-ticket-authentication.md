# ADR-084 — WebSocket Ticket Authentication for Writing Sessions

> **Status:** 🔄 Proposed (flips to Implemented by the implementing slice)
> **Date:** 2026-08-29
> **Deciders:** PO (decision D1:a, 2026-08-27 — execution ordered), Architecture Agent (this ADR)
> **Implements:** PO decision **D1:a** — writing WebSocket sessions authenticate via a
> REST-issued short-lived ticket passed as a `token` query param (browsers cannot
> send `Authorization` headers on a WebSocket handshake). Deferred out of PR #190's
> original wave (D4:b); now executed on this branch as the last open GAP-CRITICAL.
> **Closes:** impersonation gap on the sole WebSocket surface.
> **Related:** ADR-081 (export pipeline — single-use token precedent,
> `apps/api/narrare/export/registry.py`), ADR-009 (security modernization),
> ADR-052 (session stop & WS recovery — recovery ownership checks become
> trustworthy), ADR-080 (in-process execution — single-process validity of an
> in-memory registry), ADR-053 (`useSessionSocket` frontend contract)

---

## Context

### The defect

The API has exactly **one** WebSocket endpoint (verified: sole `@router.websocket`
in `apps/api/`):

- `apps/api/narrare/writing/router_sessions.py:18-26` — `WS /api/v1/writing/sessions/{chapter_id}`

Its signature takes **`user_id: str = ""` as a client-supplied query parameter**
(`router_sessions.py:22`). Nothing on the handshake validates that the connecting
client owns that identity. The value flows, unchecked, into:

- token-limit resolution (`router_sessions.py:112-115` — per-user cascade),
- model-routing resolution (`router_sessions.py:125-129` — `UUID(user_id)`),
- the WS rate-limit key (`router_sessions.py:70` — `ws:writing:{user_id}:{chapter_id}`),
- the session handler and thereby session ownership (`router_sessions.py:150` —
  `handler.handle(websocket, chapter_id, user_id, …)`).

Every REST route derives identity from the JWT via
`CurrentUserIdDep` (`apps/api/narrare/_app/dependencies_auth.py:18-50`). The WS
surface is the one place where identity is **asserted, not authenticated** — any
client that knows (or guesses) a `user_id` can open a writing session as that
user: consume their token budget, ride their model routing, create sessions
bound to their identity, and defeat the per-user WS rate limit by rotating ids.
The origin allowlist (`router_sessions.py:52-67`) is CSRF defense-in-depth and
does not close this: it constrains *browsers*, not the declared *identity*.

### Root cause (2× Why)

1. *Symptom:* the writing WS trusts `user_id` from the query string.
2. *Why is the parameter client-supplied?* The browser WebSocket API cannot set
   request headers, so the existing Bearer/JWT mechanism
   (`HTTPBearer` → `verify_access_token`) is structurally unavailable at the
   handshake. When ADR-052 built the session endpoint, identity was passed as a
   query param to unblock the feature — an acknowledged security debt (the
   "reload the page" error path at `router_sessions.py:46` dates from it), never
   remediated.
3. *Why does that equal impersonation?* Nothing substituted a handshake-capable
   credential in the interim. The fix must therefore introduce a credential
   transport that works over a query param **without** putting a long-lived
   bearer there.

### The house precedent

The export pipeline (ADR-081) already solved the structurally identical problem
—"hand a one-shot, URL-carried credential to a client that cannot send headers"—

- `apps/api/narrare/export/registry.py:17-43` — token security model:
  `secrets.token_urlsafe(32)`; the **SHA-256 hash** is the stored validation
  credential (raw token never stored; delivered exactly once inside
  `artifact_url`);
- single-use (`registry.py:235-243` — first consume flips `artifact_consumed`),
- owner binding + **foreign ≡ unknown** anti-enumeration (`registry.py:229-241`),
- in-memory, process-local registry (`registry.py:114-118`) — valid because the
  deployment is single-process post-ADR-080;
- TTL + sweep hooked into the lifespan periodic cleanup
  (`apps/api/narrare/_app/lifespan.py:163-170`).

D1:a directs: mirror this pattern for the writing WS.

---

## Decision Drivers

- **PO decision D1:a (2026-08-27), binding:** short-lived ticket issued over
  REST (where Bearer auth works), passed as `token` query param, ~60 s TTL,
  single-use, bound to the authenticated user; the WS handshake validates it and
  *derives* identity server-side.
- **Browser constraint:** no headers on `new WebSocket(url)` — credential must
  ride the URL or the first message.
- **URL-borne-secret caution:** query strings can surface in server/proxy access
  logs. Note: WS handshake URLs do **not** enter browser history (no navigation
  occurs), so logs are the only realistic leak surface — and it is bounded by
  short TTL + single-use + hash-only storage.
- **RULE-03** — Protocol/contract before implementation.
- **RULE-06** — REST router thin, delegates to `AuthService`; the WS route keeps
  its established inline-handshake shape but validation is one registry call.
- **RULE-11** — typed, distinguishable-server-side / indistinguishable-to-client
  failures; no silent anything.
- **RULE-14** — no DB migration (in-memory registry mirrors D1 of ADR-081).
- **RULE-20** — mint + consume + WS rewire + frontend + tests land as ONE slice;
  backend-only would brick every writing session (the frontend would keep
  sending `user_id` and be rejected).
- **ADR-052 recovery:** reconnection semantics must survive (each reconnect
  performs a fresh handshake → needs a fresh ticket).

---

## Options Considered

### Option A — First-message authentication frame

Server accepts immediately; client's first WS message carries the JWT; server
buffers/rejects everything until the frame arrives (with timeout).

**Pros:** no secret in the URL; reuses the JWT as-is.

**Cons:** racy by construction — the server must hold an unauthenticated socket
open and timestamp-gate it; every client (including the recovery path,
`recover_session` in `writing-session-socket.ts:135-139`, and `ws_test_helpers`)
must guarantee message ordering before any other send; doubles the handshake
state machine on both ends for zero security gain over a pre-handshake
credential.

**Rejected:** race window + protocol complexity imposed on all clients.

### Option B — JWT in the query string

Reuse the access token itself as the `token` query param.

**Pros:** no new server surface at all.

**Cons:** the access token is a long-lived (minutes-to-hours), multi-use bearer;
URL/log leakage of it is a full account compromise until expiry, with no
revocation seam; TTL coupling to the access-token lifetime is far coarser than
the handshake needs; the house explicitly avoided this class of exposure with
the opaque export token (hash-stored, single-use).

**Rejected:** leak blast radius vastly larger than the one handshake being
protected.

### Option C — Cookie-based WS authentication

The refresh cookie (`auth/cookie_helpers.py`) is ambient and would accompany the
handshake automatically.

**Pros:** no URL secret, no client change.

**Cons:** ambient-credential handshakes are the canonical CSRF shape — the origin
allowlist would become the *only* defense on a stateful, expensive endpoint
(LLM turns); it also couples WS identity to cookie/session semantics rather
than the explicit Bearer flow the REST API uses.

**Rejected:** opens a CSRF surface on the highest-cost endpoint; identity
semantics diverge from REST.

### Option D — REST-issued short-lived single-use ticket as `token` query param (chosen)

`POST /api/v1/auth/ws-ticket` (JWT-authenticated, `CurrentUserIdDep`) returns an
opaque `token_urlsafe(32)` string; the WS handshake presents it as `token`;
the server validates against an in-memory, SHA-256-hash-keyed, single-use,
60 s-TTL registry and derives `user_id` from the ticket record.

**Pros:** exact mirror of the proven export-token pattern (same security model,
same registry mechanics, same sweep seam); secret is useless 60 s after mint and
after first use; identity is server-derived — the spoofable `user_id` param is
removed outright; no client protocol state machine changes.

**Cons:** one extra REST roundtrip per connection (and per reconnect); tickets
are process-local (lost on restart → clients simply fetch a new one; single-use
tickets have no meaningful cross-restart state).

---

## Decision

**We choose Option D.**

1. **Mint:** new route `POST /api/v1/auth/ws-ticket` in the auth domain
   (house-consistent home — identity minting belongs with `auth/`; login /
   register / refresh already live in `apps/api/narrare/auth/router.py`).
   JWT-authenticated via `CurrentUserIdDep`; delegates to
   `AuthService.issue_ws_ticket(user_id)` (RULE-06); responds
   `WsTicketResponse { token: str, expires_in: int }` with `expires_in = 60`
   (seconds; mirrors `TokenResponse.expires_in`). No dedicated rate limiter:
   the endpoint is Bearer-gated (ambient-credential-free, hence no CSRF surface)
   and cheap — same stance as `/auth/refresh` and `/auth/logout`; the limiters
   on register/login exist because those are unauthenticated surfaces.

2. **Registry:** new module `apps/api/narrare/auth/ws_tickets.py`, mirroring
   `export/registry.py` module-function style. Token = `secrets.token_urlsafe(32)`;
   stored credential = SHA-256 hex, which is also the dict key (lookup hashes
   the presented token — the raw token is never stored, exactly the
   preimage-protection of `export/registry.py:17-23`). Record: `user_id: UUID`,
   `expires_at: datetime`. `WS_TICKET_TTL = timedelta(seconds=60)`. Single-use
   is enforced by **deleting the record on successful consume**. Process-local
   by design (valid post-ADR-080 single-process deployment; RULE-14 — no
   migration). Expired-but-unused records are dropped lazily on lookup and by
   `sweep_expired()` hooked into the existing lifespan periodic loop beside the
   export sweep (`lifespan.py:163-170`).

3. **Consume & derive:** `consume(token: str) -> UUID` raises a typed
   `WsTicketError` on unknown / expired / already-consumed. Server-side reasons
   are logged (structlog); the client NEVER receives a distinguishing reason
   (foreign ≡ unknown ≡ expired ≡ consumed — anti-enumeration, mirroring
   `export/registry.py` owner-binding note). The writing WS route calls this
   first; the returned `UUID` **is** the session's `user_id` from that point on.

4. **WS handshake (rewritten order in `router_sessions.py`):**
   1. **Ticket validation** (authn) — missing/invalid/expired/consumed →
      accept → error frame → `close(4401)`.
   2. `project_id` presence → `close(4001)` (unchanged code; message loses its
      `user_id` mention).
   3. Origin allowlist → `close(1008)` (reclassified from 4001: it is a policy
      violation per RFC 6455 §7.4.1, not a malformed handshake; cosmetic break —
      no client ever branched on 4001).
   4. WS rate limit, now keyed on the **derived** `user_id`
      (`ws:writing:{user_id}:{chapter_id}`) → `close(4003)` — the per-user limit
      becomes unspoofable as a side effect.
   5. Everything downstream (token-limits cascade, model routing, handler,
      recovery ownership checks in `ws_session_control_service`) receives the
      **derived** identity — signatures unchanged, trust changed.

   The house accept → error-JSON → close pattern is retained (browsers cannot
   read close codes; the JSON frame is the readable channel —
   `router_sessions.py:42-49` precedent).

5. **`user_id` query param is REMOVED** from the endpoint signature — sanctioned
   backward break (PO D1:a). Old clients sending only `user_id` are rejected
   with 4401 (unknown ticket). No compatibility shim.

6. **Frontend:** `WritingSessionSocket` drops the `userId` constructor param and
   the `user_id` URL param; it gains a `ticketProvider: () => Promise<string>`
   callback. `connect()` awaits a **fresh ticket per connection attempt** —
   since reconnects re-enter `connect()` (`writing-session-socket.ts:157-163`),
   every retry carries a new ticket and a dead ticket can never be replayed
   (single-use would reject it anyway). `useSessionSocket` keeps `userId` solely
   as an auth-readiness gate (`if (!userId) return`) and no longer transmits it;
   the ticket provider calls the new `authApi.wsTicket()`.

---

## Rationale

1. **Symptom:** writing WS identity is client-asserted → impersonation.
2. **Why a ticket rather than header auth?** The platform (browser WS API)
   cannot send headers — the credential must ride the URL or the first frame;
   the frame variant is racy (Option A), the JWT variant leaks a long-lived
   bearer into logs (Option B), the cookie variant is a CSRF invitation on the
   most expensive endpoint (Option C).
3. **Why this is safe despite the URL:** the ticket is single-use (replay
   dead on arrival), 60 s TTL (mint-to-handshake window; the client uses it
   immediately), hash-stored (server compromise of the registry does not yield
   consumable tokens), and indistinguishable in failure (no oracle). The only
   realistic leak surface is server/proxy access logs — the same accepted
   trade-off the PO already sanctioned for export artifact URLs, at 30× shorter
   TTL and strictly single-use.
4. **Why the auth domain, not writing:** the credential asserts *identity*;
   minting belongs beside login/refresh. `writing/` consumes it, one import
   deep (`narrare.auth.ws_tickets`), matching the existing direction of
   cross-domain utility imports in `router_sessions.py` (config, rate limits,
   token-limits service).

Simplest *correct* solution: one new module (~80 LOC) + one route + one service
method + a handshake reorder; zero migrations; the security model is a verified
copy of an in-production pattern.

---

## Consequences

**Positive:**

- The impersonation GAP-CRITICAL closes: identity on the WS surface is derived
  from a JWT-backed, single-use credential.
- Per-user WS rate limiting and per-user token budgets become honest (keyed on
  authenticated identity).
- ADR-052 recovery ownership checks (`ownership_mismatch`) now compare against
  trustworthy identity end-to-end.
- Reconnect loops cannot burn stale credentials (fresh ticket per attempt).

**Negative / Trade-offs:**

- **Sanctioned backward break:** `user_id` query param gone; any non-web client
  of the WS endpoint must adopt the ticket flow.
- One extra REST roundtrip per WS connection/reconnection (≈ 1 request per
  session — negligible against multi-minute LLM sessions).
- Tickets are process-local: restart invalidates outstanding tickets (clients
  self-heal — next `connect()` fetches a new one; 60 s TTL makes persistence
  meaningless).
- Close code 4001 for origin reclassified to 1008 (cosmetic; no client
  branching existed).
- Secret-in-URL residual risk accepted and bounded (see Rationale 3).

**Constraints introduced / touched:** RULE-03 (contract first — sketches below),
RULE-04 (auth router stays < 150 lines — split rule specified), RULE-06 (REST
route thin; WS route single registry call), RULE-11 (typed error, logged
server-side, uniform client reason), RULE-14 (no migration), RULE-20 (one
coherent slice), RULE-22 (reads only auth-owned state).

---

## Contract Sketches (RULE-03 — authored before implementation)

> Home: `apps/api/narrare/auth/contracts.py` (Protocol seam),
> `apps/api/narrare/auth/ws_tickets.py` (registry — module-function contract in
> the `export/registry.py` style), `apps/api/narrare/auth/schemas.py`
> (`WsTicketResponse`).

```python
# auth/schemas.py
class WsTicketResponse(BaseModel):
    token: str          # opaque, returned exactly once, never stored raw
    expires_in: int     # seconds (60)


# auth/contracts.py — extend AuthServiceProtocol
@runtime_checkable
class AuthServiceProtocol(Protocol):
    ...
    def issue_ws_ticket(self, user_id: uuid.UUID) -> WsTicketResponse: ...


# auth/ws_tickets.py — registry contract (module functions, export-style)
WS_TICKET_TTL: timedelta  # 60 s

def issue(user_id: UUID, now: Callable[[], datetime] = _now) -> str:
    """Mint a single-use ticket bound to user_id; return the raw token once."""

def consume(token: str, now: Callable[[], datetime] = _now) -> UUID:
    """Validate + burn the ticket; return the bound user_id.

    Raises WsTicketError for unknown, expired, or already-consumed tickets
    (identical client-facing behavior for all three; specific reason logged).
    """

def sweep_expired(now: Callable[[], datetime] = _now) -> int:
    """Drop expired-unused records (lifespan periodic cleanup)."""


class WsTicketError(Exception):
    """Ticket missing, unknown, expired, or consumed (RULE-11 — typed)."""
```

---

## RULE-XX Compliance

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-03 | ✅ | `AuthServiceProtocol.issue_ws_ticket` + registry contract sketched here, authored in `contracts.py` / `ws_tickets.py` before implementation. |
| RULE-04 | ✅ | `auth/router.py` grows 129 → ~144 lines; the slice MUST split to `router_ws_tickets.py` first if it would cross 150. Registry is its own module. |
| RULE-05 | ✅ | No Core concern — credential lifecycle is API/identity domain; nothing leaks into `packages/core`. |
| RULE-06 | ✅ | REST route: `CurrentUserIdDep` → `service.issue_ws_ticket` → return (thin). WS route: validation is one `ws_tickets.consume()` call inside the existing inline-handshake pattern. |
| RULE-07 | ✅ | Registry is pure in-memory + `datetime`; no I/O; injectable `now` for testability (mirrors `sweep_expired(now)` in export). |
| RULE-09 | ✅ | Full annotations on all new signatures. |
| RULE-10 | ✅ | Test matrix below (registry semantics + handshake acceptance + regression for the removed param). |
| RULE-11 | ✅ | Typed `WsTicketError`; structlog carries the precise reason server-side; client sees one uniform rejection — anti-enumeration by design. |
| RULE-14 | ✅ | In-memory registry — no model column, no migration (ADR-081 D1 precedent). |
| RULE-18b | N/A | Not a configuration value. |
| RULE-20 | ✅ | Mint endpoint + registry + WS rewire + frontend + all tests land as one slice; partial landing is a broken writing surface, not a half-feature. |
| RULE-21 | ✅ | This ADR is the architecture review; deviations (TTL policy change, persistent store, header-auth enabler) require re-review. |
| RULE-22 | ✅ | Registry owns its state; WS route reads via the documented consume seam; no foreign module mutates `_TICKETS`. |
| RULE-01b/02/13 | N/A | No LLM client, prompt, or streaming-contract change. |

**RULE-20 streaming note:** the WS message protocol (streaming turns, recovery,
stop) is untouched — only the handshake gate changes. SSE surfaces are not
affected.

---

## Sustainability Check

1. **Correct in 3 months?** Yes — the credential mirrors an in-production
   pattern; TTL/single-use parameters live as named constants; the frontend
   transport owns ticket freshness per attempt, so TTL tuning needs no client
   change.
2. **Hard-to-undo coupling?** Low. One module + one route + one handshake
   reorder behind stable seams; if browsers ever gain WS headers (or the app
   moves to a non-browser client), the consume seam is a single call site to
   swap.
3. **Simplest correct solution?** Yes — rejected alternatives each add a race
   (A), a leak amplifier (B), or a CSRF surface (C) for the same outcome.
4. **Design intent clear?** Yes — D1:a mapped 1:1 to Decisions 1-6.

---

## Implementation Slice (binding spec for the executing agents)

### Backend

| # | File | Change |
|---|------|--------|
| B1 | `apps/api/narrare/auth/contracts.py` | + `issue_ws_ticket` on `AuthServiceProtocol` (contract first) |
| B2 | `apps/api/narrare/auth/ws_tickets.py` | **NEW** — registry per Contract Sketches: `WS_TICKET_TTL = timedelta(seconds=60)`, `issue()`, `consume()`, `sweep_expired()`, `WsTicketError`, `_TICKETS: dict[sha256-hex, _TicketRecord]` |
| B3 | `apps/api/narrare/auth/schemas.py` | + `WsTicketResponse(token: str, expires_in: int)` |
| B4 | `apps/api/narrare/auth/service.py` | + `issue_ws_ticket(user_id) -> WsTicketResponse` (delegates to registry) |
| B5 | `apps/api/narrare/auth/router.py` | + `POST /auth/ws-ticket` — `CurrentUserIdDep` → service; 200; no new limiter (Bearer-gated). Split to `router_ws_tickets.py` if this crosses the RULE-04 150-line limit |
| B6 | `apps/api/narrare/writing/router_sessions.py` | Remove `user_id` param; add `token: str = ""` query param; new handshake order: ticket→`4401`, `project_id`→`4001`, origin→`1008`, rate-limit (derived id)→`4003`; derive `user_id = ws_tickets.consume(token)`; all downstream calls receive the derived id |
| B7 | `apps/api/narrare/_app/lifespan.py` | Hook `ws_tickets.sweep_expired()` into `_periodic_cleanup_loop` beside the export sweep (lines 163-170) |

### Frontend

| # | File | Change |
|---|------|--------|
| F1 | `packages/web/types/auth.ts` | + `WsTicketResponse { token: string; expires_in: number }` |
| F2 | `packages/web/lib/api/auth.ts` | + `wsTicket: () => fetchApi<WsTicketResponse>("/auth/ws-ticket", { method: "POST" })` (Bearer attached by `core.ts`) |
| F3 | `packages/web/lib/api/writing-session-socket.ts` | Drop `userId` param + `user_id` URL param; add `ticketProvider: () => Promise<string>`; `connect()` awaits a fresh ticket per attempt before building the URL |
| F4 | `packages/web/components/studio/editor/useSessionSocket.ts` | Wire `ticketProvider` from `authApi.wsTicket()`; keep `userId` only as the auth-readiness gate; stop passing it to the socket |

### Tests (regression-first — written against the NEW contract; old `user_id`-based tests rewritten, not patched)

| # | File | Required cases |
|---|------|----------------|
| T1 | `tests/unit/api/auth/test_ws_tickets.py` **NEW** | issue→consume roundtrip returns bound `user_id`; second consume of same token raises; expired (injected `now`) raises; unknown token raises; all three failures raise the same `WsTicketError` type; `sweep_expired` drops expired-unused only |
| T2 | `tests/unit/api/writing/test_router_sessions_auth.py` **NEW** | connect **without** `token` → rejected 4401; with **foreign/unknown** token → 4401; with **consumed** ticket → 4401; with **expired** ticket → 4401; with **valid** ticket → session proceeds and handler/limits/rate-key receive the **ticket-bound** user id; connect with only the old `user_id` param → 4401 (param gone) |
| T3 | `tests/unit/api/writing/ws_test_helpers.py` + `test_router_sessions_{basic,recovery,validation}.py` | Rewritten: helper mints via `ws_tickets.issue()` and sends `token=`; remove all `user_id=` query usage |
| T4 | `tests/integration/writing/test_session_lifecycle.py`, `test_session_stop_and_recovery.py`, `_ws_db_isolation.py` | Same migration to ticket auth (issue via registry directly — no REST hop needed in integration setup) |
| T5 | `packages/web` socket tests (`writing-session-socket` / `useSessionSocket`) | URL contains `token`, never `user_id`; `ticketProvider` awaited per `connect()`; reconnect path fetches a fresh ticket |

**Acceptance gate (RULE-20):** T1+T2 green, all T3/T4 migrations green, web
build + tests green, `scripts/check_architecture.py` green — in the same slice
(**met 2026-08-30, commit `6f51129e`**), **plus a browser E2E exercise of the
ticket flow (connect → session → recovery) before the status flips.**
Then this ADR flips to ✅ Implemented.

---

## Review Trigger

- [ ] When the deployment ever scales to **multiple API workers/processes** —
      the in-memory registry must move to a shared store (same trigger as
      ADR-081 D1; single-process is the post-ADR-080 contract).
- [ ] When a **second WebSocket endpoint** appears — extract the handshake gate
      (ticket → origin → limits) into a shared WS-entry helper instead of
      copy-pasting `router_sessions.py`'s checks.
- [ ] When browsers ship **WebSocket header support** (or the web client is
      replaced by a non-browser client) — revisit the query-param transport;
      the consume seam is the single swap point.
- [ ] When TTL policy changes materially (e.g., tickets reused for
      multi-connection sessions) — single-use is a load-bearing security
      property; relaxing it requires re-review.
