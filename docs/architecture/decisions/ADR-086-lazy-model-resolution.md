# ADR-086 — Lazy Model Resolution via shared `ModelResolution` Abstraction (Validation Precedence for AI Endpoints)

> **Status:** ✅ Implemented (design approved by the Architecture layer 2026-09-09;
> implementation slices S1–S4 landed 2026-09-09 — Gate 12 criteria met
> (S1–S4 wired + regression-contract-verified, ledger entries 1–5 checked
> off); remaining ledger entries 6–39 open (migration backlog) — see
> Implementation Notes)
> **Date:** 2026-09-09
> **Deciders:** Architecture Agent
> **Related:** ADR-082 (token-budget governance — `get_resolved_limits` cascade is
> a deferred resolution source here, unchanged in content),
> ADR-045 (run-limit resolution precedent — timing contrast),
> P2 fix package 2026-09-09 (nonexistent-novel 404 guard in
> `ModelRoutingResolverImpl.resolve()` — semantics preserved, timing moves),
> RULE-03/04/06/11/12/18/18b/19

---

## Context

### The defect class: dependency resolution preempts body validation

FastAPI 0.141.1 solves **all sub-dependencies before request-body validation**.
Verified at source level in the installed package
(`fastapi/dependencies/utils.py`, `solve_dependencies`): the
`for sub_dependant in dependant.dependencies` loop runs to completion before
`request_body_to_args` is ever called. Any environment/config-dependent work
performed inside a `Depends` factory therefore executes **before** the request
body is validated.

Consequently, every AI dependency factory that resolves provider/model
configuration at construction time can preempt a legitimate `422` validation
error with a different, wrong status:

- **400 `NO_AI_PROVIDER`** instead of `422` when the body is invalid *and* the
  user has no AI provider configured (the dependency raises
  `ConfigurationError` before the body is ever looked at).
- **500 FK violation** instead of `422`/`404` when the resolution path touches
  the DB — `ModelRoutingResolverImpl.resolve()` reads/creates
  `project_ai_settings` rows (`ProjectAiSettingsRepository.get()` runs
  `INSERT … ON CONFLICT DO NOTHING`, which never suppresses FK violations),
  so a nonexistent `novel_id` in the body explodes as an unhandled
  `asyncpg.ForeignKeyViolationError` before validation can reject the payload.
- **200 with degraded behavior** instead of `422` on gracefully-degrading
  optional-AI paths.

### Observed evidence

| # | Symptom | Location |
|---|---------|----------|
| 1 | Dialogue-coach SSE: invalid body → `400 NO_AI_PROVIDER` instead of `422` | `tests/integration/ai_assist/test_dialogue_coach_sse.py` |
| 2 | Memory analyze: invalid body → `400` (and one `200`-class case) instead of `422` | `tests/integration/memory/test_memory_analyze_api.py` |
| 3 | CI-only FK-500s: `POST /api/v1/analysis/beta-reader/deep-dive` and `/readability` with nonexistent `novel_id` → 500 | analysis integration tests (CI order-dependent DB state) |

**Root cause (2× Why):**
1. *Symptom:* wrong status codes (400/500/200 where 422 is correct).
2. *Why?* Because provider/model/token-limit resolution runs inside FastAPI
   dependency factories, i.e. before the handler and before body validation.
3. *Why does that ordering bite?* Because FastAPI 0.141.1 structurally solves
   all sub-dependencies before `request_body_to_args` — the eager resolution
   and the validation ordering are on a collision course by construction. No
   amount of parameter reordering inside the handler signature can change it.

---

## Decision Drivers

- **Correct HTTP semantics** — an invalid request body must yield `422`
  regardless of the caller's AI configuration state; validation errors must
  not be masked by environment-dependent failures.
- **Root cause, not symptom** — the fix must address *when* resolution runs,
  not re-map statuses after the fact.
- **One shared primitive (RULE-04)** — the codebase has ~40 eager factory
  call-sites with this defect; a per-module bespoke fix would multiply drift.
- **Contract-first (RULE-03)** — the abstraction is a Protocol; services
  depend on the contract, not on a concrete resolver.
- **Thin routers (RULE-06/RULE-12)** — resolution stays in the service layer;
  routers delegate.
- **Loud failures (RULE-11)** — `ConfigurationError` must still propagate
  loudly on AI-mandatory endpoints; no swallowing.
- **Resolution-source stability (RULE-18/18b)** — the ModelRoutingResolver
  cascade and token-limits cascade remain the single sources of truth; only
  *timing* changes.
- **Incremental rollout** — per-module slices must be safe to ship
  independently; the remaining eager factories are tracked, not forgotten.

---

## Options Considered

### Option (a) — Lazy resolution via a shared `ModelResolution` abstraction (chosen)

DI factories keep wiring eagerly (repositories, registry, composer), but
provider/model configuration is resolved on **first use** inside the service
layer, behind one shared abstraction:

- `ModelResolution` — Protocol with `async def resolve() -> ResolvedModel`
  (+ api key/base url envelope as resolved today),
- `LazyModelResolution` — the production implementation: wraps resolver +
  intent + user/project ids, caches the result after the first `await`
  (idempotent),
- `StaticModelResolution` — pre-resolved config for tests and
  `app.dependency_overrides`.

Hosted in `apps/api/narrare/_app/dependencies_services.py` (the canonical
wiring home). ~60 LOC total.

**Pros:** fixes the ordering defect at its root; one primitive for all ~40
call-sites; Protocol-first (RULE-03); test-friendly; per-module migration
possible; SSE pre-header error semantics preservable with one idempotent line.

**Cons:** services gain an explicit resolution step; migration is incremental
(a ledger tracks the remainder).

### Option (b) — Parameter/dependency ordering

Reorder handler parameters / sub-dependencies so body validation runs first.

**Rejected.** Refuted at FastAPI source level: `solve_dependencies` completes
the sub-dependency loop before `request_body_to_args` — ordering of parameters
does not and cannot change this. Any "fix" along these lines couples to
FastAPI internals and stops working on the next refactor of `solve_dependencies`.

### Option (c) — Handler-side resolution

Resolve provider/model inside the router handlers themselves.

**Rejected.** Puts business logic into routers (RULE-06/RULE-18); duplicates
resolution logic across every handler; untestable in isolation from HTTP.

### Option (d) — Middleware status re-mapping

Post-process responses in middleware: turn 400s into 422 when the body was
invalid, etc.

**Rejected.** A workaround: by re-mapping time the body is already discarded;
middleware cannot reliably distinguish "invalid body" from "unconfigured
provider"; fixes neither the FK-500 (the 500 never was a 400) nor SSE in-band
errors (the response has already started streaming). Treats the symptom, not
the ordering.

### Option (e) — Shared abstraction WITHOUT lazy-first-use

Introduce `ModelResolution` but keep resolving inside the factories.

**Rejected.** Keeps the ordering defect entirely — the abstraction would be
inert ceremony. (Listed for completeness: any migration that stops at the
type change without moving resolution past validation is this option in
disguise.)

---

## Decision

**We choose Option (a)** — lazy resolution via one shared `ModelResolution`
abstraction — in six decisions:

1. **Shared abstraction, one home.** `ModelResolution` (Protocol
   `resolve()`), `LazyModelResolution` (cached async, idempotent), and
   `StaticModelResolution` (tests/overrides) live in
   `apps/api/narrare/_app/dependencies_services.py` — the canonical wiring
   home (RULE-03 Protocol-first, RULE-04 one shared primitive instead of ~40
   local variants).

2. **Factories wire eagerly, resolve lazily.** DI factories continue to
   construct repos/registry/composer eagerly; the *provider/model resolution*
   (and, where applicable, token-limit resolution) moves to **first use**
   inside the service layer. Services call `await resolution.resolve()` (or
   the convenience `await self.ensure_resolved()`) at the top of their
   entry-point methods.

3. **SSE pre-header contract.** SSE-bearing routers MUST call
   `await service.ensure_resolved()` **before** constructing the
   `StreamingResponse`, so a `ConfigurationError` still surfaces as a proper
   pre-header 400 rather than an in-band SSE error. Idempotent, one line,
   RULE-06-compatible (pure delegation to the service).

4. **Resolution sources unchanged (RULE-18/18b).** The
   `ModelRoutingResolver` cascade and the token-limits cascade
   (`TokenLimitsService.get_resolved_limits`) remain the authoritative
   sources; only *when* they run changes. No new cascade, no new defaults.

5. **Error semantics.** On AI-mandatory endpoints `ConfigurationError` still
   propagates loudly (RULE-11; no planning-style swallowing): valid body +
   unconfigured provider → 400 before any stream starts; invalid body → 422
   regardless of provider state; nonexistent `novel_id` → 404 via the P2
   novel-guard inside `resolve()` (semantics unchanged, now simply evaluated
   after validation).

6. **Ledger-governed migration.** The remaining eager factories are tracked
   in the migration ledger below; each slice/SKU checks off its entries.
   Unmigrated entries knowingly retain 400-before-422 until their slice
   lands — visible debt, not silent debt.

---

## Rationale

The root cause is an ordering conflict between FastAPI's dependency solving
(all sub-dependencies before body validation) and environment-dependent work
placed in dependency factories. Only two levers exist: move the work later
(lazy) or re-map the results later (middleware). Everything else (b, c, e) is
either structurally impossible or relocates the defect.

Option (a) is the only choice that fixes the class, not the instances: one
Protocol replaces ~40 copies of the eager pattern, migration can proceed
module by module with zero big-bang risk, and the SSE pre-header requirement
is satisfied by a single idempotent call rather than by new infrastructure.
The conscious trade-off is transitional inconsistency (migrated endpoints
return 422; ledger entries still return 400) — made acceptable by the ledger
being a binding checklist in this ADR, not a backlog wish.

---

## Consequences

**Positive:**

- Invalid bodies get `422` on migrated endpoints regardless of AI provider
  state; the FK-500 class on AI endpoints disappears as slices land.
- One testable seam (`StaticModelResolution`) for overrides; simpler tests
  (no resolver monkeypatching for config-free cases).
- SSE error contract preserved (pre-header 400) by construction.
- The P2 novel-guard (404) keeps working — evaluated after validation, where
  it belongs semantically.

**Negative / Trade-offs:**

- Services gain an explicit resolution step (`ensure_resolved()` /
  `resolve()` at the top of entry points).
- Two coexisting timings until the ledger is empty; consumers see different
  status codes for identical invalid payloads on migrated vs. unmigrated
  endpoints.
- Each SSE router carries one extra mandatory line — forgetting it would
  move errors in-band (caught by the regression contract's SSE 422 nodes).

**Constraints introduced / touched:**

- RULE-03 (Protocol first — `ModelResolution` before any implementation),
- RULE-04 (one shared primitive in `dependencies_services.py`, not per-module
  copies),
- RULE-06/RULE-12 (routers stay thin; `ensure_resolved()` is delegation, not
  logic),
- RULE-11 (`ConfigurationError` propagates loudly on AI-mandatory endpoints;
  no swallowing),
- RULE-18/18b (resolution sources stay the ModelRoutingResolver cascade and
  token-limits cascade; only timing changes),
- RULE-19 (`SessionDep`-based factories unchanged).
- Layering router→service unchanged; no core→apps import (the abstraction is
  API-app-local; `packages/core` is unaware of it).

---

## Implementation Notes

### Slice plan

- **S1 — Abstraction.** Add `ModelResolution` (Protocol),
  `LazyModelResolution`, `StaticModelResolution` to
  `apps/api/narrare/_app/dependencies_services.py`. Inert by default: no
  consumer changes in S1.
- **S2 — ai_assist.** `ai_assist/dependencies.py` wires
  `LazyModelResolution` instead of resolving; `service.py` gains idempotent
  `ensure_resolved()` consumed at the agent-runner call;
  `router.py` calls `await service.ensure_resolved()` before the
  `StreamingResponse` (pre-header 400 preserved).
- **S3 — memory.** `memory/router_analysis.py` factory switches to lazy
  wiring; `analysis_service.py` resolves at the top of `_run_agent()`,
  preserving the existing monkeypatch seam (documented in the test
  docstring).
- **S4 — analysis.** `analysis/dependencies_beta_reader.py`,
  `analysis/dependencies.py`, and the services defer **both**
  `resolver.resolve()` **and** `token_limits_service.get_resolved_limits()`
  past validation. Budgeted separately (it is the FK-500 epicenter).

### Migration ledger (mandatory)

Eager resolver factories that retain 400-before-422 until migrated. Each
slice/SKU checks off its entries. Sweep of `apps/api/` for factories calling
`resolver.resolve(...)` / provider resolution / `get_resolved_limits(...)`
at construction (2026-09-09; factory function names verified):

**Slice-scoped (S2–S4):**

1. [x] `ai_assist/dependencies.py` — `get_dialogue_coach_service` *(S2 —
       landed 2026-09-09: lazy wiring + `ensure_resolved()` + SSE
       pre-header call)*
2. [x] `memory/router_analysis.py` — `_get_analysis_service` *(S3 —
       landed 2026-09-09: lazy wiring + first-use resolve at the top of
       the service's `_run_agent()`)*
3. [x] `analysis/dependencies_beta_reader.py` — `get_beta_reader_service`
       (+ eager `get_resolved_limits`) *(S4-beta — landed 2026-09-09: lazy
       wiring + deferred budget-assembler composition, both cascades at
       service first use)*
4. [x] `analysis/dependencies.py` — `get_readability_service` *(S4a —
       landed 2026-09-09: lazy wiring, first-use resolve at the top of
       `ReadabilityService.analyze()`)*
5. [x] `analysis/dependencies.py` — `get_pov_service` *(S4a —
       landed 2026-09-09: lazy wiring, first-use resolve at the top of
       `POVService.analyze()`)*

**Open (29):**

6. [x] `analysis/dependencies_character_voice.py` — `get_character_voice_service`
       *(A1/L06 — landed 2026-09-13: lazy wiring + first-use resolve +
       SSE pre-header call)*
7. [x] `analysis/dependencies_coreference.py` — `get_coreference_service`
       *(A2/L07 — landed 2026-09-13: lazy wiring + first-use resolve +
       SSE pre-header call)*
8. [x] `analysis/dependencies_voice_check.py` — `get_voice_check_service`
       *(A3/L08 — landed 2026-09-14: lazy wiring + first-use resolve +
       SSE pre-header call)*
9. [x] `analysis/dependencies_author_voice.py` — `get_author_voice_service`
       *(A4/L09 — landed 2026-09-14: lazy wiring + first-use resolve +
       SSE pre-header call)*
10. [x] `analysis/dependencies_author_voice_drift.py` — `get_author_voice_drift_service`
       *(A5/L10 — landed 2026-09-14: lazy wiring + first-use resolve +
       SSE pre-header call)*
11. [ ] `analysis/dependencies_voice_drift.py` — `get_voice_drift_service` (SSE)
12. [ ] `chat/dependencies.py` — `get_chat_service` (SSE)
13. [ ] `consistency/deps.py` — `get_consistency_service` (two eager resolves: fact-extraction + consistency)
14. [ ] `generation/router.py` — `_get_service` (NameGeneratorService factory)
15. [ ] `kb/_consistency_deps.py` — `get_consistency_service` (two eager resolves: consistency + worldbuild)
16. [ ] `kb/dependencies_extraction.py` — `get_extraction_service`
17. [ ] `kb/dependencies_improve.py` — `get_kb_improve_service`
18. [ ] `kb/dependencies_session.py` — `get_kb_session_service`
19. [ ] `kb/dependencies_worldbuilding.py` — `get_worldbuilding_service`
20. [ ] `planning/_character_arc_factory.py` — `get_character_arc_service`
21. [ ] `planning/_service_factory.py` — `get_storyboard_service`
22. [ ] `planning/_timeline_analysis_factory.py` — `get_timeline_analysis_service`
23. [ ] `planning/_timeline_consistency_factory.py` — `get_timeline_consistency_service`
24. [ ] `planning/_timeline_extraction_factory.py` — `get_timeline_extraction_service`
25. [ ] `series/dependencies.py` — `build_band_summary_service` (+ eager `get_resolved_limits`)
26. [ ] `series/dependencies_consistency.py` — `get_series_consistency_service`
27. [ ] `series/dependencies_context_preview.py` — `get_series_history_preview_service` (+ eager `get_resolved_limits`)
28. [ ] `series/dependencies_voice.py` — `get_series_voice_service`
29. [ ] `series/dependencies_voice_drift.py` — `get_series_voice_drift_service`
30. [ ] `wiki/dependencies.py` — `get_wiki_service`
31. [ ] `writing/deps_coauthor.py` — `get_coauthor_service` (+ eager `get_resolved_limits`)
32. [ ] `writing/deps_extend.py` — `get_extend_service` (+ eager `get_resolved_limits`)
33. [ ] `writing/deps_rewrite.py` — `get_rewrite_service` (+ eager `get_resolved_limits`)
34. [ ] `writing/deps_story_suggest.py` — `get_story_suggest_service`
       (graceful-degradation variant: swallows `ConfigurationError` —
       AI-optional feature; migration must preserve that degradation
       behavior, moved past validation)
35. [ ] `writing/deps_style_variants.py` — `get_style_variant_service` (+ eager `get_resolved_limits`)
36. [ ] `writing/deps_suggest.py` — `get_suggest_service`
37. [ ] `writing/deps_writing.py` — `get_writing_service` (+ eager `get_resolved_limits`)
38. [ ] `writing/summary_deps.py` — `get_summary_service` (+ eager `get_resolved_limits`)
39. [ ] `writing/router_sessions.py` — `interactive_session` (inline eager
       resolve + `get_resolved_limits` in session bootstrap)

Migration rule per entry: wire `LazyModelResolution`, resolve at first use in
the service, apply the SSE pre-header line where the endpoint streams, and
check the entry off in the same slice/SKU.

**Explicitly NOT in the ledger** (verified 2026-09-09 — not eager
construction-time resolution): service-internal `_run_limit_resolver.resolve(...)`
calls (already first-use: `beta_reader_service`, `pov_service`,
`readability_service`, `coreference_service`, `summary_service`,
`story_suggest_service`, `ws_turn_service`, `_interview_draft`, planning/KB
services); `kb/entity_resolution/dependencies_adjudicator.py` (resolve is
deferred behind the `merge_service_factory` closure invoked in
`adjudicate()`); `consistency/checker_context.py` (`collect_check_context`,
service-layer); `chat/_invocation.py` and `wiki/dependencies_core.py`
(run-limit resolver at agent-run/prep time, not ModelRoutingResolver);
`settings/token_limits/router.py` (the resolution IS the product of that
settings endpoint); `build_system_default_config` (settings-only, no DB, no
user context).

### Regression contract

- **Green after S2+S3:** `test_dialogue_coach_sse` invalid-body → 422 (×2
  nodes); `test_memory_analyze` 422/schema nodes (×2).
- **Green after S4:** beta-reader deep-dive + readability with empty/missing
  `chapter_ids` → 422 nodes.
- **MUST NOT change:** 401-without-auth nodes; SSE happy-path with override;
  valid-body + unconfigured provider → 400 **pre-headers**; P2 novel-guard
  404 semantics; service unit-test outcomes.

**ADR Implementation Completeness Gate (Gate 12):** this ADR reaches
"✅ Implemented" only when S1–S4 are fully wired, tested, and
regression-contract-verified, and the migration ledger entries 1–5 are
checked off. Ledger entries 6–39 do not block the gate — they are tracked
debt with their own per-entry check-offs.

---

## Review Trigger

- [ ] When the migration ledger reaches zero: add an architecture check
      forbidding `resolver.resolve(`/`get_resolved_limits(` inside `Depends`
      factories (prevention, mirroring this ADR).
- [ ] When FastAPI changes dependency solving/body-validation ordering
      (watch `solve_dependencies` changelogs): re-evaluate whether the eager
      pattern becomes safe again (it may never — lazy stays simpler).
- [ ] When a new AI endpoint is added: it must wire `ModelResolution` from
      day one; no new ledger entries.
- [ ] If an SSE consumer requires in-band error events instead of pre-header
      400s: revisit Decision 3 in a dedicated amendment.
