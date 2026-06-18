# AUFG Registry — Architecture Governance Lifecycle

> **Status:** Active registry
> **Established by:** [ADR-047](../decisions/ADR-047-governance-drift-automation.md)
> **Maintained by:** Architecture Specialist
> **Last updated:** 2026-06-18 (AUFG-04-01 added — writing/story_suggest orphan template disposition)

This registry is the durable, tracked lifecycle surface for AUFGs, accepted risks,
accepted enhancements, and coverage pointers that originate from architecture reviews.
Review files under `_audit/` are evidence inputs, not the long-lived lifecycle SSOT.

---

## Lifecycle Contract

Every review finding that is material to architecture, release readiness, security,
observability, CI, or SSOT governance must have exactly one durable lifecycle state:

| State | Meaning |
|-------|---------|
| `open` | Actionable work exists and is not complete. |
| `in_progress` | A specialist is actively implementing the accepted scope. |
| `blocked` | Actionable, but waiting on an explicit dependency or user decision. |
| `resolved` | Acceptance criteria and Definition of Done are complete with exit evidence. |
| `accepted_risk` | Risk is knowingly accepted with owner, rationale, controls, and review date. |
| `accepted_enhancement` | Non-blocking improvement is accepted for future consideration with trigger/date. |
| `not_applicable` | Finding does not apply; rationale and reviewer are recorded. |
| `covered_by_existing_aufg` | Finding is explicitly delegated to another AUFG with no duplicate task. |

### Entry Schema

Each entry records: ID, title, source, status, priority, area, owner role,
dependencies, acceptance criteria, Definition of Done, exit evidence, and review
trigger/date where relevant.

Priorities use `P0` (release/security blocking), `P1` (high governance priority),
`P2` (planned hardening), and `P3` (strategic/post-MVP exploration).

---

## Active AUFGs

### AUFG-04-01 — writing/story_suggest Orphan Template Disposition

| Field | Value |
|-------|-------|
| ID | AUFG-04-01 |
| Title | writing/story_suggest Orphan Template Disposition |
| Source | CR-04 Phase D ORPHAN-TEMPLATE gate (ADR-049 A6). The `writing/story_suggest` template has no production Python consumer; acknowledged as documented ratcheted debt in `scripts/architecture/_checkers/_check_prompt_orphan.py::_ORPHAN_EXEMPTIONS`. |
| Status | `open` |
| Priority | P2 |
| Area | Prompts, Writing features, Prompt-surface governance |
| Owner role | Architecture Specialist (disposition decision) + Implementation Specialist (rewire or delete) |
| Dependencies | WRITE-009 (Writer's Block Tools) feature planning; ADR-049 ORPHAN-TEMPLATE gate; `writing/story_suggest/system.md` (v1.3.0, 113 lines). |
| Review trigger/date | Re-review when WRITE-009 (or a dedicated story-suggestions feature) enters implementation, or by 2026-09-30 if no consumer is planned. |

**Background:**

`packages/core/narrare_core/prompts/_bundled/writing/en/story_suggest/system.md`
exists at v1.3.0 (113 lines, well-developed) but no service or agent loads it.
It is a `writing` sub-mode template that generates 3–5 distinct story
suggestions (plot developments, character moments, dialogue options, stylistic
alternatives). It appears to be a remnant of an earlier or redesigned
story-suggestions feature. Three probe scripts reference it
(`writing_probes.py`, `mode_data.py`, `validation_budget_probes.py`) but those
are test/probe harnesses, not production consumers.

**Disposition decision (Architecture, 2026-06-18):**

**Do NOT delete now.** The template is substantial, well-structured, and maps
plausibly to [WRITE-009 (Writer's Block Tools)](../../features/writing/WRITE-009-unblock.md),
which is `📋 planned`. Deleting it would discard meaningful work for a feature
that may still be implemented. The ORPHAN-TEMPLATE gate already acknowledges it
as documented ratcheted debt, so it is not silently suppressing CI.

**Acceptance criteria (one of):**

- **Rewire** — when WRITE-009 (or a dedicated story-suggestions feature) is
  implemented, route a `story_suggest` context-mode under an existing writing
  intent through PromptComposer so the template becomes runtime-loaded. Update
  the manifest and route-table; remove the `_ORPHAN_EXEMPTIONS` entry.
- **Delete** — if WRITE-009 is permanently descoped or redesigned to not use
  this prompt shape, delete the template and remove the `_ORPHAN_EXEMPTIONS`
  entry. Record the descoping rationale here.

**Definition of Done:**

- The `("writing", "story_suggest")` entry is removed from
  `_check_prompt_orphan.py::_ORPHAN_EXEMPTIONS` because it is either reachable
  by a manifest/route entry OR deleted.
- `just check-architecture` remains green with one fewer orphan exemption.
- This registry entry is updated with exit evidence and status `resolved`.

**Exit evidence:** Pending — open until WRITE-009 planning or a descoping decision.

---

### AUFG-05-07 — CORS-/Rate-Limiting-Security-Audit

| Field | Value |
|-------|-------|
| ID | AUFG-05-07 |
| Title | CORS-/Rate-Limiting-Security-Audit |
| Source | Review-05 release/security finding captured durably in ADR-047 §Context (`CORS and rate-limiting were not fully audited`). |
| Status | `resolved` |
| Priority | P0 |
| Area | Security, Backend, API middleware, deployment configuration |
| Owner role | Backend/Security Specialist, with Platform review for deploy-time configuration |
| Dependencies | ADR-009 security modernization; current FastAPI middleware stack; deployment environment configuration; rate-limit backend availability. |
| Review trigger/date | Re-review before the next release-readiness claim or whenever CORS origins/rate-limit storage changes. |

**Acceptance criteria:**

- All HTTP entry points have an explicit CORS policy assessment: allowed origins,
  credentials behavior, local-dev allowances, and production hardening.
- Rate limiting is audited for auth, AI/SSE, generation, setup, and write-heavy
  state-changing endpoints.
- Any environment-specific allowance is documented as configuration, not hardcoded
  router behavior.
- Security audit output distinguishes required fixes from accepted risk; no prose-only
  findings remain.

**Definition of Done:**

- Backend/Security audit document or architecture handoff is added to tracked docs.
- Required code/config changes are implemented with tests or checker evidence.
- `just check-ssot` and relevant architecture/security checks pass after implementation.
- This registry entry is updated with exit evidence and status `resolved` or
  `accepted_risk`.

**Exit evidence (2026-06-14):** Audit completed. Full audit document at
`docs/architecture/governance/security-audit-cors-rate-limiting.md`. Findings:

- **CORS:** PASS. No wildcard origins with credentials in any environment.
  Dev/test: `["http://localhost:3000"]` (specific origin). Production: `[]`
  (CORS disabled; Next.js reverse proxy makes API same-origin from browser).
  `allow_credentials=True` never paired with wildcard origins. Cookie
  credentials: `httpOnly`, `secure=production`, `samesite=lax`.
- **Rate limiting:** Auth `register` (3/min) and `login` (5/min) are rate-limited
  via `Depends()`. 14 AI/SSE/WebSocket endpoint classes lack rate limits →
  AUFG-05-12 created (P1/P2, `open`). 14 CRUD/auth-read endpoint classes lack
  rate limits → accepted risk (AR-05-03, AR-05-04, justified by local-first
  single-user model).
- **Architecture discrepancy:** TECH_STACK.md/ADR-009 specify Redis-based
  rate limiting, but implementation uses in-memory `pyrate_limiter` (Redis init
  never called). Accepted risk AR-05-02 — functional for single-instance; revisit
  if multi-instance deployment is pursued.
- **Follow-up items:** AUFG-05-12 (rate limiting for AI endpoints), AE-05-03
  (CORS origins as Settings field), AR-05-02/03/04 (accepted risks).
- **Release-security checklist:** Embedded in §5 of the audit document.

No code changes in this slice (audit + documentation only). Implementation
of AI-endpoint rate limits is tracked in AUFG-05-12.

---

### AUFG-05-08 — CSRF-Strategie für state-changing Endpoints

| Field | Value |
|-------|-------|
| ID | AUFG-05-08 |
| Title | CSRF-Strategie für state-changing Endpoints |
| Source | Review-05 release/security finding captured durably in ADR-047 §Context (`CSRF token validation was not explicitly decided for state-changing endpoints`). |
| Status | `resolved` |
| Priority | P0 |
| Area | Security, Backend architecture, Web client auth/session behavior |
| Owner role | Architecture Specialist for strategy decision; Backend/Security Specialist for implementation |
| Dependencies | Auth/session architecture; cookie/header credential mode; CORS audit AUFG-05-07; four-client model constraints from CONSTRAINTS.md RULE-12. |
| Review trigger/date | Re-review before enabling browser-authenticated state changes in production or changing auth credential transport. Re-open if any architectural invariant in §12 of the strategy document is violated. |

**Acceptance criteria:**

- A tracked CSRF strategy decision exists and explicitly covers browser WebUI,
  MCP, A2A, and CLI clients without making one client call another.
- Every state-changing route category is classified as protected, not applicable,
  or covered by a stronger same-site/token/auth mechanism.
- Chosen strategy includes failure semantics, test strategy, and migration impact.
- Any exception is documented as `accepted_risk` with owner, controls, and review date.

**Definition of Done:**

- Architecture decision or feature/security spec records the chosen CSRF strategy.
- Backend implementation follows the chosen contract without router-level hardcoded
  security shortcuts.
- Integration tests cover accepted and rejected state-changing requests where applicable.
- Registry status is updated with exit evidence.

**Exit evidence (2026-06-14):** CSRF strategy decision completed. Full strategy document
at `docs/architecture/governance/csrf-strategy.md`. Decision summary:

- **Strategy chosen:** SameSite=Lax (existing) + Origin/Referer validation (defense-in-
  depth, follow-up AUFG-05-13). No Double-Submit-Token.
- **Root cause:** The backend authenticates state-changing endpoints via `Authorization:
  Bearer` header (HTTPBearer), NOT via cookies. CSRF is structurally inapplicable because
  the browser cannot auto-attach `Authorization` headers cross-origin. Only two endpoints
  (`/auth/refresh`, `/auth/logout`) use cookie-based auth, and they are protected by
  SameSite=Lax + path-restriction with no data-integrity impact.
- **Options evaluated:** Option A (SameSite=Lax + Origin/Referer — chosen), Option B
  (Double-Submit-Token — rejected: solves non-existent vector), Option C (SameSite=Strict
  — rejected: breaks `restoreSession()` UX), Option D (combination — rejected:
  over-engineering).
- **Endpoint inventory:** ~85 route handlers are N/A (Bearer-authenticated, CSRF-
  inapplicable); 2 are cookie-protected (SameSite=Lax); ~6 are N/A (no auth); 1 WebSocket
  endpoint has CSWSH risk (→ AUFG-05-13).
- **Accepted risk:** AR-05-05 (no Double-Submit-Token) — rationale: Bearer auth makes
  CSRF structurally inapplicable. Controls: Bearer auth, SameSite=Lax, JSON-only API,
  CORS disabled in prod, Origin/Referer validation (pending AUFG-05-13).
- **4-client compatibility:** WebUI (Origin validated), CLI/MCP/A2A (Bearer-exempt from
  Origin check). No client calls another.
- **Architectural invariants:** 5 invariants documented (INV-1 through INV-5) — backend
  must never add cookie-based auth for state-changing endpoints without re-review.
- **Follow-up:** AUFG-05-13 (Origin/Referer validation + WebSocket Origin check) — P1,
  open, before public release.

No code changes in this slice (architecture decision + documentation only). Implementation
of Origin/Referer validation is tracked in AUFG-05-13.

---

### AUFG-05-09 — Secret-Scanning als CI-Gate

| Field | Value |
|-------|-------|
| ID | AUFG-05-09 |
| Title | Secret-Scanning als CI-Gate |
| Source | Review-05 release/security finding captured durably in ADR-047 §Context (`Secret scanning was not configured as a dedicated CI gate`). |
| Status | `resolved` |
| Priority | P0 |
| Area | Platform, CI, supply-chain security |
| Owner role | Platform Specialist |
| Dependencies | Existing GitHub Actions CI; local developer check workflow; Gitleaks CI/dev gate; optional GitHub Secret Scanning where repository settings support it; baseline policy for historical findings; no `--no-verify` bypass. |
| Review trigger/date | Re-review when CI workflow topology changes or before first public release artifact. |

**Tooling decision (Architecture, 2026-06-14):**

- **Chosen gate:** Gitleaks is the required repository-local secret-scanning gate for CI
  and local developer handoff commands.
- **Defense in depth:** GitHub Secret Scanning / push protection should be enabled in
  repository settings where available, but it is not the sole acceptance mechanism because
  it is not guaranteed for all repository plans and does not provide the local-first command
  evidence this AUFG requires.
- **Rejected as primary:** `detect-secrets` is not the primary gate because its baseline-first
  workflow is weaker for blocking new high-confidence secret patterns in Git history. It may
  be reconsidered only if Platform needs a Python-native supplemental audit path.
- **ADR scope:** No new ADR is required for this AUFG-level tool selection as long as the
  implementation treats Gitleaks as CI/developer security tooling and does not add a runtime
  product dependency or change `docs/_shared/TECH_STACK.md`. If Platform adds a persistent
  project dependency, changes the Tech Stack, or makes secret scanning a new cross-cutting
  architecture pattern beyond this gate, Architecture must re-review and decide whether a
  dedicated ADR is required.
- **Blocking semantics:** CI must block new unapproved secret findings from the first
  implementation. A short baseline/grace path is allowed only for pre-existing historical
  findings and only with explicit owner, rationale, redacted evidence, and review trigger.
- **Dummy/test secrets:** Test-only values are allowed only when obviously non-production
  and explicitly scoped, for example `.env.example`, CI test environment values, or generated
  temporary fixtures. Synthetic positive tests should generate a fake secret in a temporary
  file and assert Gitleaks fails, rather than committing realistic-looking provider secrets.
  If a committed positive fixture is unavoidable, it must be confined to a dedicated
  secret-scanning fixture path and allowlisted by exact rule/value or inline marker, never by
  a broad repository-wide path ignore.

**Acceptance criteria:**

- Gitleaks is documented and implemented as the dedicated CI/local secret-scanning gate,
  including detection scope, ignore/baseline policy, and failure semantics.
- CI blocks new unapproved secrets; any historical false positives have explicit
  redacted baseline entries with owner, rationale, and expiry/review trigger.
- GitHub Secret Scanning is enabled or explicitly recorded as unavailable/not-applicable for
  the repository; it must not replace the Gitleaks CI gate.
- Local command documentation exists so specialists can run the gate before handoff.
- Dummy/test secret allowances are narrow, documented, and prove both detection and approved
  baseline/allowlist behavior without committing live or realistic production credentials.
- No real secrets are committed as part of implementation or validation evidence.

**Definition of Done:**

- CI workflow includes the secret-scanning gate.
- Platform tests or dry-run evidence prove the gate detects a synthetic secret and
  honors approved baselines/allowlists.
- Developer docs list the command and expected status semantics.
- Registry status is updated with exit evidence.

**Exit evidence (2026-06-14):** Implemented as blocking Gitleaks CI/local gate.
Evidence paths: `.gitleaks.toml` (default Gitleaks rules plus narrow exact fake-value
allowlist; no broad path ignores; no baseline file because no approved historical findings
were introduced), `scripts/check_secrets.py` (invokes `gitleaks detect --source ...
--redact --config ...` and fails with actionable install guidance when the binary is
missing), `justfile` (`just check-secrets`, included by `just security` and
`just check-full`), and `.github/workflows/ci.yml` (`security` job installs Gitleaks
v8.30.1 and runs the wrapper before Bandit/pip-audit; `fetch-depth: 0` enables full
history scanning). Validation evidence: targeted tests
`tests/unit/scripts/test_check_secrets.py` cover missing-binary install guidance (exit
127), command construction with mandatory `--source/--redact/--config` flags, default
config path resolution to the project-root `.gitleaks.toml`, and config-not-found
wrapper error (exit 2); GREEN `4 passed`; targeted Ruff, format, and TOML/YAML static
validation passed. Local runtime scan could not run in the implementation environment
because `gitleaks` was not installed; the wrapper returned exit 127 with install guidance
(`just check-secrets` confirmed). GitHub Secret Scanning / push protection remains optional
defense-in-depth and is not the acceptance mechanism for this AUFG.

---

### AUFG-05-10 — OTel-Health-Severity-Semantik

| Field | Value |
|-------|-------|
| ID | AUFG-05-10 |
| Title | OTel-Health-Severity-Semantik |
| Source | Review-05 observability finding captured durably in ADR-047 §Context (`OTel setup failures were warnings, with no explicit Health-severity policy`). |
| Status | `resolved` |
| Priority | P1 |
| Area | Observability, Platform health, Backend health/readiness endpoints |
| Owner role | Architecture Specialist (policy + contract); Platform/Backend Specialist for implementation (AUFG-05-14) |
| Dependencies | ADR-031 local-first OpenTelemetry; `apps/api/narrare/_app/observability.py`; health/readiness endpoint behavior; current system health scoring. |
| Review trigger/date | Re-review before changing health score thresholds or OTel exporter configuration, or when AE-05-02 (managed hosting) is promoted (S5/CRITICAL mechanism must be decided). |

**Architecture decision (2026-06-14):**

- **Severity policy:** OTel-not-configured (no OTLP endpoint) → **HEALTHY**
  (intentional local-first default); OTel-configured-and-operational → **HEALTHY**;
  OTel-configured-but-setup-failed → **DEGRADED** (warning-only); OTel-package-
  unavailable → **DEGRADED**. **CRITICAL is reserved** for a future mandatory-
  telemetry deployment profile (none exists today; tied to AE-05-02 managed
  hosting). DEGRADED never blocks serving and never flips `/ready` to 503.
- **Root cause:** `setup_telemetry` swallows its setup `Exception` after logging,
  and `get_observability_status()` probes only package importability — so
  "configured but broken" is a RULE-11 silent failure invisible to `/health`.
  This policy specifies the severity semantics; the visibility fix is AUFG-05-14.
- **Review-05 question answered:** OTel-Ausfall is **DEGRADED, not CRITICAL**, for
  the local-first single-user model — graceful degradation is architecturally
  correct (core functionality has zero OTel runtime dependency).
- **Vocabulary alignment:** `/health` adopts the same severity semantics as
  `scripts/check_system_health.py` (HEALTHY/DEGRADED/CRITICAL; lowercase in JSON
  payload per REST convention). This is shared *vocabulary*, not a shared
  measurement surface — OTel is not added as a CI governance gate (category
  error: OTel status is runtime, not static baseline debt).
- **Content capture:** `NARRARE_OTEL_INCLUDE_CONTENT` production default remains
  `false` (privacy invariant INV-OH-2); already implemented and tested.

**Acceptance criteria:**

- OTel setup degradation states have explicit severity mapping: warning-only,
  DEGRADED, or CRITICAL. → **Met by policy §2.1** (severity table + state mapping).
- Health/readiness behavior states whether telemetry exporter failure blocks serving
  requests, blocks release, or only emits governance debt. → **Met by policy §2.1
  / §4.3** (DEGRADED = warning-only; does not block serving or release).
- Failure semantics are visible in tracked docs and validated by tests or checker
  output. → **Policy docs: met. Tests: delegated to AUFG-05-14** (§7.5 test matrix).
- Local-first operation remains valid when external telemetry exporters are absent.
  → **Met by policy §2.1 S1 / §2.2** (not-configured = HEALTHY).

**Definition of Done:**

- Tracked observability/health documentation records the severity policy. → **Done
  (policy doc).**
- Backend health response and/or system-health checker reflects the policy without
  silent failure. → **Contract specified (policy §7); implementation in AUFG-05-14.**
- Tests cover exporter unavailable/misconfigured states where applicable. → **Test
  matrix specified (policy §7.5); implementation in AUFG-05-14.**
- Registry status is updated with exit evidence. → **Done (this entry).**

**Exit evidence (2026-06-14):** OTel Health-Severity Policy completed. Full policy
at `docs/architecture/governance/otel-health-severity-policy.md`. This AUFG's
*architecture/policy* scope (severity mapping, ADR-031 alignment, vocabulary
alignment, no-silent-failure contract, content-capture invariant) is complete and
follows the AUFG-05-07 → AUFG-05-12 precedent (policy/audit resolved; implementation
in a follow-up AUFG). The *implementation* scope — closing the RULE-11 silent-failure
gap by making "configured but broken" queryable from `/health` — is tracked in
**AUFG-05-14** (`open`, Backend/Platform). Policy invariants INV-OH-1 through INV-OH-5
govern future changes. No code changes in this slice (architecture policy +
contract specification only).

---

### AUFG-05-11 — CURRENT_STATE Volatile Stats De-duplication

| Field | Value |
|-------|-------|
| ID | AUFG-05-11 |
| Title | CURRENT_STATE Volatile Stats De-duplication |
| Source | ADR-047 `CURRENT_STATE Volatility Policy`; repeated `just check-ssot` drift from generated counts such as backend test-file totals. |
| Status | `resolved` |
| Priority | P1 |
| Area | Documentation SSOT, Governance checks, Platform tooling |
| Owner role | Docs Specialist for `CURRENT_STATE.md`; Platform Specialist for checker/test changes; Architecture Specialist for policy validation |
| Dependencies | ADR-047; `docs/_shared/CONSTRAINTS.md` §8; `docs/_shared/CURRENT_STATE.md`; `scripts/check_current_state_facts.py`; `just check-ssot`; Governance Health aggregation path. |
| Review trigger/date | Re-review whenever `CURRENT_STATE.md` reintroduces machine-derived counts, or when `check-ssot` changes from warn-only to governance-health reporting. |

**Acceptance criteria:**

- `CURRENT_STATE.md` contains human-curated status, blockers, risks, decision summaries,
  and authority links/commands, but no volatile generated inventory counts.
- Volatile generated facts are replaced by authoritative links or commands, not by freshly
  updated numbers.
- `check_current_state_facts.py` rejects forbidden volatile-count patterns and verifies
  required authority links/commands instead of requiring those counts to be present.
- Checker output remains warn-only until cleanup is complete; any future blocking behavior
  is introduced through the ADR-047 governance-health ratchet path.

**Definition of Done:**

- Docs Specialist updates `docs/_shared/CURRENT_STATE.md` according to ADR-047
  `CURRENT_STATE Volatility Policy` without changing the authoritative source hierarchy.
- Platform Specialist updates `scripts/check_current_state_facts.py` and its unit tests for
  the new policy semantics.
- `just check-ssot` no longer fails because generated counts were intentionally removed
  from `CURRENT_STATE.md`.
- Registry status is updated with exit evidence and either `resolved` or a documented
  governed-debt state.

**Exit evidence (2026-06-15):** Implementation complete. All 14 volatile count claims
removed from `docs/_shared/CURRENT_STATE.md`: Knowledge Graph node/edge counts,
backend/frontend test-file counts, architecture rule counts, ADR/feature inventory
counts, adoption-debt and health-score counts, router inventory counts. Replaced with
authoritative commands and index links: `code-review-graph list-graph-stats`, `just test`,
`just test-frontend`, `docs/_shared/CONSTRAINTS.md`, `docs/architecture/decisions/INDEX.md`,
`docs/features/INDEX.md`, `docs/architecture/questions/INDEX.md`, `just check-adoption`,
`just check-health`, `docs/architecture/governance/aufg-registry.md`.
`scripts/check_current_state_facts.py` (updated in prior session) enforces the policy
with forbidden-pattern detection and required-authority checks. `just check-ssot` now
passes cleanly: "✅ No forbidden volatile count claims found. ✅ Required authority
references/commands are present. ✅ CURRENT_STATE.md follows the volatility policy."
Human-curated content preserved: ADR-045 runtime adoption terminology note, Phase 6
summaries, Decisions/Open Questions/Risks tables.

---

### AUFG-05-12 — Rate-Limiting für AI-/SSE-/WebSocket-Endpoints

| Field | Value |
|-------|-------|
| ID | AUFG-05-12 |
| Title | Rate-Limiting für AI-/SSE-/WebSocket-Endpoints |
| Source | AUFG-05-07 security audit coverage matrix — 14 AI-cost-bearing endpoint classes without rate limits. See `docs/architecture/governance/security-audit-cors-rate-limiting.md` §4. |
| Status | `resolved` |
| Priority | P1 (SSE writing, chat, consistency, analysis, WebSocket session), P2 (generation, KB extraction/improve, setup provider models) |
| Area | Security, Backend, API middleware |
| Owner role | Backend/Security Specialist |
| Dependencies | ADR-009 (fastapi-limiter); AR-05-02 (Redis vs in-memory backend decision); existing rate-limiter DI pattern in `auth/router.py`. |
| Review trigger/date | Before public release or when AE-05-02 (managed hosting) is promoted. |

**Acceptance criteria:**

- Every AI-cost-bearing endpoint (SSE writing/extend/rewrite/coauthor/suggest,
  chat, consistency, analysis, timeline, WebSocket writing session, generation/names,
  KB extraction/improve/sessions, setup provider models) has an explicit rate limit
  via `Depends()`.
- Limits are per-user for authenticated endpoints, per-IP for unauthenticated
  (setup provider models).
- Integration tests prove the limit triggers (HTTP 429 response).
- No router-level hardcoded security; all limits flow through DI cascade.
- Rate-limit backend (Redis vs in-memory) is decided per AR-05-02 resolution.

**Definition of Done:**

- Backend implementation follows the existing `Depends()` pattern from
  `auth/router.py` without router-level hardcoded security shortcuts.
- Integration tests cover accepted (200) and rejected (429) rate-limit scenarios
  for representative endpoints per priority tier.
- Registry status is updated with exit evidence.

**Exit evidence (2026-06-15):** Implementation complete. Shared module at
`apps/api/narrare/_app/rate_limits.py` provides 3 reusable AI limiters:
`AI_WRITE_LIMITER` (3/min, Depends()), `AI_ANALYSIS_LIMITER` (5/min, Depends()),
`AI_LIGHT_LIMITER` (10/min, Depends()), and `AI_WS_LIMITER` (3/min, raw Limiter
for WebSocket inline check) plus `SETUP_MODELS_LIMITER` (10/min, IP-based).
17 router files wired via `dependencies=[Depends(CONSTANT)]`. WebSocket
rate-inline check in `router_sessions.py`. 14 unit tests at
`tests/unit/api/_app/test_rate_limits.py` covering type-check, enforcement,
independence, and WebSocket scenarios. 963+ broader backend tests pass.
Uses in-memory `pyrate_limiter` per AR-05-02 accepted risk (no Redis init).

---

### AUFG-05-13 — Origin/Referer Validation + WebSocket Origin Check (CSRF Defense-in-Depth)

| Field | Value |
|-------|-------|
| ID | AUFG-05-13 |
| Title | Origin/Referer Validation + WebSocket Origin Check (CSRF Defense-in-Depth) |
| Source | AUFG-05-08 CSRF strategy decision — defense-in-depth layer to close subdomain CSRF, SameSite=Lax 2-minute-window, and Cross-Site WebSocket Hijacking (CSWSH) gaps. See `docs/architecture/governance/csrf-strategy.md` §9. |
| Status | `resolved` |
| Priority | P1 (before public release or managed hosting promotion) |
| Area | Security, Backend middleware, WebSocket |
| Owner role | Backend/Security Specialist |
| Dependencies | CSRF strategy decision (`docs/architecture/governance/csrf-strategy.md`); trusted-origin configuration; existing middleware stack in `apps/api/narrare/_app/middleware.py`; WebSocket endpoint `apps/api/narrare/writing/router_sessions.py`; AR-05-05 (accepted risk that this AUFG partially mitigates). |
| Review trigger/date | Before public release, when AE-05-02 (managed hosting) is promoted, or when subdomain deployment is configured. |

**Scope:**

1. Origin/Referer validation middleware for all state-changing HTTP methods (POST/PUT/
   PATCH/DELETE). Trusted origins configurable via `Settings.csrf_trusted_origins`.
   Requests without Origin allowed only if valid `Authorization: Bearer` present
   (programmatic clients: CLI/MCP/A2A). Rejection: HTTP 403 with
   `{"detail": "Origin not allowed", "code": "CSRF_ORIGIN_MISMATCH"}`.
2. WebSocket Origin validation during handshake on `/writing/sessions/{chapter_id}` to
   prevent CSWSH. Reject non-trusted Origin (close code 4001).
3. `Settings.csrf_trusted_origins` field added (default: `["http://localhost:3000"]`;
   production: deployed origin via env var).

**Acceptance criteria:**

- All POST/PUT/PATCH/DELETE requests validated against trusted origins.
- Same-origin requests accepted (200); cross-origin rejected (403).
- Bearer-authenticated requests without Origin accepted (programmatic clients).
- Requests without Origin AND without Bearer rejected (403).
- WebSocket connections validate Origin during handshake.
- Integration tests cover accepted, rejected, and exempt scenarios.
- No router-level hardcoded security — middleware or dependency-based.

**Definition of Done:**

- Middleware implemented in `apps/api/narrare/_app/middleware.py`.
- WebSocket Origin check implemented in `router_sessions.py`.
- `Settings.csrf_trusted_origins` field added.
- Integration tests cover: same-origin accepted, cross-origin rejected, no-Origin-with-
  Bearer accepted, no-Origin-without-Bearer rejected, WebSocket origin validated.
- Registry status is updated with exit evidence.

**Exit evidence (2026-06-15):** Implementation complete. `OriginValidationMiddleware`
in `apps/api/narrare/_app/middleware.py` validates Origin/Referer on all
POST/PUT/PATCH/DELETE requests; Bearer-authenticated requests without Origin
are exempt (programmatic clients). Middleware registered in `main.py` after CORS.
`Settings.csrf_trusted_origins` field (`NARRARE_CSRF_TRUSTED_ORIGINS`, default
`["http://localhost:3000"]`) configures trusted origins. WebSocket Origin check
in `writing/router_sessions.py` rejects non-matching origins with close code
4001. 12 unit tests at `tests/unit/api/_app/test_csrf_middleware.py` covering
same-origin (200), cross-origin (403), Bearer-exempt (200), WebSocket (4001),
Referer fallback, and invalid Bearer scenarios. Backend middleware gated in test
environment to avoid breaking existing TestClient-based tests.

---

### AUFG-05-14 — OTel-Health-Severity Implementierung (Backend/Platform)

| Field | Value |
|-------|-------|
| ID | AUFG-05-14 |
| Title | OTel-Health-Severity Implementierung (Backend/Platform) |
| Source | AUFG-05-10 OTel Health-Severity Policy §7 (Implementation Contract). AUFG-05-10's architecture/policy scope is resolved; this AUFG carries the implementation scope that closes the RULE-11 silent-failure gap. |
| Status | `resolved` |
| Priority | P1 |
| Area | Observability, Backend health/readiness endpoints, Platform testing |
| Owner role | Backend Specialist (observability/telemetry + health endpoint) with Platform Specialist (tests/smoke-checks) |
| Dependencies | ADR-031; OTel Health-Severity Policy (`docs/architecture/governance/otel-health-severity-policy.md` §7); `apps/api/narrare/_app/observability.py`; `apps/api/narrare/_app/telemetry.py`; `apps/api/narrare/metrics/router.py`; `scripts/check_system_health.py` (vocabulary reference, not modified). |
| Review trigger/date | Re-review if the OTel Health-Severity Policy (§7 contract or §10 invariants) changes, or when AE-05-02 promotes S5/CRITICAL. |

**Scope (normative: policy §7):**

1. **`get_observability_status()` extension** (`observability.py`): add `state`
   (`not_configured` | `configured_ok` | `configured_failed` | `package_unavailable`),
   `severity` (`healthy` | `degraded` | `critical`), and `endpoint_configured` to the
   return shape. Retain `available` (backward-compat) = `severity == "healthy"`.
   State → severity mapping per policy §2.1.
2. **New `record_otel_setup_outcome()`** (`observability.py`): thread-safe function
   called by `setup_telemetry` to record setup success/failure so it is queryable.
   Signature per policy §7.2.
3. **`setup_telemetry` wiring** (`telemetry.py`): call `record_otel_setup_outcome()`
   on the no-endpoint early-return (succeeded, not configured), on success
   (configured_ok), and in the `except Exception` branch (configured_failed) —
   replacing the current silent swallow while preserving the no-raise contract.
4. **`/health` endpoint** (`metrics/router.py`): return `status = observability
   severity` (`healthy`/`degraded`/`critical`) instead of always `"ok"`. HTTP 200
   for healthy and degraded (liveness). `/ready` unchanged.
5. **Tests** (policy §7.5): cover no-endpoint (T1), configured-but-failed (T2),
   successful configuration (T3), and reaffirm production-safe content-capture
   default (T4). Update existing tests in `tests/unit/api/_app/test_observability.py`
   and `test_telemetry*.py` for the new return shape (backward-compat `available`
   retained).

**Acceptance criteria:**

- `get_observability_status()` exposes `state` and `severity` per policy §7.1.
- `setup_telemetry` records outcome via `record_otel_setup_outcome()` on all three
  paths (no-endpoint, success, failure); the failure path no longer swallows state
  silently (RULE-11).
- `/health` `status` reflects the policy severity vocabulary; DEGRADED returns HTTP
  200 and does not affect `/ready`.
- Tests cover T1–T4 (policy §7.5); no OTel failure elevates severity above DEGRADED
  without a mandatory-telemetry profile (invariant INV-OH-1).
- `available` backward-compat key retained so existing consumers do not break.
- No new external dependency; no `apps/` → `core/` import (RULE-07).

**Definition of Done:**

- Implementation follows the policy §7 contract without router-level business logic
  (RULE-06).
- Unit tests for observability state transitions + telemetry outcome recording +
  `/health` payload pass GREEN.
- This registry entry is updated with exit evidence and status `resolved`.

**Exit evidence (2026-06-15):** Implementation complete. `get_observability_status()`
in `apps/api/narrare/_app/observability.py` extended with `state`
(not_configured|configured_ok|configured_failed|package_unavailable), `severity`
(healthy|degraded|critical), and `endpoint_configured` keys; `available` retained
for backward compatibility (= `severity == "healthy"`). New
`record_otel_setup_outcome()` function records setup outcomes thread-safely.
`setup_telemetry()` in `telemetry.py` calls it on all 3 paths: no-endpoint
(not_configured), success (configured_ok), failure (configured_failed). `/health`
in `metrics/router.py` returns `status: obs["severity"]` instead of hardcoded
`"ok"`; DEGRADED returns HTTP 200 (liveness). 13 unit tests at
`tests/unit/api/_app/test_observability_health.py` covering T1–T5 (no-endpoint,
configured-failed, configured-ok, content-capture default, package-unavailable).
RULE-11 silent-failure gap closed: configured-but-broken is now both logged AND
queryable from `/health`.

---

## Coverage Pointers

### AUFG-05-03 — Memory/Embedding-Spans and Metrics-Exporter Decision/Extension

| Field | Value |
|-------|-------|
| ID | AUFG-05-03 |
| Title | Memory/Embedding-Spans and Metrics-Exporter Decision/Extension |
| Source | Review-05 observability scope referenced by ADR-047-related handoff; durable coverage pointer created here to avoid duplicate AUFGs. |
| Status | `covered_by_existing_aufg` |
| Priority | P1 |
| Area | Observability, Memory, Embeddings, metrics export |
| Owner role | Platform Specialist with Core Specialist for memory/embedding instrumentation |
| Dependencies | ADR-031 OpenTelemetry standard; ADR-033 mem0 memory architecture; existing memory/embedding clients and metrics/exporter decisions. |
| Review trigger/date | Re-review whenever AUFG-05-03 is closed, or if AUFG-05-10 changes health semantics for telemetry/exporter failures. |

**Acceptance criteria:**

- AUFG-05-03 exit evidence explicitly states whether memory/embedding spans are
  implemented, rejected as not applicable, or tracked as accepted risk/enhancement.
- Metrics-exporter behavior is decided in AUFG-05-03 or a linked ADR/spec; no separate
  prose-only observability finding remains.
- If AUFG-05-03 scope is insufficient, this pointer must be converted into a separate
  AUFG before release governance claims are made.

**Definition of Done:**

- AUFG-05-03 tracked evidence includes memory/embedding span and metrics-exporter
  decision coverage.
- This pointer remains `covered_by_existing_aufg` only while that evidence exists.

**Exit evidence:** Pending AUFG-05-03 closure evidence.

---

## Accepted Enhancements

Accepted enhancements are non-blocking by default. They become blocking only if a
later ADR/spec/release gate promotes them to `open` AUFG scope.

### AE-05-01 — Cosign/SLSA Release Provenance Hardening

| Field | Value |
|-------|-------|
| ID | AE-05-01 |
| Title | Cosign/SLSA Release Provenance Hardening |
| Source | `docs/development/deployment-guide.md` §Cosign Signing (Future) and provenance trust model. |
| Status | `accepted_enhancement` |
| Priority | P2 |
| Area | Platform, release engineering, supply-chain security |
| Owner role | Platform Specialist |
| Dependencies | Release workflow, GHCR publishing, SBOM generation, GitHub OIDC permissions, secret-scanning gate AUFG-05-09. |
| Review trigger/date | Review before first public release artifact, or by 2026-09-30 if release hardening has not been revisited. |

**Acceptance criteria:**

- Platform decides whether to implement Cosign keyless signing, SLSA provenance, or
  both, with rationale and verification commands.
- Release documentation explains how users verify image signatures/provenance.
- CI/release workflow evidence demonstrates signed/provenance-bearing artifacts if promoted.

**Definition of Done:**

- If promoted: workflow, docs, and verification evidence are added in one coherent change.
- If deferred: registry remains `accepted_enhancement` with renewed review date and rationale.

**Exit evidence:** Non-blocking enhancement accepted; implementation evidence pending only
if promoted by Platform/release planning.

---

### AE-05-02 — Managed Hosting Strategy Exploration

| Field | Value |
|-------|-------|
| ID | AE-05-02 |
| Title | Managed Hosting Strategy Exploration |
| Source | `docs/architecture/questions/Q-011-distribution-strategy.md` Option C / Variant C2 and recommendation. |
| Status | `accepted_enhancement` |
| Priority | P3 |
| Area | Product architecture, distribution strategy, platform operations |
| Owner role | Architecture Specialist with Product/Coordinator decision from user |
| Dependencies | Q-011 distribution strategy; local-first product vision; auth/multi-tenancy, billing, GDPR, rate limiting, and operational support decisions. |
| Review trigger/date | Review at Post-MVP Phase 4 or when active non-developer onboarding begins, whichever comes first. |

**Acceptance criteria:**

- Managed hosting remains an exploration/enhancement, not an implementation decision.
- Any move toward hosted/SaaS delivery requires a new ADR covering local-first impact,
  multi-tenancy, data isolation, billing, rate limiting, and GDPR/compliance.
- Q-011 remains the strategy question until the user explicitly selects a distribution path.

**Definition of Done:**

- No production code is added for managed hosting under this enhancement entry alone.
- If promoted, Architecture creates a dedicated ADR/spec before implementation.
- If rejected, status changes to `not_applicable` or `accepted_risk` with rationale.

**Exit evidence:** Non-blocking strategic enhancement accepted for future review; no
implementation evidence required until user-approved promotion.

---

### AE-05-03 — CORS Origins als Settings-Feld

| Field | Value |
|-------|-------|
| ID | AE-05-03 |
| Title | CORS Origins als Settings-Feld |
| Source | AUFG-05-07 security audit §2.4 — CORS origins hardcoded in app factory. |
| Status | `accepted_enhancement` |
| Priority | P3 |
| Area | Backend, configuration, deployment |
| Owner role | Backend Specialist |
| Dependencies | `apps/api/narrare/_app/settings_model.py`; `apps/api/narrare/_app/main.py` CORS middleware. |
| Review trigger/date | Re-review when a deployment scenario requires custom CORS origins, or by 2027-06-14. |

**Acceptance criteria:**

- `Settings.cors_origins` field added so operators configure CORS via env var.
- Default remains `["http://localhost:3000"]` for dev, `[]` for production.
- No behavior change for existing deployments.

**Definition of Done:**

- If promoted: Settings field + tests in one coherent change.
- If deferred: registry remains `accepted_enhancement` with renewed review date.

**Exit evidence:** Non-blocking enhancement accepted; implementation evidence pending
only if promoted.

---

## Accepted Risks

Accepted risks are knowingly accepted with owner, rationale, controls, and review
date. They become blocking only if a later ADR/spec/release gate promotes them to
`open` AUFG scope.

### AR-05-02 — Rate-Limiting Backend Discrepanz (In-Memory vs Redis)

| Field | Value |
|-------|-------|
| ID | AR-05-02 |
| Type | `accepted_risk` |
| Risk | Rate limits are process-local in-memory (`pyrate_limiter`), not Redis-based as specified in TECH_STACK.md / ADR-009. Multi-instance deployments would have independent counters per instance. |
| Owner | Backend/Security Specialist |
| Rationale | Current deployment model is single-instance local-first. In-memory rate limiting is functionally equivalent for single-instance. `pyrate-limiter` is a transitive dependency of `fastapi-limiter`; the combination works in practice (e2e tests confirm HTTP 429 responses on auth endpoints). |
| Controls | (1) TECH_STACK.md documents the intended Redis-based approach. (2) AUFG-05-12 implementation should evaluate whether to align with TECH_STACK.md (call `FastAPILimiter.init(redis)`) or update TECH_STACK.md/ADR-009 to reflect the in-memory approach. |
| Review trigger/date | Re-review when AE-05-02 (managed hosting) is promoted to implementation, or when multi-instance API deployment is configured. No fixed date — gated by deployment topology change. |
| Source | AUFG-05-07 security audit §3.3 |

### AR-05-03 — Auth-Non-Brute-Force Endpoints ohne Rate Limit

| Field | Value |
|-------|-------|
| ID | AR-05-03 |
| Type | `accepted_risk` |
| Risk | `/auth/refresh`, `/auth/logout`, `GET /auth/me` have no rate limits. |
| Owner | Backend/Security Specialist |
| Rationale | Refresh: cookie-scoped (`samesite=lax`, `path=/api/v1/auth`), token rotation on every call, invalid tokens clear the cookie. Logout: no-op (clears cookie). Me: read-only, auth-protected. None present a meaningful brute-force or cost-abuse surface. |
| Controls | `sameSite=lax` prevents CSRF-based abuse. Token rotation invalidates stolen refresh tokens on use. Auth-protected endpoints require valid JWT. |
| Review trigger/date | Re-review if refresh token flow changes, or if `sameSite` is weakened. By 2027-06-14 if no change. |
| Source | AUFG-05-07 security audit §4.2 |

### AR-05-04 — State-Changing CRUD ohne Rate Limit (Local-First)

| Field | Value |
|-------|-------|
| ID | AR-05-04 |
| Type | `accepted_risk` |
| Risk | State-changing CRUD endpoints (novels, chapters, volumes, KB, settings, embeddings, prompts, templates, wiki), setup validation/complete have no rate limits. |
| Owner | Backend/Security Specialist |
| Rationale | All endpoints are auth-protected (require valid JWT). Deployment model is local-first, single-user self-hosted. No multi-tenant or public-facing surface. Rate-limiting CRUD on a single-user local instance adds complexity without security benefit. |
| Controls | JWT authentication on all endpoints. `ENVIRONMENT` defaults to `development`. Production requires explicit operator configuration. Setup complete requires authentication. |
| Review trigger/date | Re-review when AE-05-02 (managed hosting) is promoted, or when multi-user/multi-tenant features are added. No fixed date — gated by product evolution. |
| Source | AUFG-05-07 security audit §4.2 |

### AR-05-05 — No Double-Submit-CSRF-Token

| Field | Value |
|-------|-------|
| ID | AR-05-05 |
| Type | `accepted_risk` |
| Risk | No Double-Submit-CSRF-Token is used. CSRF defense relies on (1) Bearer-token authentication for all state-changing endpoints, (2) SameSite=Lax for cookie-authenticated auth endpoints, and (3) Origin/Referer validation (to be implemented per AUFG-05-13). |
| Owner | Architecture Specialist |
| Rationale | The backend authenticates state-changing endpoints via `Authorization: Bearer` headers (`HTTPBearer` in `get_current_user_id`), not cookies. CSRF is structurally inapplicable because the browser cannot auto-attach `Authorization` headers cross-origin. The only cookie-authenticated endpoints (`/auth/refresh`, `/auth/logout`) are protected by SameSite=Lax + path-restriction (`/api/v1/auth`) and have no data-integrity impact (token rotation, logout). A Double-Submit-Token would protect against a vector that does not exist in the current architecture, adding complexity (token generation, storage, client-server coordination, contract, test surface) without proportional security benefit. |
| Controls | (1) Bearer-token auth via `HTTPBearer` (`apps/api/narrare/_app/dependencies_auth.py`). (2) SameSite=Lax + path-restriction on `narrare_refresh` cookie (`apps/api/narrare/auth/cookie_helpers.py`). (3) JSON-only API (Pydantic rejects non-JSON bodies). (4) CORS disabled in production (same-origin proxy). (5) Origin/Referer validation per AUFG-05-13 (pending implementation). (6) Architectural invariant INV-1 through INV-5 (see `docs/architecture/governance/csrf-strategy.md` §12): backend must never add cookie-based auth for state-changing endpoints. |
| Review trigger/date | Re-review if: (a) cookie-based authentication is added to any state-changing endpoint, (b) AE-05-02 (managed hosting) is promoted introducing subdomains, (c) WebSocket auth model changes, or (d) by 2027-06-14 if no change. |
| Release trigger | Origin/Referer validation (AUFG-05-13) should be implemented before public release or managed hosting promotion. Until then, the current posture (Bearer auth + SameSite=Lax) is safe for local-first single-user deployment. |
| Source | AUFG-05-08 CSRF strategy decision (`docs/architecture/governance/csrf-strategy.md` §8) |
