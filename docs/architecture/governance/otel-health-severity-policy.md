# OTel Health-Severity Policy

> **Status:** Accepted — Architecture decision (governance policy). Implementation complete (AUFG-05-14 resolved)
> **Date:** 2026-06-14
> **Owner:** Architecture Specialist
> **Established by:** AUFG-05-10 (Review-05 observability finding)
> **Authority:** ADR-031 (Local-First OpenTelemetry Observability), `docs/_shared/CONSTRAINTS.md`
> **Implementation tracked in:** AUFG-05-14 (Backend/Platform)

---

## 0. TL;DR

OpenTelemetry is **local-first and optional** (ADR-031). Its absence is the
intended default; its breakage is **degradation, not a critical outage**.

| OTel condition | Health severity | Blocks serving? | Blocks release? |
|----------------|-----------------|-----------------|-----------------|
| Not configured (no OTLP endpoint) | **HEALTHY** | No | No |
| Configured + setup succeeded | **HEALTHY** | No | No |
| Configured + setup failed | **DEGRADED** | No | No |
| Package unavailable (import failed) | **DEGRADED** | No | No |
| OTel declared mandatory by a deployment profile (none exists today) | **CRITICAL** on failure | Profile-defined | Profile-defined |

DEGRADED is warning-only. CRITICAL is reserved for a future **mandatory-telemetry
deployment profile** that does not exist in the current local-first single-user
model (see AE-05-02 managed hosting).

---

## 1. Context & Root Cause

### 1.1 The Review-05 finding

> *"OTel setup failures were warnings, with no explicit Health-severity policy."*

(ADR-047 §Context; AUFG-05-10 source.)

### 1.2 Root-cause chain (5× Why)

1. **Symptom:** When an operator configures `OTEL_EXPORTER_OTLP_ENDPOINT` but the
   exporter setup fails, `/health` still reports `status: "ok"` and
   `get_observability_status()` reports `available: true`. The failure is invisible
   to health checks.
2. **Why?** `apps/api/narrare/_app/telemetry.py::setup_telemetry` catches the
   setup `Exception`, logs `otel_setup_failed`, and **swallows it** — it records
   no queryable state.
3. **Why?** `get_observability_status()` (in `_app/observability.py`) probes only
   whether the `opentelemetry` package is *importable*, not whether the OTLP
   exporter was *successfully configured*. Package importability ≠ exporter
   readiness.
4. **Why?** Two distinct OTel conditions were conflated under one boolean
   (`available`), and there was no explicit severity policy separating
   "intentionally off" from "configured but broken".
5. **Why?** ADR-031 commits to "local-first, optional, graceful degradation" and
   RULE-11 ("instrumentation failures must degrade visibly ... never silently"),
   but the **severity semantics of that degradation** were never specified. This
   policy closes that gap.

### 1.3 Two OTel conditions that must not be conflated

| Concept | Detection | Current handling | Correct severity |
|---------|-----------|------------------|------------------|
| **OTel off** — no endpoint configured, the local-first default | `OTEL_EXPORTER_OTLP_ENDPOINT` unset → `setup_telemetry` early-returns | Logged `otel_disabled_no_endpoint` (info). Correct. | **HEALTHY** |
| **OTel broken** — endpoint configured but exporter init raised | `setup_telemetry` `except Exception` branch | Logged `otel_setup_failed` (warning), then **swallowed with no queryable state**. **RULE-11 silent-failure risk.** | **DEGRADED** (must be surfaced) |

The gap to close is the "OTel broken" visibility — *not* a change to the local-first
default. This is an implementation contract (AUFG-05-14), not a policy ambiguity.

---

## 2. Decision — Severity Policy

### 2.1 Severity mapping

The Observability subsystem exposes a single `severity` derived from its internal
`state`. Severity uses the **same vocabulary and blocking model** as the CI
governance health aggregator (`scripts/check_system_health.py`):

- **HEALTHY** — nominal. No action required.
- **DEGRADED** — warning-only. Does **not** block serving requests, does **not**
  fail CI, does **not** change `/ready` status. Surfaced in `/health` payload and
  structured logs so operators can detect and fix it.
- **CRITICAL** — blocking, per existing governance semantics. Reserved for
  mandatory subsystems whose failure invalidates the deployment's stated contract.

| # | Scenario | `OTEL_EXPORTER_OTLP_ENDPOINT` | OTel `state` | `severity` | HTTP `/health` body `status` | `/health` status code | `/ready` impact |
|---|----------|-------------------------------|--------------|------------|------------------------------|-----------------------|-----------------|
| S1 | Intentionally off (local-first default) | unset | `not_configured` | **HEALTHY** | `healthy` | 200 | none |
| S2 | Configured and operational | set | `configured_ok` | **HEALTHY** | `healthy` | 200 | none |
| S3 | Configured but setup failed | set | `configured_failed` | **DEGRADED** | `degraded` | 200 | none |
| S4 | OTel package not importable (unexpected) | any | `package_unavailable` | **DEGRADED** | `degraded` | 200 | none |
| S5 | Mandatory-OTel deployment profile + failure | set + mandatory profile | `configured_failed` (or `package_unavailable`) | **CRITICAL** | `critical` | 200 (liveness) / profile-defined | profile-defined |

**S5 does not exist today.** No deployment profile currently declares OTel
mandatory. S5 is documented so that *if and when* such a profile is introduced
(via AE-05-02 managed-hosting promotion or a dedicated ADR), the severity rule is
already decided and does not need re-derivation.

### 2.2 Why DEGRADED (not CRITICAL) for the local-first model

ADR-031 establishes OpenTelemetry as **optional infrastructure** for local-first
Narrare. Core product functionality — writing, KB, agents, sessions — has **zero
runtime dependency** on OTel. A broken trace exporter means lost observability
data, not lost product capability. Mapping that to CRITICAL would:

- falsely signal that serving requests is unsafe (it is not),
- couple the product's availability posture to an optional backend, violating
  ADR-031's local-first guarantee,
- and fail CI/releases for a non-functional regression.

**Graceful degradation (DEGRADED) is the architecturally correct severity.** This
directly answers the Review-05 open question: *OTel-Ausfall is DEGRADED, not
CRITICAL, for the local-first model.*

### 2.3 Why CRITICAL is reserved (and what would trigger it)

CRITICAL is reserved for the case where a deployment profile **explicitly declares
OTel mandatory** as part of its operational contract (e.g. a managed-hosting SLO
where observability is a paid guarantee, or a regulated deployment where trace
retention is audited). This:

- keeps the local-first default untouched,
- makes the criticality decision **configuration-driven, not hardcoded**,
- and defers the blocking mechanism to the deployment profile that introduces the
  requirement (per AE-05-02 — not yet promoted).

**Trigger to revisit:** If AE-05-02 (managed hosting) is promoted to
implementation, Architecture must re-review this policy and decide the S5
blocking mechanism (e.g. whether CRITICAL OTel flips `/ready` to 503 or only
emits a release-gate signal).

---

## 3. Answer to the Review-05 Question

> *"Soll OTel-Ausfall CRITICAL sein oder ist graceful degradation korrekt?"*

**Graceful degradation (DEGRADED) is correct for the current local-first
single-user deployment model.** Rationale:

1. ADR-031 positions OTel as optional, vendor-neutral, local-backend-friendly
   infrastructure — not as a product dependency.
2. Core functionality is unaffected by telemetry loss; only observability data is.
3. The severity vocabulary already supports the right granularity: HEALTHY →
   DEGRADED → CRITICAL. Using CRITICAL here would erase the distinction between
   "product down" and "telemetry down".
4. CRITICAL remains available for a future mandatory-telemetry profile (§2.3) so
   the policy scales without re-derivation.

---

## 4. Vocabulary Alignment (Acceptance Criterion #3)

### 4.1 Two health surfaces, one semantic model

The codebase has two distinct health surfaces. This policy does **not** merge them
into one tool (that would be a category error — they measure different things),
but it requires them to share the **same severity vocabulary and blocking model**:

| Surface | Purpose | What it measures | Severity vocabulary |
|---------|---------|------------------|---------------------|
| `GET /health` (runtime, `metrics/router.py`) | Liveness + subsystem degradation for operators | Runtime OTel state (and future subsystems) | `healthy` / `degraded` / `critical` |
| `scripts/check_system_health.py` (CI governance) | Architecture/governance debt score over weighted gates | Static baseline debt, test pass rate | `HEALTHY` / `DEGRADED` / `CRITICAL` |

**Shared blocking model (already established by `check_system_health.py`):**
- HEALTHY / DEGRADED → exit 0 (do not block).
- CRITICAL → exit 1 (blocks CI / release).

The runtime `/health` endpoint adopts the **same semantics**: DEGRADED never
blocks serving (HTTP 200, warning-only); CRITICAL is the only blocking state, and
OTel cannot produce CRITICAL without a mandatory-telemetry deployment profile.

### 4.2 Casing convention

- CI governance output uses UPPERCASE (`HEALTHY`/`DEGRADED`/`CRITICAL`) —
  unchanged, it is operator console output.
- Runtime `/health` JSON payload uses lowercase (`healthy`/`degraded`/`critical`)
  per REST/JSON convention.

These map 1:1. The **semantics are identical**; casing is a presentation detail
of each surface. This is explicitly documented to prevent a future
misunderstanding where the two are treated as different vocabularies.

### 4.3 What this does NOT mean

- It does **not** add an "otel" gate to `check_system_health.py`. OTel exporter
  status is a *runtime* property that cannot be measured from static baseline
  data. The CI governance aggregator measures architecture debt; OTel health is
  measured at runtime via `get_observability_status()`.
- It does **not** make `/health` return non-200 for DEGRADED. `/health` is a
  liveness signal; a degraded-observability process is still alive and serving.

---

## 5. Content-Capture Default (`NARRARE_OTEL_INCLUDE_CONTENT`)

`NARRARE_OTEL_INCLUDE_CONTENT` controls whether prompt/completion content is
captured in AI spans (ADR-031 Phase 1). This is a **privacy** control, not a
health-severity control.

| Environment | Default | Rationale |
|-------------|---------|-----------|
| `production` | `false` | Privacy-safe: no prompt/completion content leaves the process in spans. |
| non-production (`development`, `test`) | `true` | Developer ergonomics: local debugging benefits from content in spans. |

**Policy:**

- The production default **must remain `false`**. This is a privacy invariant.
- An operator **may** explicitly set `NARRARE_OTEL_INCLUDE_CONTENT=true` in
  production when they control their own collector and accept the privacy
  trade-off. This is an explicit operator decision, not a silent default.
- A misconfigured content-capture (content captured unexpectedly in production)
  is a **configuration audit finding**, not a health-CRITICAL event. It does not
  elevate OTel severity. (The default is already production-safe; the only way to
  capture content in production is an explicit opt-in.)

The production-safe default is **already implemented and tested**
(`telemetry._include_ai_content()` +
`test_include_ai_content_defaults_to_false_in_production`). AUFG-05-14 adds a
smoke-check assertion that the default is production-safe as part of the OTel
health test matrix.

---

## 6. No-Silent-Failure Contract (Acceptance Criterion #5)

ADR-031 RULE-11 row: *"Instrumentation failures must degrade visibly through
logs/health, never silently."* This policy makes that commitment concrete for the
"configured but broken" path.

**Rule:** Every OTel setup failure that is currently swallowed (S3) MUST be:
1. logged once, privacy-safe (no secrets, no prompt content) via structlog, and
2. recorded in queryable state surfaced by `get_observability_status()`, and
3. visible in the `/health` payload as `severity: "degraded"` with a
   human-readable `failure_reason`.

A failure that is logged but not queryable from `/health` is still a silent
failure for an operator who only checks the health endpoint. Both channels are
required.

---

## 7. Implementation Contract (for AUFG-05-14 — ✅ IMPLEMENTED)

This section specifies the contract that Backend/Platform implements in AUFG-05-14.
It is normative for that AUFG. **No code is changed by this policy document.**

### 7.1 Enhanced `get_observability_status()` (observability.py)

Current return shape (package-importability only):

```python
{"available": bool, "failure_reason": str, "warning_emitted": bool}
```

**Required** return shape (adds `state`, `severity`, `endpoint_configured`):

```python
{
    "available": bool,            # backward-compat: True iff state in {not_configured, configured_ok}
    "state": str,                 # one of: not_configured | configured_ok | configured_failed | package_unavailable
    "severity": str,              # healthy | degraded | critical
    "endpoint_configured": bool,  # True iff OTEL_EXPORTER_OTLP_ENDPOINT was set
    "failure_reason": str,        # non-empty when state is a failure state
    "warning_emitted": bool,      # one-shot warning guard (existing semantics preserved)
}
```

State → severity mapping is the single source of truth defined in §2.1.
`available` is retained for backward compatibility and equals
`severity == "healthy"`.

### 7.2 New: setup-failure recording (telemetry.py → observability.py)

`setup_telemetry` currently swallows its `except Exception`. It MUST instead
record the failure so `get_observability_status()` can surface it. Contract:

```python
# observability.py — new function (Protocol-level requirement)
def record_otel_setup_outcome(
    *,
    endpoint_configured: bool,
    succeeded: bool,
    failure_reason: str = "",
) -> None:
    """Record the OTLP exporter setup outcome.

    Called by setup_telemetry exactly once after attempting configuration.
    Transitions internal state to configured_ok / configured_failed /
    not_configured and updates severity accordingly. Thread-safe.
    """
```

`setup_telemetry` (telemetry.py) call sites:

```python
def setup_telemetry(app: FastAPI) -> None:
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        logger.info("otel_disabled_no_endpoint")
        record_otel_setup_outcome(endpoint_configured=False, succeeded=True)
        return
    try:
        ...  # existing configuration
        record_otel_setup_outcome(endpoint_configured=True, succeeded=True)
        logger.info("otel_configured", ...)
    except Exception:
        logger.warning("otel_setup_failed", exc_info=True)
        record_otel_setup_outcome(
            endpoint_configured=True, succeeded=False,
            failure_reason="OTLP exporter setup raised",
        )
```

**RULE-11 compliance:** The failure is now both logged AND queryable. No silent
swallow.

### 7.3 `/health` response contract (metrics/router.py)

```python
@router.get("/health")
async def health() -> dict[str, Any]:
    obs = get_observability_status()
    return {
        "status": obs["severity"],   # healthy | degraded | critical (was: always "ok")
        "observability": obs,
    }
```

- HTTP status code remains **200** for `healthy` and `degraded` (liveness).
- `critical` HTTP semantics are profile-defined (§2.3); no profile exists, so no
  code path produces `critical` today.
- `/ready` is **unchanged**: OTel degradation does not affect readiness to serve.

### 7.4 Dependency direction (RULE-06 / RULE-07)

- `telemetry.py` → `observability.py` (records outcome). Same `_app` layer.
- `metrics/router.py` → `observability.py` (reads status). Router delegates; no
  business logic in the router.
- No new cross-layer dependency. No `apps/` → `core/` OTel-health import.

### 7.5 Test matrix (Acceptance Criterion #4)

AUFG-05-14 must cover at minimum:

| Test | Scenario | Asserts |
|------|----------|---------|
| T1 | No `OTEL_EXPORTER_OTLP_ENDPOINT` | `state == not_configured`, `severity == "healthy"`, `/health` `status == "healthy"` |
| T2 | Endpoint set, exporter import fails (invalid/unreachable) | `state == configured_failed`, `severity == "degraded"`, `/health` `status == "degraded"`, `failure_reason` non-empty, setup did not raise |
| T3 | Endpoint set, no-op successful configuration | `state == configured_ok`, `severity == "healthy"` |
| T4 | `ENVIRONMENT=production`, no `NARRARE_OTEL_INCLUDE_CONTENT` | `_include_ai_content() is False` (production-safe default) — *already tested; reaffirm* |
| T5 | (Optional) Package unavailable simulation | `state == package_unavailable`, `severity == "degraded"` |

T1–T3 are the new coverage. T4 already exists
(`test_include_ai_content_defaults_to_false_in_production`); AUFG-05-14
reaffirms it as part of the OTel-health test matrix. T5 is best-effort since the
package is a declared dependency (the existing `test_observability.py`
import-injection pattern applies).

---

## 8. RULE-XX Compliance

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-01b | ✅ | OTel instrumentation paths unchanged; no direct provider/agent bypass. |
| RULE-03 | ✅ | Contract (`record_otel_setup_outcome`, `get_observability_status` shape) specified **before** implementation (this doc); AUFG-05-14 implements against it. |
| RULE-05 | ✅ | Module boundaries unchanged: state lives in `_app/observability.py`; setup in `_app/telemetry.py`; reporting in `metrics/router.py`. No new module coupling. |
| RULE-06 | ✅ | Router delegates to `get_observability_status()`; severity computation is owned by the observability module, not the router. |
| RULE-07 | ✅ | All changes are within `apps/api/narrare/_app` and `metrics`. No `apps/` → `core/` import. |
| RULE-08 | ✅ | OTel remains the sole observability integration (ADR-031); no new external dependency. |
| RULE-09 | ✅ | Contract specifies fully-typed return shape; no `Any` in the new public fields. |
| RULE-11 | ✅ | **This policy closes the RULE-11 gap**: configured-but-broken setup is no longer silent; it is logged AND queryable from `/health` (§6). |
| RULE-12 | ✅ | Health is exposed via the standard API endpoint; no client-to-client coupling. |
| RULE-20 | ✅ | No dormant/incomplete observability path introduced; the failure path is fully specified. |

---

## 9. Options Considered

### Option A — DEGRADED for configured-but-broken, CRITICAL reserved for mandatory profile (**chosen**)

As specified in §2. DEGRADED reflects ADR-031's optional/local-first posture;
CRITICAL is configuration-gated.

**Pros:** Faithful to ADR-031; preserves local-first availability guarantee;
scales to mandatory profiles without re-derivation; consistent with the existing
CI-governance severity vocabulary.

**Cons:** Requires an implementation contract (AUFG-05-14) to make
configured-but-broken visible — but that is the correct RULE-11 outcome, not a
downside.

### Option B — CRITICAL whenever OTel is configured but broken

Any exporter setup failure → CRITICAL.

**Pros:** Maximally visible.

**Cons (rejected):** Violates ADR-031's local-first guarantee by coupling product
availability to optional infrastructure; would fail CI/releases for a
non-functional telemetry regression; erodes the HEALTHY/DEGRADED/CRITICAL
granularity (treats "telemetry down" == "product down"); no deployment profile
justifies it today.

### Option C — Keep status quo (warnings only, no health severity)

Leave `telemetry.py` swallowing the exception; `/health` stays `status: "ok"`.

**Cons (rejected):** This is the **exact RULE-11 silent-failure** that AUFG-05-10
was opened to fix. ADR-031 RULE-11 row already commits to visible degradation.
Rejecting this is the whole point of the policy.

### Option D — Add OTel as a gate in `check_system_health.py`

Surface OTel failure in the CI governance aggregator.

**Cons (rejected):** Category error. `check_system_health.py` aggregates **static
baseline debt** (architecture violations, test pass rates). OTel exporter status
is a **runtime** property unmeasurable from baseline data. The CI tool and the
runtime `/health` endpoint share a *vocabulary* (§4), not a measurement surface.

---

## 10. Architectural Invariants

These invariants hold from this policy forward. Violating any of them requires
re-review of this document and ADR-031.

- **INV-OH-1:** OTel failure MUST NOT elevate the runtime `/health` severity above
  DEGRADED unless a deployment profile explicitly declares OTel mandatory.
- **INV-OH-2:** The production default for `NARRARE_OTEL_INCLUDE_CONTENT` MUST be
  `false`. Changing it requires a privacy review and an ADR.
- **INV-OH-3:** OTel setup failure MUST be both logged (privacy-safe) AND
  queryable from `get_observability_status()` / `/health`. Either channel alone
  is a RULE-11 violation.
- **INV-OH-4:** The `/health` `status` vocabulary MUST stay aligned with the CI
  governance vocabulary (`healthy`/`degraded`/`critical` ↔
  `HEALTHY`/`DEGRADED`/`CRITICAL`). Introducing a divergent runtime-only status
  word requires re-review.
- **INV-OH-5:** DEGRADED OTel MUST NOT flip `/ready` to 503. Readiness reflects
  ability to serve product requests; telemetry loss does not impair that.

---

## 11. Sustainability Check

1. **Correct in 3 months?** Yes. The policy is rooted in ADR-031's stable
   local-first decision. The DEGRADED mapping does not depend on transient state.
2. **Hard-to-undo coupling?** No. The contract extends an existing function's
   return shape (backward-compatible `available` retained) and adds one recording
   function. No new external dependency, no cross-layer coupling.
3. **Simplest correct solution?** Yes. It distinguishes the two OTel conditions
   (off vs. broken) with the minimum necessary state (`state` + `severity`) and
   reuses the existing severity vocabulary rather than inventing a new one.
4. **Design intent clear?** Yes. The invariant set (INV-OH-1..5) and the 5×Why
   chain make the intent legible to the next developer.

---

## 12. Review Triggers

Re-review this policy when:

- AE-05-02 (managed hosting) is promoted to implementation — S5 / CRITICAL
  blocking mechanism must be decided.
- A deployment profile is introduced that declares OTel mandatory.
- `NARRARE_OTEL_INCLUDE_CONTENT` production default is proposed to change.
- The `/health` or `check_system_health.py` severity vocabulary is proposed to
  diverge.
- ADR-031 is superseded or OpenTelemetry is replaced as the trace standard.
- A new OTel failure mode emerges that does not fit `state` ∈ {not_configured,
  configured_ok, configured_failed, package_unavailable}.

---

## 13. References

- **ADR-031** — Local-First OpenTelemetry Observability (authority for OTel
  architecture and RULE-11 commitment).
- **AUFG-05-10** — Source finding (Review-05); this policy is its architecture
  deliverable.
- **AUFG-05-14** — Implementation AUFG (Backend/Platform): realizes the contract
  in §7 and the test matrix in §7.5.
- **`apps/api/narrare/_app/observability.py`** — `get_observability_status()`,
  `_probe_once()`, state tracking (to be extended per §7.1).
- **`apps/api/narrare/_app/telemetry.py`** — `setup_telemetry()` (to call
  `record_otel_setup_outcome()` per §7.2).
- **`apps/api/narrare/metrics/router.py`** — `/health` endpoint (to adopt
  severity vocabulary per §7.3).
- **`scripts/check_system_health.py`** + **`scripts/health_types.py`** — CI
  governance severity vocabulary (HEALTHY/DEGRADED/CRITICAL, thresholds 0.85/0.70).
- **`docs/_shared/CONSTRAINTS.md`** — RULE-11 (no silent failures), RULE-06/07
  (module boundaries / dependency direction).
