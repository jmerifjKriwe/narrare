# ADR-060 — Retry False-Control Resolution (AUFG-01-01): Reclassify Transport Retry to the Provider Layer

> **Status:** ✅ Implemented (Implemented 2026-07-01)
> **Date:** 2026-07-01
> **Deciders:** Architecture Specialist (recommendation); Coordinator + User approved Option B
> **Supersedes:** —
> **Related:** ADR-015 (Agents first-class / Gateway v2), ADR-051 (RULE-18b Configuration Effect Adoption Contract), ADR-061 (Matrix Effect-Integrity Hardening), AUFG-01-01, CONSTRAINTS.md RULE-18b / RULE-20 / RULE-22

---

## Context

Review-01 (verified 2026-07-01 via the code graph + live source reads) found that the
LLM retry settings are a **false control**: a value exposed, stored, resolved, and
documented as user/project-configurable that never reaches the runtime boundary it
claims to affect (RULE-18b violation #1, "exposed setting without a runtime consumer").

### Verified evidence (2026-07-01)

- `packages/core/narrare_core/llm/retry.py::with_retry` — the only retry boundary in
  the codebase — has **zero production callers**. The code graph (`trace_path` inbound)
  returns `[]`. `RetryConfig` is referenced only inside `retry.py` itself (the preset
  constants `DEFAULT_RETRY` / `FAST_RETRY` / `PATIENT_RETRY` / `NO_RETRY`).
- `packages/core/narrare_core/llm/gateway.py` (Gateway v2, the RULE-01b LLM boundary)
  calls `agent.run()` / `agent.run_stream()` directly in `ModelRegistry.run()`
  (line 132) and `ModelRegistry.stream()` (line 217). Neither path imports or invokes
  `with_retry`.
- The two retry settings are resolved but never consumed:
  `apps/api/narrare/settings/token_limits/service.py::_apply_env_layer` resolves
  `retry_max_attempts = cfg.retry_max_attempts` and `retry_base_delay =
  cfg.retry_base_delay` into `TokenLimitOverrides` (lines 204–206). The merged result
  is returned to callers and stored, but **no LLM / SSE / WebSocket retry boundary reads
  the resolved retry values**.
- The false control is a **complete end-to-end chain**: UI inputs
  (`packages/web/components/studio/settings/SystemTimeouts.tsx` — `retry_max_attempts`
  1–10, `retry_base_delay` 0.1–30) → frontend types (`packages/web/types/settings.ts`)
  → API DTO (`apps/api/narrare/settings/token_limits/schemas.py:157–159`) → router
  (`router.py:73–75`) → validator (`_validators.py:27–29`) → DB (`models.py`) →
  resolver (`TokenLimitsService`) → **dropped**.

### Matrix false claim (aggregation defect)

The Configuration Adoption Matrix entry `websocket_idle_retry_cascade` aggregates
**three** settings under one row (`ws_idle_timeout_seconds`, `retry_max_attempts`,
`retry_base_delay`) and declares `lifecycle: adopted`. But its `source`,
`runtime_consumer`, and `enforcement_evidence` cover **only** `ws_idle_timeout_seconds`
→ `WritingSessionHandler` (the WebSocket idle timeout). The two retry fields ride the
coattails of a real setting to inherit an `adopted` claim they do not earn.

### Root-cause chain (≥2× "Why")

- **Symptom:** two settings look implemented (UI → DB → resolver) but never affect runtime.
- **Why #1 — why did the false control survive?** The matrix checker
  (`scripts/governance/configuration_matrix.py::validate_matrix`, Rules 6/7/8) validated
  that `runtime_consumer` and `enforcement_evidence` are **non-empty strings**, not that
  they are **true**. An entry may cite `runtime_consumer: "WritingSessionHandler"` and
  `enforcement_evidence: "test_ws_handler.py"` and PASS even though those tests exercise
  the idle timeout, not retry. **RC1 — checker-blindness:** the gate trusts field
  presence, not field truth. *(Historical — the configuration-adoption-matrix.yaml and
  `scripts/governance/` checker referenced throughout this root-cause analysis were
  subsequently removed in `f8abb42c`; the analysis of how the false control survived
  remains valid history.)*
- **Why #2 — why could one entry cover three settings?** The matrix has no
  one-setting-per-row rule. `websocket_idle_retry_cascade` aggregates three settings, so
  one real runtime consumer + one evidence path satisfies the whole row. **RC2 —
  aggregation defeats per-setting effect integrity.** RULE-18b is phrased per *value*
  ("a configurable value … consumed at the runtime boundary it claims to affect"), but
  the checker operates per *entry*, with no per-setting granularity.
- **Why #3 (deepest) — why does `with_retry` exist at all with no caller?** It is a
  **Gateway v1 vestige**. `with_retry` wraps a whole `Awaitable[T]` operation — the call
  shape of the pre-ADR-015 gateway that returned completed results. The codebase migrated
  to pydantic-ai Agents and Gateway v2 (`ModelRegistry`, ADR-015), whose call shape
  (`agent.run()` / `agent.run_stream()`) and whose underlying provider SDKs have their
  own transport retry. `with_retry` was never reconciled with the agent-first
  architecture, so it became dead code. **RC3 — abstraction drift:** the retry
  abstraction predates the current LLM architecture and was never re-homed or retired.

---

## Decision Drivers

- **RULE-18b (Configuration Effect Integrity):** the false control must be eliminated —
  either the resolved value reaches its runtime boundary with regression evidence, or the
  exposed surface is removed and the value reclassified.
- **RULE-20 (No half-implementations):** a full UI→API→DB→resolver chain that never
  retries is a half-implementation. The remedy must complete or remove the feature, not
  preserve the illusion.
- **RULE-22 (Cross-Feature Coherence):** any change to the settings cascade (token
  limits, writing context, provider construction) must remain coherent across layers.
- **Architectural discipline §1 (root cause first) / §3 (≥2 alternatives) / §5
  (sustainability):** the choice must address RC1–RC3, not just the symptom, and remain
  correct in 3–12 months.
- **Agent-first boundary (ADR-015 / RULE-01b):** LLM transport behavior belongs to
  `core/llm/` (provider construction), not to user/project token-limit overrides.

---

## Options Considered

### Option A — Wire `with_retry` into the Gateway `run()`/`stream()` path (Alt 1)

Thread the resolved `retry_max_attempts` / `retry_base_delay` from
`TokenLimitOverrides` → a `RetryConfig` → into `ModelRegistry.run(...)` /
`ModelRegistry.stream(...)`, wrapping `agent.run()` / `agent.run_stream()` in
`with_retry`.

**Pros:**
- Reuses the existing `with_retry` / `RetryConfig` abstraction; the user-facing settings
  would, at last, take real effect (with an effect regression test).

**Cons:**
- **Streaming incoherence (fatal).** `with_retry` wraps a complete `Awaitable[T]`. The
  dominant UX for AI writing is SSE streaming (`ModelRegistry.stream()`), which yields
  chunks to the client as they arrive. Once partial prose has been streamed, the
  operation cannot be retried — you cannot un-send SSE frames or un-show partial text to
  the author. Operation-level retry is only coherent for the non-streaming `run()` path
  and the *connection-establishment* phase of `stream()`. Wiring it generically creates a
  retry that silently does nothing for the streaming path that matters most — a new false
  control.
- **Double-retry with provider SDKs.** The OpenAI / Anthropic SDK clients already retry
  transient transport errors (429 / 5xx / timeouts) with their own backoff (`max_retries`,
  default 2). A narrare `with_retry` layer on top nests two backoffs, inflating
  user-perceived latency and risking thundering-herd on rate limits. The two layers must
  be carefully composed; naively wiring produces worse behavior than today.
- **pydantic-ai retry interaction.** pydantic-ai retries `ModelRetry` for
  tool/`result_validator` validation failures — a *semantic* retry, not a transport
  retry. `with_retry`'s error taxonomy (`LLMRateLimitError` etc.) is not produced by the
  Gateway v2 call path (`gateway.py` only catches `UsageLimitExceeded`), so `with_retry`
  would also require a new exception-translation layer before it could even fire.
- **Coupling + dependency-direction cost.** Resolved user/project token-limit overrides
  (a backend concern, `apps/api`) would have to be threaded into the core gateway as a
  `RetryConfig` parameter, coupling provider-transport behavior to per-user DB settings.
- **Sustainability:** fails the 3-month check — it fights the provider SDK and cannot
  serve streaming.

### Option B — Reclassify: transport retry is governed at the provider layer; remove the false user surface (Alt 2)  [RECOMMENDED]

Declare `retry_max_attempts` / `retry_base_delay` to be **not** user/project token-limit
settings. LLM transport retry is governed at the architecturally correct boundary — the
**provider factories** in `packages/core/narrare_core/llm/_providers/`, where the
pydantic-ai `Model` (and its underlying SDK client) is constructed — as a
`governed_default` (or `operator_default` from `Settings`) with rationale, owner, and a
fail-if-changed effect test. Remove the false user-configurable surface end-to-end and
retire the Gateway v1 vestige.

**Pros:**
- Removes the false control at the root (RC1 surface disappears; the exposed settings no
  longer exist to be lied about).
- Localizes transport retry to the **correct layer**: provider SDK construction already
  owns retry; Narrare governs it there with a real effect test (changing the governed
  default changes the SDK client's `max_retries`). No double-retry, no streaming
  incoherence — provider SDK retry handles connection/first-token establishment
  uniformly for both `run()` and `stream()`.
- Honors RULE-20: the feature becomes *complete* at the provider layer (real, tested
  retry) rather than *half-present* at the user-settings layer.
- Honors dependency direction: `core/llm/_providers` is the LLM transport owner; it reads
  retry from a governed default / operator Settings, not from user DB overrides.
- Retires dead code (`with_retry` / `RetryConfig`) — RULE-22 / architectural hygiene.
- Sustainable: correct regardless of provider, unchanged by future streaming evolution.

**Cons:**
- Sacrifices *user/project-configurable* retry backoff. Assessed as low value: provider
  SDKs already retry sensibly; per-user backoff that composes badly with provider retry is
  a footgun; the local-first single-user model means the operator-env knob (not a per-user
  DB setting) is the right control surface.
- Requires a cross-layer removal: UI inputs, frontend types, API DTO fields, router
  mapping, validator allow-list, and DB override keys for `retry_*` must all be removed or
  migrated, plus a migration consideration for any stored user override (see
  Implementation Notes).

### Option C — Hybrid: keep `with_retry`, wire only the non-streaming `run()` path, leave stream() as-is

Wrap only `ModelRegistry.run()` in `with_retry`; leave `stream()` un-retried; keep the
user-configurable surface.

**Pros:** Partial effect; keeps the abstraction.

**Cons:** Rejected. It preserves RC1/RC3 (a retry abstraction that only covers half the
call surface is itself a half-implementation — RULE-20), leaves the streaming false
control intact, and still double-retries with the provider SDK on the `run()` path. It is
the worst of both options.

---

## Decision

**We choose Option B (Reclassify).** LLM transport retry is governed at the **provider
layer** (`core/llm/_providers/`) as a `governed_default` / `operator_default` with a real
effect regression test, **not** as a user/project token-limit setting. The false
user-configurable `retry_*` surface (UI → API → DB → resolver) is removed end-to-end, and
the Gateway v1 vestige (`with_retry` / `RetryConfig`) is retired.

This is not "giving up on retry." Narrare still retries transient transport errors — at
the correct layer (provider SDK construction), where retry already lives and where it
works uniformly for streaming and non-streaming calls.

### Immediate remediation consequences (the AUFG-01-01 DoD)

1. **Provider-layer retry is made real and proven.** The provider factories set the SDK
   client's `max_retries` from a governed default (and/or operator `Settings`), with a
   fail-if-changed test proving a changed value changes retry behavior at the runtime
   boundary. This satisfies RULE-18b for transport retry at the correct boundary.
2. **The false user/project surface is removed.** `retry_max_attempts` and
   `retry_base_delay` are removed from the user-facing token-limit override surface:
   `TokenLimitOverrides`, `_validators.py` allow-list, `schemas.py` DTO, `router.py`
   mapping, frontend `SystemTimeouts.tsx` inputs, `AiTab.tsx` wiring, and
   `types/settings.ts`. `ws_timeout` **remains** — it has a real runtime consumer
   (`WritingSessionHandler` idle timeout).
3. **The Gateway v1 vestige is retired.** `with_retry`, `RetryConfig`, and the preset
   constants are removed (or, if the provider-layer retry test reuses the
   `delay_for_attempt` math, that pure helper may be preserved with a single production
   caller). Zero-production-caller dead code is not kept "for later."
4. **The aggregated matrix entry is split (P2 mandate).** `websocket_idle_retry_cascade`
   is decomposed into **per-setting rows** so RULE-18b is enforceable per entry:
   - `ws_idle_timeout` → its own `adopted` entry (real consumer: `WritingSessionHandler`;
     evidence: `test_ws_turn_budget.py`, `test_ws_handler.py`).
   - `llm_transport_retry` (provider `max_retries`) → a new entry classified
     `governed_default` / `operator_default`, with the provider-factory runtime consumer
     and the new effect test as evidence.
   - The standalone `retry_max_attempts` / `retry_base_delay` *user* settings cease to
     exist as matrix entries (removed, not merely re-labeled).

---

## Rationale

The deciding factor is **sustainability at the correct layer**. Transport retry for
external LLM providers is inherently a provider-client concern: the SDK clients already
implement it, it must apply uniformly to streaming and non-streaming calls, and
user-tunable backoff that double-retries with the SDK is a footgun rather than a feature.
Option A's operation-level `with_retry` is an abstraction from a prior gateway era
(RC3) that cannot serve streaming and fights the provider SDK; wiring it would create a
*new* false control for the streaming path. Option B removes the false surface, makes
retry real and tested at the layer that owns it, and retires dead code — addressing
RC1 (no surface to lie about), RC2 (per-entry split), and RC3 (vestige retired) together.

The sacrificed configurability (per-user retry backoff) is low-value and architecturally
misplaced; the operator-env / governed-default knob is the correct, safer control for a
local-first single-user product.

---

## Consequences

**Positive:**
- RULE-18b satisfied for transport retry at the correct runtime boundary, with evidence.
- One false-control class eliminated; the user no longer sees controls that do nothing.
- Dead Gateway v1 code retired; LLM retry has a single, tested home.
- The aggregated matrix entry is split, enabling ADR-061's per-entry enforcement.

**Negative / Trade-offs:**
- Cross-layer removal touches Core, Backend, and Frontend (Stage 3 work).
- Stored user overrides for `retry_*` (if any exist in DBs) become orphan keys; the
  resolver must ignore them gracefully (unknown-key drop, already the `_merge_overrides`
  behavior) and the removal should be documented in the SET-005 changelog. No destructive
  migration is required — the keys simply stop being read or written.
- Operators lose a per-user retry knob in favor of a governed/operative default.

**Constraints introduced:**
- **RULE-18b:** no user/project setting may be (re)introduced for LLM transport retry;
  transport retry is governed at the provider layer only.
- **RULE-20:** `with_retry` / `RetryConfig` may not be retained as "future" infrastructure
  without a production caller.
- Aggregated matrix entries are prohibited (see ADR-061).

---

## RULE-XX Compliance

| Rule | Status | Note |
|------|--------|------|
| RULE-18b | ✅ (post-remediation) | Transport retry proven at the provider boundary; false user surface removed. |
| RULE-20 | ✅ | Half-implemented user-retry chain removed; provider retry made complete + tested. |
| RULE-22 | ✅ | Cross-layer removal keeps the settings cascade coherent. |
| RULE-01b | ✅ | Retry stays inside `core/llm/` (provider factories); no LLM import leakage. |
| RULE-03 | ✅ | Provider-factory retry contract specified before Stage-3 implementation. |

---

## Implementation Notes (Stage 3 — Core/Backend/Frontend/Platform; NOT done by this ADR)

- **Core:** `packages/core/narrare_core/llm/_providers/` — set SDK client `max_retries`
  from a governed default / `Settings`; add the effect test in `tests/unit/core/llm/`.
  Decide governed_default vs operator_default in the implementation spec.
- **Backend:** remove `retry_*` from `TokenLimitOverrides`, `_validators.py`,
  `schemas.py`, `router.py`; keep `ws_timeout`.
- **Frontend:** remove `retry_*` inputs from `SystemTimeouts.tsx`, `AiTab.tsx`,
  `types/settings.ts`, and their tests; keep the `ws_timeout` control.
- **Platform:** update `configuration-adoption-matrix.yaml` per the P2 split above; this
  ADR's split is the concrete instance that ADR-061 generalizes into a prohibition.
  *(Historical — `configuration-adoption-matrix.yaml` was subsequently removed in
  `f8abb42c`; ADR-061 is ⛔ Superseded. This step is retained as the record of what was
  done at implementation time.)*
- **Cleanup:** remove `with_retry` / `RetryConfig` / presets from `retry.py` (or repurpose
  the file) once the provider-layer test is the sole consumer of any preserved helper.

**ADR Implementation Completeness Gate (Gate 12):** before marking ✅ Implemented,
verify the provider-layer effect test exists and passes, the user surface is gone in all
layers, the matrix is split, and `with_retry` has no remaining callers.

---

## Implementation Evidence (2026-07-01)

Implemented as Option B across Core / Backend / Frontend / Platform waves. The
Gate-12 completeness checks are satisfied:

- **Provider-layer retry (made real + proven):**
  - `packages/core/narrare_core/llm/_transport_retry.py` — governed source
    (`TRANSPORT_MAX_RETRIES_DEFAULT = 2`; env `NARRARE_LLM_TRANSPORT_MAX_RETRIES`;
    `get_transport_max_retries()`).
  - All 7 provider factories wired (`core/llm/_providers/`: openai, anthropic,
    ollama, zai, others[google/groq/openrouter]).
  - Effect test: `tests/unit/core/llm/test_transport_retry.py` (fail-if-changed).
- **False user/project surface removed (all layers):**
  - Backend: `retry_max_attempts` / `retry_base_delay` removed from
    `token_limits/` contracts, schemas, router, validators, service; operator
    `NARRARE_RETRY_*` removed from `_app/settings_model.py`. `ws_timeout` kept.
  - Frontend: `retry_*` inputs/types/i18n removed (9 keys × 3 locales); `ws_timeout`
    kept; `useTipTapEditorController` and `WritingPipeline.generate` modularized.
- **Gateway v1 vestige retired:** `packages/core/narrare_core/llm/retry.py`
  (`with_retry` / `RetryConfig`) and `tests/unit/core/llm/test_retry.py` deleted;
  code graph confirms `with_retry` has **zero** remaining callers post-deletion.
- **Matrix split (P2 mandate):** `configuration-adoption-matrix.yaml` entry
  `websocket_idle_retry_cascade` decomposed into `ws_idle_timeout` (adopted) and
  `llm_transport_retry` (adopted, operator governed default). `check-configuration-matrix`
  PASSED.
  *(Historical — the matrix file and `check-configuration-matrix` were removed in
  `f8abb42c`. The split itself and the underlying per-setting effect test
  (`test_transport_retry.py`) remain the real, surviving enforcement for transport retry;
  the matrix row no longer exists.)*
- **Registry:** AUFG-01-01 → `resolved` (exit evidence below).
- Prevention for the class of defect is ADR-061 (effect-integrity hardening,
  ✅ Implemented).

---

## Review Trigger

- When a provider is added or its SDK retry behavior changes.
- When a genuine requirement emerges for user-tunable retry (would require a new ADR
  evaluating composition with provider SDK retry and streaming semantics).
- If ADR-061's aggregation prohibition or effect-integrity checker is weakened.
