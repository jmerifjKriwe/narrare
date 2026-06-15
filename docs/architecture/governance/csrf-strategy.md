# CSRF Strategy — State-Changing Endpoints

> **AUFG-05-08** deliverable
> **Date:** 2026-06-14
> **Reviewer:** Architecture Specialist
> **Status:** Decision complete — strategy chosen. Implementation complete (AUFG-05-13 resolved)

---

## 1. Scope & Method

This document records the CSRF (Cross-Site Request Forgery) strategy decision for all
state-changing HTTP endpoints in the Narrare backend (`apps/api/`).

### 1.1 Files and sources examined

| What | How | Result |
|------|-----|--------|
| Auth credential transport | `read apps/api/narrare/_app/dependencies_auth.py` | Backend authenticates via `HTTPBearer` (`Authorization` header), NOT cookies |
| Refresh cookie | `read apps/api/narrare/auth/cookie_helpers.py` | `narrare_refresh`: httpOnly, `path=/api/v1/auth`, `samesite=lax`, `secure=production` |
| Frontend token storage | `read packages/web/lib/api/core.ts` | Access token in JS memory (`_accessToken`), mirrored to `narrare_auth` non-httpOnly cookie for Next.js proxy route protection |
| `narrare_auth` cookie backend usage | `grep narrare_auth apps/api/**/*.py` | **NOT FOUND** — backend never reads `narrare_auth` for authentication |
| CORS configuration | `read apps/api/narrare/_app/main.py:41-47` | Dev/test: `["http://localhost:3000"]`; Production: `[]` (CORS disabled) |
| Production topology | `read docs/development/deployment-guide.md:398-419` | Next.js (port 3000, external) reverse-proxies `/api/v1/*` to FastAPI (port 8000, `127.0.0.1` internal) |
| Next.js rewrite | `read packages/web/next.config.ts:15-22` | `/api/v1/:path*` → backend — same-origin from browser |
| Frontend proxy | `read packages/web/proxy.ts` | Reads `narrare_auth` cookie for server-side route protection only (redirect to /login) |
| State-changing endpoints | `grep @router.(post\|put\|patch\|delete) apps/api/**/*.py` | 99 route handlers across all domain modules |
| Existing CSRF mechanisms | `grep csrf\|CSRF\|Origin\|Referer apps/api/**/*.py` | **NONE** — no CSRF middleware, no Origin/Referer validation |
| WebSocket session | `read apps/api/narrare/writing/router_sessions.py` | Accepts `user_id` as query parameter; no Origin validation |
| Auth router | `read apps/api/narrare/auth/router.py` | register/login: body auth; refresh/logout: cookie-based |
| Prior security audit | `read docs/architecture/governance/security-audit-cors-rate-limiting.md` | CORS audit (PASS), rate-limiting matrix, accepted risks AR-05-02/03/04 |
| ADR-009 addendum | `read docs/architecture/decisions/ADR-009-security-modernization.md:185-193` | Documents httpOnly refresh cookie + in-memory access token design |

---

## 2. Current Credential Transport Model

Understanding how credentials are transported is the foundation of CSRF analysis. CSRF
exploits the browser's **automatic credential attachment**. If the browser does not
automatically attach a credential that the backend trusts, CSRF is structurally
inapplicable.

### 2.1 Two credential channels

| Credential | Transport | Auto-attached by browser? | Backend trusts it? |
|------------|-----------|--------------------------|-------------------|
| **Access token (JWT)** | `Authorization: Bearer <token>` header, set from in-memory JS variable | **NO** — cross-origin JS cannot read the in-memory token; the browser only auto-attaches cookies, not Authorization headers | **YES** — `HTTPBearer` in `get_current_user_id` |
| **Refresh token** | `narrare_refresh` cookie (httpOnly, `path=/api/v1/auth`, SameSite=Lax) | Only on same-site requests to `/api/v1/auth/*` | **YES** — `/auth/refresh` and `/auth/logout` only |
| `narrare_auth` cookie | Non-httpOnly cookie (`path=/`, SameSite=Lax), set by frontend JS | Yes, to all same-site paths | **NO** — backend never reads it; only Next.js `proxy.ts` uses it for route protection |

### 2.2 The structural CSRF defense: Bearer-token authentication

The decisive architectural fact is: **all state-changing endpoints except `/auth/refresh`
and `/auth/logout` authenticate via the `Authorization: Bearer` header, not via cookies.**

The browser does not automatically attach `Authorization` headers to cross-origin
requests. The access token lives in JavaScript memory (`_accessToken` in `core.ts`),
and cross-origin JavaScript cannot read it due to the same-origin policy. Therefore:

> **A CSRF attacker cannot make the victim's browser send a valid `Authorization: Bearer`
> header to a state-changing endpoint. CSRF is structurally inapplicable to all
> Bearer-authenticated endpoints.**

This is the OWASP-recommended posture: *"If you're using Bearer tokens (Authorization
header), CSRF protection is not required for those requests because the browser does not
automatically attach the token."* (OWASP CSRF Prevention Cheat Sheet)

### 2.3 The cookie-authenticated endpoints

Only two endpoints use cookie-based authentication:

| Endpoint | Method | Cookie used | CSRF impact if exploited |
|----------|--------|------------|--------------------------|
| `/api/v1/auth/refresh` | POST | `narrare_refresh` | Token rotation — attacker cannot read the response (CORS blocks cross-origin response reading). Worst case: denial-of-service (other devices logged out). No data integrity violation. |
| `/api/v1/auth/logout` | POST | `narrare_refresh` | Clears cookie. Worst case: user is logged out. No data integrity violation. |

Both endpoints accept POST only (no GET state-changing auth endpoints exist), and both
are protected by SameSite=Lax.

---

## 3. CSRF-Resistenz-Analyse

### 3.1 Vectors already covered

| Attack vector | Covered by | Evidence |
|---------------|-----------|----------|
| Cross-site POST to Bearer-authenticated endpoints (novels, chapters, settings, KB, writing, planning, analysis, prompts, memory, templates, wiki, volumes) | **Bearer-token auth** — browser cannot forge `Authorization` header | `get_current_user_id` uses `HTTPBearer`; token is in-memory JS, not a cookie |
| Cross-site POST to `/auth/refresh` | **SameSite=Lax** — cross-site POSTs are not top-level navigations; cookie is not sent | `cookie_helpers.py:42` `samesite="lax"`; path-restricted to `/api/v1/auth` |
| Cross-site POST to `/auth/logout` | **SameSite=Lax** | Same as above |
| Cross-site GET navigation to state-changing endpoint | **No GET state-changing endpoints exist** — all mutations are POST/PUT/PATCH/DELETE | Endpoint inventory §4 confirms |
| Cross-origin fetch/XHR with credentials | **CORS disabled in production** (same-origin proxy) + **SameSite=Lax** | `main.py:43` `allow_origins=[]` in production |
| Form-based CSRF (content-type spoofing) | **JSON-only API** — Pydantic validation rejects non-JSON bodies with 422 | All routers use `Request` Pydantic models; `Content-Type: application/json` required |
| `narrare_auth` cookie exploitation | **Backend does not read `narrare_auth` for authentication** — it only exists for Next.js proxy route protection | `grep narrare_auth apps/api/**/*.py` → no matches |

### 3.2 Vectors remaining open (theoretical)

| Vector | Risk level | Explanation |
|--------|-----------|-------------|
| **Subdomain CSRF** (same-site, cross-origin) | Low (theoretical) | SameSite considers the registrable domain (eTLD+1). `evil.narrare.app` → `app.narrare.app` is same-site. If an attacker controls a subdomain, SameSite=Lax does not block their POSTs. **Not exploitable in current deployment** — Narrare is local-first, single-domain Docker deployment. Becomes relevant only under AE-05-02 (managed hosting with subdomains). |
| **SameSite=Lax 2-minute window** | Negligible | Some browsers (Chrome) allow POST with SameSite=Lax cookies for newly-set cookies (< 2 minutes old). This affects `/auth/refresh` and `/auth/logout` only. Impact: token rotation or logout — no data integrity violation. |
| **No explicit Origin/Referer validation** | Low | No middleware checks the `Origin` or `Referer` header on any request. Defense relies entirely on SameSite=Lax + Bearer auth. Origin/Referer validation would add defense-in-depth. |
| **Cross-Site WebSocket Hijacking (CSWSH)** | Medium | The WebSocket endpoint `/writing/sessions/{chapter_id}` accepts `user_id` as a query parameter and does NOT validate the `Origin` header. A cross-origin page could open a WebSocket connection. This is primarily an auth weakness (query-param auth) that overlaps with CSRF. See AUFG-05-13. |

### 3.3 Why no Double-Submit-Token is needed

A Double-Submit-CSRF-Token protects against the case where the browser auto-attacks a
cookie that the backend trusts for authentication. In Narrare's architecture:

- **State-changing endpoints** authenticate via `Authorization: Bearer` (not a cookie).
  The browser does not auto-attach this. CSRF is structurally impossible.
- **Cookie-authenticated endpoints** (`/auth/refresh`, `/auth/logout`) are already
  protected by SameSite=Lax and have no data-integrity impact if CSRF succeeds.

Adding a Double-Submit-Token would protect against a vector that does not exist in the
current architecture. It would add complexity (token generation, client-server
coordination, contract, test surface) without proportional security benefit.

---

## 4. State-Changing Endpoint Inventory

Every state-changing endpoint class is classified by its CSRF relevance:

**Legend:**
- **N/A (Bearer)**: CSRF structurally inapplicable — endpoint authenticates via
  `Authorization: Bearer` header, which the browser cannot auto-attach cross-origin.
- **Cookie-protected**: Endpoint uses cookie-based auth; protected by SameSite=Lax.
- **N/A (no auth)**: Pre-auth endpoint with no credential to forge.

### 4.1 Auth

| Endpoint | Method | Auth mechanism | CSRF class |
|----------|--------|---------------|------------|
| `/auth/register` | POST | Body (email/password) | N/A (no session credential to forge — creates new session) |
| `/auth/login` | POST | Body (email/password) | N/A (creates new session) |
| `/auth/refresh` | POST | `narrare_refresh` cookie | Cookie-protected (SameSite=Lax, path=/api/v1/auth) |
| `/auth/logout` | POST | `narrare_refresh` cookie | Cookie-protected (SameSite=Lax) |

### 4.2 Settings

| Endpoint | Method | Auth mechanism | CSRF class |
|----------|--------|---------------|------------|
| `/settings/user` | PATCH | Bearer | N/A (Bearer) |
| `/settings/novels/{id}` | PATCH | Bearer | N/A (Bearer) |
| `/settings/ai` | PATCH | Bearer | N/A (Bearer) |
| `/settings/ai/novels/{id}` | PATCH | Bearer | N/A (Bearer) |
| `/settings/ai/providers` | POST | Bearer | N/A (Bearer) |
| `/settings/ai/providers/{id}` | PATCH/DELETE | Bearer | N/A (Bearer) |
| `/settings/tones` | POST/PUT/DELETE | Bearer | N/A (Bearer) |
| `/settings/models/refresh` | POST | Bearer | N/A (Bearer) |
| `/settings/token-limits/user` | PUT | Bearer | N/A (Bearer) |
| `/settings/token-limits/project/{id}` | PUT | Bearer | N/A (Bearer) |

### 4.3 Knowledge Base (KB)

| Endpoint | Method | Auth mechanism | CSRF class |
|----------|--------|---------------|------------|
| `/novels/{id}/kb/entries` | POST | Bearer | N/A (Bearer) |
| `/novels/{id}/kb/entries/{id}` | PATCH/DELETE | Bearer | N/A (Bearer) |
| `/novels/{id}/kb/extract/{chapter_id}` | POST | Bearer | N/A (Bearer) |
| `/novels/{id}/kb/extract/apply` | POST | Bearer | N/A (Bearer) |
| `/novels/{id}/kb/sessions` | POST | Bearer | N/A (Bearer) |
| `/novels/{id}/kb/sessions/{id}/...` | POST/PATCH/DELETE | Bearer | N/A (Bearer) |
| `/novels/{id}/kb/consistency` | POST | Bearer | N/A (Bearer) |
| `/novels/{id}/kb/improve` | POST | Bearer | N/A (Bearer) |
| `/novels/{id}/kb/worldbuilding` | POST | Bearer | N/A (Bearer) |
| `/novels/{id}/kb/relationships` | POST/DELETE | Bearer | N/A (Bearer) |
| `/novels/{id}/kb/references` | POST | Bearer | N/A (Bearer) |
| `/novels/{id}/kb/merge` | POST | Bearer | N/A (Bearer) |

### 4.4 Writing

| Endpoint | Method | Auth mechanism | CSRF class |
|----------|--------|---------------|------------|
| `/writing/chapters/{id}/generate` | POST | Bearer | N/A (Bearer) |
| `/writing/chapters/{id}/extend` | POST | Bearer | N/A (Bearer) |
| `/writing/chapters/{id}/rewrite` | POST | Bearer | N/A (Bearer) |
| `/writing/chapters/{id}/suggest` | POST | Bearer | N/A (Bearer) |
| `/writing/chapters/{id}/co-author` | POST | Bearer | N/A (Bearer) |
| `/writing/chapters/{id}/co-author/apply` | POST | Bearer | N/A (Bearer) |
| `/writing/chapters/{id}/co-author/feedback` | POST | Bearer | N/A (Bearer) |
| `/writing/chapters/{id}/summary` | POST | Bearer | N/A (Bearer) |
| `/writing/generation/{id}` | DELETE | Bearer | N/A (Bearer) |
| `/writing/generation/{id}/accept` | POST | Bearer | N/A (Bearer) |
| `/writing/generation/{id}/reject` | POST | Bearer | N/A (Bearer) |
| `/writing/stats` | POST | Bearer | N/A (Bearer) |
| `/writing/sessions/{chapter_id}` | **WebSocket** | Query param `user_id` | **CSWSH risk** — no Origin validation. See AUFG-05-13. |

### 4.5 Planning

| Endpoint | Method | Auth mechanism | CSRF class |
|----------|--------|---------------|------------|
| `/planning/...` | POST/PUT | Bearer | N/A (Bearer) |
| `/planning/timeline-analysis` | POST | Bearer | N/A (Bearer) |

### 4.6 Analysis

| Endpoint | Method | Auth mechanism | CSRF class |
|----------|--------|---------------|------------|
| `/analysis/{path}` | POST | Bearer | N/A (Bearer) |
| `/consistency/{path}` | POST | Bearer | N/A (Bearer) |

### 4.7 Prompt Management

| Endpoint | Method | Auth mechanism | CSRF class |
|----------|--------|---------------|------------|
| `/prompts/{id}` | PUT | Bearer | N/A (Bearer) |
| `/prompts/{id}/override` | DELETE | Bearer | N/A (Bearer) |

### 4.8 Memory / Feedback

| Endpoint | Method | Auth mechanism | CSRF class |
|----------|--------|---------------|------------|
| `/memory/feedback` | POST | Bearer | N/A (Bearer) |
| `/memory/preferences` | DELETE | Bearer | N/A (Bearer) |
| `/memory/analyze` | POST | Bearer | N/A (Bearer) |

### 4.9 Other CRUD (novels, chapters, volumes, templates, wiki, embeddings, generation, chat)

| Endpoint | Method | Auth mechanism | CSRF class |
|----------|--------|---------------|------------|
| All POST/PUT/PATCH/DELETE endpoints | Mutative | Bearer | N/A (Bearer) |

### 4.10 Setup

| Endpoint | Method | Auth mechanism | CSRF class |
|----------|--------|---------------|------------|
| `/setup/validate/step-{1..4}` | POST | None (pre-auth) | N/A (no session credential to forge) |
| `/setup/providers/{p}/models` | GET | None (pre-auth) | N/A (read-only + no auth) |
| `/setup/complete` | POST | Bearer | N/A (Bearer) |

### 4.11 Inventory summary

| CSRF class | Endpoint count | CSRF risk |
|------------|---------------|-----------|
| N/A (Bearer) | ~85 route handlers | None — CSRF structurally inapplicable |
| Cookie-protected (SameSite=Lax) | 2 (`/auth/refresh`, `/auth/logout`) | Low — SameSite=Lax + no data-integrity impact |
| N/A (no auth) | ~6 setup/validation routes | None |
| CSWSH risk (WebSocket) | 1 (`/writing/sessions/{id}`) | Medium — separate auth + Origin concern |

---

## 5. Options Considered

### Option A — SameSite=Lax + Origin/Referer validation (chosen)

**Description:** Maintain the existing SameSite=Lax cookie policy. Add server-side
`Origin`/`Referer` header validation for all state-changing requests (POST/PUT/PATCH/
DELETE) as defense-in-depth. Requests without a valid `Origin` are allowed only if they
carry a valid `Authorization: Bearer` token (programmatic clients).

**Pros:**
- Closes the theoretical subdomain-CSRF and Lax-2-minute-window gaps for cookie endpoints
- OWASP-recommended defense-in-depth for APIs
- No client-side changes required — `Origin` is auto-set by browsers
- Compatible with all 4 client types: browser sends `Origin`; CLI/MCP/A2A send Bearer
  tokens (validated, then Origin check skipped)
- Minimal implementation surface: one middleware or dependency
- No token management, storage, or coordination overhead

**Cons:**
- Requires trusted-origin configuration (env var)
- Adds one validation layer to every state-changing request
- `Origin`/`Referer` headers can theoretically be stripped by misconfigured proxies
  (mitigated: requests without Origin are allowed if Bearer-authenticated)

**Trade-offs accepted:**
- Relies on the architectural invariant that backend uses Bearer auth (not cookie auth)
  for state-changing endpoints. If this invariant changes, re-review is mandatory.

### Option B — Double-Submit-Token (rejected)

**Description:** Generate a CSRF token on login, store it in a cookie (separate from
the auth cookie), require the frontend to echo it in a custom header
(`X-CSRF-Token`) on every state-changing request, and validate server-side.

**Pros:**
- Industry-standard CSRF defense
- Independent of SameSite cookie behavior
- Covers subdomain CSRF and all cookie-based edge cases

**Cons:**
- **Solves a problem that does not exist:** CSRF is structurally inapplicable to
  Bearer-authenticated endpoints. The token adds overhead without proportional benefit.
- Adds significant complexity: token generation, storage (cookie or server-side),
  client-server coordination, contract definition, frontend integration for all API calls
- Breaks the "fetch wrapper" abstraction: every `fetchApi()` call must include the token
- Introduces a new cookie (`narrare_csrf`), increasing the cookie attack surface
- Incompatible with programmatic clients (MCP/A2A/CLI) without exempting them — which
  defeats the purpose if the exemption is "has Bearer token"
- Violates KISS: the simplest *correct* solution is Bearer auth + Origin validation

**Decision: Rejected.** The Double-Submit-Token protects against cookie-based CSRF, but
Narrare does not use cookie-based auth for state-changing endpoints. The token would be
defensive infrastructure against a non-existent vector.

### Option C — SameSite=Strict for refresh cookie (rejected)

**Description:** Change `narrare_refresh` cookie from `SameSite=Lax` to `SameSite=Strict`.

**Pros:**
- Strongest cookie-level CSRF protection — cookie never sent on cross-site requests,
  including top-level GET navigations

**Cons:**
- **Breaks session restoration:** When a user navigates directly to the app from an
  external link (email, bookmark, shared URL), SameSite=Strict prevents the refresh
  cookie from being sent on the initial page load. The `restoreSession()` function in
  `core.ts:87-95` calls `/api/v1/auth/refresh`, which would fail silently, redirecting
  the user to `/login` even though they have a valid session. This is a UX regression.
- Does not address the WebSocket CSWSH vector
- Overkill: the refresh endpoint has no data-integrity impact (token rotation only)
- Inconsistent: would need to keep `narrare_auth` as SameSite=Lax for Next.js proxy to
  work, creating an inconsistent cookie policy

**Decision: Rejected.** The UX regression (broken direct navigation session restore)
is unacceptable for a protection that is unnecessary given SameSite=Lax already blocks
cross-site POSTs.

### Option D — Combination: SameSite=Lax + Origin/Referer + Double-Submit-Token (rejected)

**Description:** Layer all defenses: SameSite=Lax cookies, Origin/Referer validation,
AND Double-Submit-Token.

**Pros:**
- Maximum defense-in-depth

**Cons:**
- All cons of Option B (token complexity) for no additional security benefit over
  Option A
- Violates the sustainability check: "Is this the simplest *correct* solution?" — No.
- Creates maintenance burden and cognitive load for future developers

**Decision: Rejected.** Defense-in-depth should be proportional to the threat. Option A
already provides correct, proportionate defense. Adding a token layer is over-engineering.

---

## 6. Decision

### Chosen strategy: Option A — SameSite=Lax + Origin/Referer validation

The CSRF strategy for Narrare is:

1. **Bearer-token authentication** (existing, unchanged): All state-changing endpoints
   authenticate via `Authorization: Bearer` header. CSRF is structurally inapplicable
   because the browser cannot auto-attach this header cross-origin.

2. **SameSite=Lax cookies** (existing, unchanged): The `narrare_refresh` cookie uses
   `samesite=lax` + `path=/api/v1/auth`. This blocks cross-site POSTs to the only two
   cookie-authenticated endpoints (`/auth/refresh`, `/auth/logout`).

3. **Origin/Referer validation** (NEW — follow-up AUFG-05-13): Add server-side
   validation of the `Origin` (or `Referer` fallback) header for all state-changing
   requests (POST/PUT/PATCH/DELETE). Requests from untrusted origins are rejected with
   HTTP 403. Requests without an `Origin` header are allowed only if they carry a valid
   `Authorization: Bearer` token (programmatic clients: CLI/MCP/A2A).

4. **WebSocket Origin validation** (NEW — follow-up AUFG-05-13): The WebSocket endpoint
   `/writing/sessions/{chapter_id}` must validate the `Origin` header during the
   handshake to prevent Cross-Site WebSocket Hijacking (CSWSH).

### Rationale

The root cause of CSRF is the browser's automatic attachment of cookies that the backend
trusts for authentication. Narrare's architecture eliminates this root cause for all
state-changing endpoints by using Bearer-token authentication. The only cookie-based
endpoints (`/auth/refresh`, `/auth/logout`) are already protected by SameSite=Lax and
have no data-integrity impact.

Origin/Referer validation is added as defense-in-depth (OWASP-recommended) to close
theoretical gaps (subdomain CSRF, Lax-2-minute window) without the complexity of a
Double-Submit-Token. It is compatible with all 4 client types because programmatic
clients (CLI/MCP/A2A) authenticate via Bearer tokens and are exempt from Origin checks.

---

## 7. Compatibility Assessment

### 7.1 httpOnly Refresh Cookie

✅ **Compatible.** The refresh cookie (`narrare_refresh`) maintains its current
attributes: `httpOnly=True`, `secure=production`, `samesite=lax`, `path=/api/v1/auth`.
Origin/Referer validation does not modify cookie behavior — it validates the request
origin independently. SameSite=Lax is retained (not changed to Strict) to preserve
`restoreSession()` functionality on direct navigation.

### 7.2 In-Memory Access Token

✅ **Compatible.** The in-memory access token (`_accessToken` in `core.ts`) is sent as
`Authorization: Bearer` header. This is the primary CSRF defense — the browser cannot
auto-attach it cross-origin. The strategy does not change token storage or transport.

### 7.3 `narrare_auth` Cookie (Next.js Proxy)

✅ **Compatible.** The `narrare_auth` non-httpOnly cookie exists for Next.js `proxy.ts`
server-side route protection. The backend does not read it for authentication. The
strategy does not affect this cookie. **Architectural invariant:** the backend must
never add cookie-based authentication reading `narrare_auth`. If it does, CSRF posture
changes and this strategy must be re-reviewed.

### 7.4 WebUI/API-Proxy Behavior

✅ **Compatible.** In production, Next.js (port 3000) reverse-proxies `/api/v1/*` to
FastAPI (port 8000, internal). All API requests are same-origin from the browser's
perspective. The `Origin` header will match the deployed domain. Origin/Referer
validation trusts the configured origin(s).

### 7.5 Four-Client Model (RULE-12)

✅ **Compatible.** All 4 client types are handled:

| Client | Auth method | Origin header | Origin validation behavior |
|--------|------------|---------------|---------------------------|
| **WebUI** (browser) | Bearer (in-memory) + refresh cookie | Sent by browser | Validated — same-origin in production |
| **CLI** | Bearer (config/env) | Not sent | Exempt (valid Bearer token present) |
| **MCP** | Bearer (config) | Not sent | Exempt (valid Bearer token present) |
| **A2A** | Bearer (service auth) | Not sent | Exempt (valid Bearer token present) |

No client calls another client's transport. All authenticate via the Service Layer
(Bearer tokens issued by the auth service). The Origin check is a defense-in-depth
layer that only applies to browser-originated requests (which have an `Origin` header).

---

## 8. Accepted Risk: No Double-Submit-Token

### AR-05-05 — No Double-Submit-CSRF-Token

| Field | Value |
|-------|-------|
| ID | AR-05-05 |
| Type | `accepted_risk` |
| Risk | No Double-Submit-CSRF-Token is used. CSRF defense relies on (1) Bearer-token authentication for all state-changing endpoints, (2) SameSite=Lax for cookie-authenticated auth endpoints, and (3) Origin/Referer validation (to be implemented per AUFG-05-13). |
| Owner | Architecture Specialist |
| Rationale | The backend authenticates state-changing endpoints via `Authorization: Bearer` headers, not cookies. CSRF is structurally inapplicable because the browser cannot auto-attach `Authorization` headers cross-origin. The only cookie-authenticated endpoints (`/auth/refresh`, `/auth/logout`) are protected by SameSite=Lax and have no data-integrity impact (token rotation, logout). A Double-Submit-Token would protect against a vector that does not exist in the current architecture, adding complexity without proportional benefit. |
| Controls | (1) Bearer-token auth via `HTTPBearer` in `get_current_user_id` (`apps/api/narrare/_app/dependencies_auth.py`). (2) SameSite=Lax + path-restriction on `narrare_refresh` cookie (`apps/api/narrare/auth/cookie_helpers.py`). (3) JSON-only API (Pydantic rejects non-JSON bodies). (4) CORS disabled in production (same-origin proxy). (5) Origin/Referer validation per AUFG-05-13 (implemented). (6) Architectural invariant: backend must never add cookie-based auth for state-changing endpoints (enforced by this document + code review). |
| Review trigger/date | Re-review if: (a) cookie-based authentication is added to any state-changing endpoint, (b) AE-05-02 (managed hosting) is promoted introducing subdomains, (c) WebSocket auth model changes, or (d) by 2027-06-14 if no change. |
| Release trigger | Origin/Referer validation (AUFG-05-13) should be implemented before public release or managed hosting promotion. Until then, the current posture (Bearer auth + SameSite=Lax) is safe for local-first single-user deployment. |
| Source | AUFG-05-08 CSRF strategy decision |

---

## 9. Follow-up AUFG: AUFG-05-13 — ✅ IMPLEMENTED

### AUFG-05-13 — Origin/Referer Validation + WebSocket Origin Check

| Field | Value |
|-------|-------|
| ID | AUFG-05-13 |
| Title | Origin/Referer Validation for State-Changing Requests + WebSocket Origin Check |
| Source | AUFG-05-08 CSRF strategy — defense-in-depth layer to close subdomain CSRF, Lax-2-minute-window, and CSWSH gaps. |
| Status | `open` |
| Priority | P1 (before public release / managed hosting) |
| Area | Security, Backend middleware, WebSocket |
| Owner role | Backend/Security Specialist |
| Dependencies | CSRF strategy decision (this document); trusted-origin configuration; existing middleware stack in `apps/api/narrare/_app/middleware.py`; WebSocket endpoint `apps/api/narrare/writing/router_sessions.py`. |
| Review trigger | Before public release, or when AE-05-02 (managed hosting) is promoted. |

**Scope:**

1. **Origin/Referer validation middleware:**
   - Apply to all state-changing HTTP methods: POST, PUT, PATCH, DELETE
   - Skip safe methods: GET, HEAD, OPTIONS
   - Validate `Origin` header (fallback: `Referer` header) against configured trusted origins
   - Trusted origins: configurable via `Settings.csrf_trusted_origins` (default:
     `["http://localhost:3000"]` for dev/test; production: the deployed origin)
   - Requests with matching Origin → allowed
   - Requests with non-matching Origin → **HTTP 403 Forbidden** with
     `{"detail": "Origin not allowed", "code": "CSRF_ORIGIN_MISMATCH"}`
   - Requests without `Origin` AND without `Referer` → allowed **only if** a valid
     `Authorization: Bearer` token is present (programmatic clients: CLI/MCP/A2A)
   - Requests without `Origin` AND without `Referer` AND without Bearer → **HTTP 403**

2. **WebSocket Origin validation:**
   - Validate `Origin` header during WebSocket handshake on `/writing/sessions/{chapter_id}`
   - Reject connections with non-trusted Origin (close with code 4001 + reason)
   - See CSWSH risk in §3.2

3. **Configuration:**
   - Add `csrf_trusted_origins: list[str]` to `Settings` model
   - Default: `["http://localhost:3000"]` (dev); production sets via env var
   - Integrate with existing `settings.is_production` gating pattern

**Acceptance criteria:**
- All POST/PUT/PATCH/DELETE requests are validated against trusted origins
- Same-origin requests are accepted (200)
- Cross-origin requests are rejected (403)
- Bearer-authenticated requests without Origin are accepted (programmatic clients)
- WebSocket connections validate Origin during handshake
- Integration tests cover accepted, rejected, and exempt scenarios
- No router-level hardcoded security — middleware or dependency-based
- Error response includes machine-readable `code` field

**Contract specification (for implementation):**

Error response schema:
```json
{
  "detail": "Origin not allowed",
  "code": "CSRF_ORIGIN_MISMATCH"
}
```

No new service-layer contract needed — Origin validation is HTTP middleware, not a
business-logic concern. RULE-06 compliant (middleware has one responsibility: CSRF
origin validation; it does not contain business logic).

**Definition of Done:**
- Middleware implemented in `apps/api/narrare/_app/middleware.py`
- WebSocket Origin check implemented in `router_sessions.py`
- `Settings.csrf_trusted_origins` field added
- Integration tests cover: same-origin accepted, cross-origin rejected, no-Origin-with-
  Bearer accepted, no-Origin-without-Bearer rejected, WebSocket origin validated
- Registry entry updated with exit evidence

---

## 10. RULE-XX Compliance Assessment

| Rule | Status | Notes |
|------|--------|-------|
| RULE-06 | ✅ | CSRF strategy is middleware-level (one responsibility); no business logic in the validation layer |
| RULE-07 | ✅ | CSRF middleware lives in `apps/api/`; no `core/` import dependency direction issue |
| RULE-09 | ✅ | All public interfaces fully typed (when implemented: middleware signature, Settings field) |
| RULE-11 | ✅ | No silent failures — CSRF rejection returns explicit HTTP 403 with error code |
| RULE-12 | ✅ | Strategy compatible with all 4 clients (WebUI, MCP, A2A, CLI); Service Layer remains the only public API |
| RULE-18 | ✅ | Trusted origins are configurable via Settings, not hardcoded in routers |
| RULE-21 | ✅ | This document constitutes a re-review trigger for CSRF/auth changes |

---

## 11. Root-Cause Analysis

### Symptom
CSRF token validation was not explicitly decided for state-changing endpoints (Review-05,
ADR-047 §Context).

### Root cause
The security modernization (ADR-009) introduced httpOnly refresh cookies and in-memory
access tokens but did not explicitly document the CSRF posture. The implicit defense
(Bearer-token auth + SameSite=Lax) was architecturally sound but undocumented, creating
uncertainty about whether additional CSRF controls were needed.

### Design (this strategy)
This strategy documents the implicit CSRF defense (Bearer-token auth makes CSRF
structurally inapplicable), adds Origin/Referer validation as explicit defense-in-depth
(AUFG-05-13), and records the accepted risk of not using a Double-Submit-Token (AR-05-05)
with rationale, controls, and review triggers.

---

## 12. Architectural Invariants

The following invariants MUST hold for this CSRF strategy to remain valid. If any is
violated, this strategy must be re-reviewed and AUFG-05-08 re-opened.

| # | Invariant | Enforcement |
|---|-----------|-------------|
| INV-1 | The backend authenticates all state-changing endpoints via `Authorization: Bearer` header (`HTTPBearer`), NOT via cookies | Code review + `check_architecture.py`; this document |
| INV-2 | The backend never reads `narrare_auth` cookie for authentication | Code review; `grep narrare_auth apps/api/**/*.py` returns no auth-reading results |
| INV-3 | The `narrare_refresh` cookie maintains `samesite=lax` (not `none`) and `path=/api/v1/auth` | `cookie_helpers.py`; code review |
| INV-4 | No GET endpoint performs state-changing operations (all mutations are POST/PUT/PATCH/DELETE) | Endpoint inventory §4; code review |
| INV-5 | If cookie-based authentication is ever added to state-changing endpoints, a Double-Submit-Token or equivalent CSRF defense MUST be introduced | This document; AUFG-05-08 re-review trigger |

---

## 13. Definition of Done (AUFG-05-08)

- [x] A tracked CSRF strategy decision exists and explicitly covers browser WebUI, MCP,
      A2A, and CLI clients without making one client call another (§7.5)
- [x] Every state-changing route category is classified as protected, not applicable, or
      covered by a stronger same-site/token/auth mechanism (§4 inventory)
- [x] Chosen strategy includes failure semantics, test strategy, and migration impact
      (§6 decision, §9 follow-up AUFG acceptance criteria)
- [x] Any exception is documented as `accepted_risk` with owner, controls, and review
      date (AR-05-05 in §8)
- [x] Minimum 2 alternatives evaluated with trade-offs (§5: Options A, B, C, D)
- [x] This document is a tracked artefact in `docs/architecture/governance/`
- [x] Registry entry updated with exit evidence (AUFG-05-08 status → `resolved`)
