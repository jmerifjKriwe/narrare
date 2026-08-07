# ADR-079 — Series Cross-Novel Drift (SERIES-004 — Spec 4: Canon Contradiction + Series Voice Drift)

> **Status:** ✅ Implemented (decision in effect; all five slices shipped). Core (Task 1) +
> Backend (Tasks 2–3) landed; Frontend (Task 4) + i18n (Task 5) landed in commit `ede62081`
> (before the doc gate). See *Retrofit-Plan* for the per-slice state. Slice 6 (persistence —
> `GET …/consistency/{novel_id}` + results repository) is a deferred out-of-v1 follow-up, not
> part of this ADR's decision.
> **Date:** 2026-08-06
> **Deciders:** Architecture Specialist; User (approved the design spec
> `docs/superpowers/specs/2026-08-02-series-cross-novel-drift-design.md`)
> **Supersedes:** —
> **Related:**
> ADR-075 (Series Foundation — the Series-Canon KB layer this ADR's canon-contradiction
> check reads; `KBRepository.find_canon_for_series`),
> ADR-078 (Series Voice Hierarchy — the `SeriesSettings.author_voice` profile this ADR's
> series-scope voice drift uses as the trend baseline; closes its Review-Trigger Spec-4
> drift item),
> ADR-073/074/077 (Voice drift + author-voice storage + band-summary patterns reused),
> ADR-044 (Staged Consistency — the per-novel `ConsistencyAgent` this ADR's
> `SeriesConsistencyAgent` is the cross-novel complement of),
> ADR-055/057 (descriptive/metric boundary — preserved by construction; the series-voice
> drift reuses `author_metric_distances` which is comparison-only),
> CONSTRAINTS.md RULE-01b/02/02b/03/04/05/06/07/11/14/17/22,
> CR-04 (cross-feature coherence — canon-contradiction reads shared Canon data; series
> voice drift reads the shared `author_voice` column)

> **Scope of this ADR:** the **Series Cross-Novel Drift** vertical — (a) canon-contradiction
> detection (a novel's chapter text vs the series **Canon KB**) and (b) series-scope voice
> drift (the current band's narrator metrics vs the `SeriesSettings.author_voice` baseline),
> with the **current-band-vs-series** read-scope. Series **Export** (Spec 5) is **downstream
> program work**, flagged here but not designed here.

---

## Context

### Why this ADR exists

ADR-075 (Spec 1) introduced the Series-Canon KB — the cross-novel fixed-facts layer (magic
systems, world rules, canonical character bios) shared across every band in a series.
ADR-078 (Spec 3) introduced the `SeriesSettings.author_voice` profile — the shared
foundational voice for the series. Both ADRs explicitly deferred the *consistency* question
to Spec 4:

> *"Series voice drift across bands … This is deliberately Spec 4's concern (Cross-Novel
> Drift), not Spec 3's."* — ADR-078 Risk #4 / Review Trigger

ADR-078's Review Trigger carries an open Spec-4 item: *"verify the series-voice profile is
treated as one signal among bands (not a fixed baseline) and that drift detection reads
`SeriesSettings.author_voice` via the repository contract (no raw column access — the
ADR-050 'no SSOT bypass' analogue)."* **This ADR is Spec 4.** It closes that item.

Two distinct drift questions arise once a series has both a shared canon and a shared voice:

1. **Canon contradiction** — does band N's prose contradict the series' fixed canon? (e.g.
   the canon says "magic requires a spoken incantation"; band N has a mage casting silently
   with no explanation). This is a *novel-vs-series* check, distinct from CONS-001 (which
   checks *within* one novel).
2. **Series voice drift** — has band N's narrator drifted from the series' foundational
   voice? (e.g. the series voice is spare and literary; band N has become verbose and
   colloquial). This is the *series-scope* mirror of ANAL-009 Phase 2B's per-novel
   author-voice drift.

### Verified state (grounded, not assumed — per architectural-discipline §7)

| Concern | State | Location |
|---------|-------|----------|
| Series-Canon KB (read source) | EXISTS — ADR-075 (Spec 1). `KBRepository.find_canon_for_series` returns the canon entries for a series. | `apps/api/narrare/kb/scope_repository.py`, `canon_service.py` |
| `SeriesSettings.author_voice` (drift baseline) | EXISTS — added empty in Spec 1 (ADR-075), populated in Spec 3 (ADR-078). This ADR **reads** it as the trend baseline. | `apps/api/narrare/series/models.py` |
| `AuthorVoiceDriftAgent` + `author_voice_drift` scoring | EXISTS — ANAL-009 Phase 2B; the pipeline this ADR **reuses** (no new drift agent). | `packages/core/narrare_core/agents/author_voice_drift_agent.py`, `analysis/author_voice_drift_scoring.py` |
| `author_metric_distances` (shared delta normalisation) | EXISTS — extracted in ANAL-009 Phase 2B; reused unchanged for series-scope trend. | `packages/core/narrare_core/analysis/_metric_distances.py` |
| Per-novel `ConsistencyAgent` (CONS-001) | EXISTS — ADR-044; the *within-novel* checker. This ADR's `SeriesConsistencyAgent` is the *cross-novel* complement, NOT a replacement. | `packages/core/narrare_core/agents/consistency_agent.py` |
| `BandSummaryAgent` pattern (1-call Output-Function agent) | EXISTS — ADR-077; the implementation pattern `SeriesConsistencyAgent` mirrors. | `packages/core/narrare_core/agents/band_summary_agent.py` |
| `LLMIntent.ANALYSE` routeable intent | EXISTS — `series_consistency` added as a new `context_mode` (Mode 1). | `packages/core/narrare_core/prompts/route_table.py` |
| Frontend Bände-Tab | EXISTS — Spec 1; the integration surface for the per-band "Check" button (Task 4 — now landed in `ede62081`). | `packages/web/app/series/[id]/` |

### Program-level position

This is **Spec 4 of 5** in the Series program:

| # | Spec | Status |
|---|------|--------|
| 1 | Series Foundation + KB Evolution (ADR-075) | ✅ Implemented |
| 2 | Series Generation Context (ADR-077) | ✅ Implemented |
| 3 | Series Voice Hierarchy (ADR-078) | ✅ Implemented |
| **4** | **Series Cross-Novel Drift (this ADR)** | **✅ Implemented** |
| 5 | Series Export | Downstream |

---

## Decision Drivers

- **RULE-01b** — Agents are the way to use LLMs; models come from ModelRegistry. The new
  `SeriesConsistencyAgent` lives in `core/agents/`; the series-scope voice drift **reuses**
  the existing `AuthorVoiceDriftAgent` (no new drift agent).
- **RULE-02/02b** — No prompt assembly in services; resolution path exklusiv in
  `core/prompts/`. `series_consistency` is a governed Mode-1 template
  (`analysis/en/series_consistency/system.md`); the series-voice drift reuses the existing
  `author_voice_drift` governed template via the standard resolver.
- **RULE-03** — `SeriesConsistencyServiceProtocol` and `SeriesVoiceDriftServiceProtocol`
  (Core contracts) MUST exist before the services.
- **RULE-04/06** — Modularise; one responsibility per file. Canon-contradiction and
  series-voice-drift are two separate concerns in two separate service families
  (`series_consistency_*` + `series_voice_drift_*`), each with its own contracts/service/
  schemas/prompt/runtime-content/router.
- **RULE-05/07** — Core owns the agent + types + governed template; Backend owns the
  services + repositories + routers; no `core/`→`apps/` imports; dependency direction
  `router → service → repository → DB`. The Canon read goes through
  `KBRepository.find_canon_for_series` (no raw SQL); the series-voice read goes through
  `SeriesRepository` (no raw column access — the ADR-050 "no SSOT bypass" analogue
  ADR-078's Review Trigger demanded).
- **RULE-11** — Graceful degradation: a series with no Canon, a band with no chapters, a
  series with no voice profile, or a voice profile with no metrics all degrade to a no-op
  (canon: empty conflicts; voice-drift: `no_profile` event) — no LLM call, no crash.
- **RULE-17** — Frontend/back-end type parity: TS mirrors preserve snake_case (Task 4).
- **RULE-22 / CR-04** — Canon data and the voice profile are **shared data** (Canon is
  written by the KB editor, read by this check; the voice profile is written by
  `SeriesVoiceService`, read by this drift). Producer + consumer defined together; the
  read path goes through the repository contract (no bypass).
- **architectural-discipline §1/§4/§7** — Root-cause solution; no workarounds;
  "documented ≠ implemented" — the agent + services + contracts + tests must actually land
  (and the frontend + i18n slices must land before this ADR is marked fully ✅ Implemented).

---

## Options Considered

### Decision 1 — What to detect

| Option | Scope | Verdict |
|--------|-------|---------|
| **Voice Drift only** | series-scope narrator drift, no canon check | **Rejected** — leaves the most consequential series error (a band contradicting the shared canon) undetected. Canon contradiction is the higher-value signal. |
| **Voice Drift + Canon-Contradiction** *(CHOSEN)* | both | **Chosen** — covers the two cross-novel drift modes that matter: prose-style drift (voice) and fact drift (canon). Both reuse existing infrastructure (voice pipeline + 1-call agent pattern). |
| **+ Character Arc Drift** | add cross-band character-arc tracking | **Rejected (YAGNI)** — character arcs are per-novel in the current model; cross-band arc tracking is speculative until a use-case materialises. |

### Decision 2 — Read-scope

| Option | Scope | Verdict |
|--------|-------|---------|
| **Full-series scan** | evaluate every band against the series canon/voice in one pass | **Rejected (YAGNI / cost)** — O(bands) LLM cost per check; the natural unit of work is "I just wrote/edited band N, does it still fit?". Full-series batch scan is deferred (Spec §4 YAGNI). |
| **Current-band-vs-series-reference** *(CHOSEN)* | evaluate band N against the series canon + series voice baseline | **Chosen** — O(1) per check; matches the author's mental model ("does *this* book still belong?"). The series voice is the trend baseline (one signal, not a fixed template — per ADR-078's Review Trigger). |

### Decision 3 — Presentation

| Option | Surface | Verdict |
|--------|---------|---------|
| **Separate "Series Drift" tab** | a new tab in the series workspace | **Rejected** — fragments the band-level surface; the Bände-Tab is already where per-band questions live. |
| **Integrated in Bände-Tab** *(CHOSEN)* | a "Check Series Consistency" affordance per band + results panel | **Chosen** — one coherent band-level surface; reuses existing analysis-panel patterns. |

### Decision 4 — Voice drift service shape (implementation)

| Option | Shape | Verdict |
|--------|-------|---------|
| **Extend `AuthorVoiceDriftService`** (plan-literal) | add series-scope branching to the existing per-novel service | **Rejected** — would change the behaviour of the existing `POST /analysis/author-voice-drift/{novel_id}` SSE endpoint for *every* novel in a series (conditional series-voice pull); real regression risk against the 292-test analysis lane. Blurs the novel/series responsibility boundary (RULE-06). |
| **New `SeriesVoiceDriftService`** *(CHOSEN / implemented)* | a separate series-scoped service that **reuses the pipeline** (`compute_author_voice_per_chapter`, `analyse_author_voice_drift`, `resolve_author_voice_drift_prompt`) but sources the reference profile from `SeriesSettings.author_voice` | **Chosen** — zero regression surface (the novel-level service + router + tests are untouched); RULE-06 (separate endpoint → separate service); the *pipeline is reused, not duplicated*. |

---

## Decision

**Voice Drift + Canon-Contradiction · Current-band-vs-series read-scope · Integrated in
Bände-Tab · Separate `SeriesVoiceDriftService` (pipeline reused).**

- **Canon-Contradiction — new `SeriesConsistencyAgent`.** One LLM call per check. Input:
  the series **Canon KB** entries (read via `KBRepository.find_canon_for_series`) + the
  current band's chapter prose. Output: a list of `CanonConflict` (each with the
  `canon_statement`, the `chapter_text_excerpt`, an `explanation`, and a `severity` ∈
  `{error, warning}`). An empty list is a valid, common result (no contradictions). The
  agent mirrors the `BandSummaryAgent` 1-call Output-Function + ADR-035 validator pattern.
  Governed Mode-1 template `analysis/en/series_consistency/system.md`.
- **Series Voice Drift — reuse `AuthorVoiceDriftAgent`.** No new drift agent. The new
  `SeriesVoiceDriftService` computes the band's per-chapter narrator metrics (reusing
  `compute_author_voice_per_chapter`), loads the series voice
  (`SeriesSettings.author_voice` via `SeriesRepository`), and runs the existing
  `analyse_author_voice_drift` with the **series** metrics as the trend baseline. Returns
  the aggregate `AuthorVoiceDriftResponse`. The series voice is treated as **one signal**
  (a trend baseline), not a fixed template — per ADR-078's Review Trigger.
- **Read-scope — current-band-vs-series.** Each check evaluates the *current* band against
  the series references (canon + voice). Full-series batch scan is deferred (Spec §4 YAGNI).
- **Presentation — integrated in Bände-Tab.** A per-band "Check Series Consistency"
  affordance + a results panel (conflicts + drift warnings) reusing existing analysis-panel
  patterns. (Frontend — Task 4 — landed in `ede62081`.)
- **Persistence — stateless (v1).** The v1 check runs the agent and returns the result; it
  persists nothing. A results repository + the `GET …/consistency/{novel_id}` retrieval
  endpoint from the plan are deferred to a follow-up slice.

---

## Rationale

The two-mode choice (Decision 1) reflects what actually breaks in a series. A band that
drifts in *voice* is a stylistic problem (often intentional — an experimental book); a
band that *contradicts the canon* is a factual error (almost never intentional). Detecting
both lets the author distinguish "this book sounds different" from "this book breaks the
rules" — and the two checks naturally live in the same per-band surface.

The current-band read-scope (Decision 2) is the **proportionality** choice. A full-series
scan is O(bands) in LLM cost and answers a question the author rarely asks ("does the
*whole* series still cohere?"); the current-band check is O(1) and answers the question the
author asks constantly ("does *this* book still belong?"). The series voice is used as a
**trend baseline** (one signal among bands), not a fixed template — exactly what ADR-078's
Review Trigger required, and exactly what distinguishes this from a brittle "every band
must match the series voice exactly" model.

The separate `SeriesVoiceDriftService` (Decision 4) is the **root-cause** choice over the
plan's literal "extend" instruction. Extending `AuthorVoiceDriftService` would have
introduced conditional series-voice logic into a service consumed by the standalone novel
endpoint — changing standalone behaviour for series novels and risking the 292-test
analysis lane. A separate series-scoped service keeps the novel/series boundary clean
(RULE-06) while reusing the *pipeline* (`compute_author_voice_per_chapter`,
`analyse_author_voice_drift`, `resolve_author_voice_drift_prompt`). The agent itself is
unchanged — the only difference is the *source* of the reference profile
(`SeriesSettings.author_voice` vs `ProjectSettings.author_voice`).

### Sustainability check

1. **Correct in 3 months?** Yes — Spec 5 (Export) does not touch the drift surface; the
   current-band read-scope + stateless v1 are additive. A future full-series scan or
   persistence layer extends without undoing this work.
2. **Hard-to-undo coupling?** Minimal — one new agent + governed template + two new
   services/routers, all reading existing shared data through repository contracts. No
   schema change in v1 (no persistence).
3. **Simplest correct solution?** Yes — no new drift agent (reuses
   `AuthorVoiceDriftAgent`); no new drift scoring (reuses `author_metric_distances`); the
   only new agent is `SeriesConsistencyAgent`, which has no existing analogue.
4. **Design intent clear?** Yes — `series_consistency_{agent,types,contracts,service,
   schemas,prompt,runtime_content}` and `series_voice_drift_{contracts,service,schemas}`
   each name their single responsibility.

---

## Consequences

**Positive:**

- **Closes ADR-078's Spec-4 Review-Trigger item** — the series-voice profile is read as one
  signal (trend baseline) via the repository contract (no raw column access).
- **Cross-novel consistency now detectable.** A band that contradicts the shared canon is
  caught at check time, not at reader-complaint time.
- **No new drift agent / no new drift scoring.** The series-scope voice drift reuses the
  entire ANAL-009 Phase 2B pipeline; only the reference-profile source differs.
- **Standalone regression untouched.** The novel-level `AuthorVoiceDriftService` + its SSE
  router + the 292-test analysis lane are byte-identical (a regression test
  `TestNovelLevelRegression` asserts the protocol surface is intact).
- **Descriptive/metric boundary preserved.** The series-voice drift reuses
  `author_metric_distances`, which is comparison-only; metrics never reach generation.

**Negative / Tradeoffs:**

- **One new agent** (`SeriesConsistencyAgent`) + one new governed template
  (`series_consistency`) — accepted, standard cost (mirrors `BandSummaryAgent`).
- **Both new endpoints return JSON, not SSE** (matching the design doc's `POST …/check`
  shape and keeping the two series endpoints consistent). The novel-level drift endpoint
  remains SSE. If the frontend needs progressive streaming for series drift, a small
  follow-up adds an SSE variant.
- **Stateless v1 — no persistence.** The `GET …/consistency/{novel_id}` retrieval endpoint
  and a results repository from the plan are deferred to a follow-up slice (see Retrofit-Plan).
- **`route_table.py` reached the hard limit (400/400) — since resolved.** Adding
  `series_consistency` required consolidating a comment; the file has since been modularised
  by extracting `INTENT_TO_CATEGORY` / `INTENT_TO_MODE` into `route_table_intents.py`
  (re-exported from `route_table.py`; the architecture AST checker follows the dicts to the
  new SSOT). Pre-existing debt surfaced by this ADR, now paid down.

**Constraints introduced:**

- Canon-contradiction checks MUST read Canon through `KBRepository.find_canon_for_series`
  (no raw `kb_entries` query) — the ADR-050 "no SSOT bypass" analogue.
- Series-voice drift MUST read `SeriesSettings.author_voice` through `SeriesRepository`
  (no raw column access) — ADR-078's Review-Trigger binding.
- The series voice MUST be treated as a **trend baseline** (one signal), not a fixed
  template every band must match — ADR-078's Review-Trigger binding.
- Standalone novels MUST see no change (the canon check is series-scoped; the voice-drift
  endpoint is series-scoped) — RULE-11 / regression-tested.

---

## CR-04 Cross-Feature Impact (coherence)

The Canon KB and the series voice profile are **shared data** — Canon is written by the KB
editor (Spec 1), the voice profile is written by `SeriesVoiceService` (Spec 3), and both
are read by this spec's checks. CR-04 coherence requires end-to-end consistency:

- **Producer (Canon).** The KB editor + Policy α/iii (ADR-075) write `kb_entries` with
  `novel_id IS NULL` + `series_id` set — unchanged by this ADR.
- **Producer (series voice).** `SeriesVoiceService.profile_from_novel()` (ADR-078) writes
  `SeriesSettings.author_voice` — unchanged by this ADR.
- **Consumer (canon check).** `SeriesConsistencyService.check()` reads Canon via
  `KBRepository.find_canon_for_series` and passes the entries as runtime user-channel
  content (category-3) to `SeriesConsistencyAgent` — mirroring the analysis convention
  (ADR-055 D4). Canon facts never enter the system prompt.
- **Consumer (voice drift).** `SeriesVoiceDriftService.check()` reads
  `SeriesSettings.author_voice` via `SeriesRepository` and uses its `AuthorMetrics` as the
  trend baseline for `author_metric_distances`. Metrics are comparison-only (ADR-055/057
  boundary preserved by construction).

This is the CR-04 lesson (architectural-discipline §7): producer + consumer are defined
together. Because both consumers read through repository contracts and treat the shared
data as input (not as prompt text they assemble), the cross-feature surface is **read-only
and additive** — no existing producer sees a change, and the read path cannot accidentally
bypass the SSOT.

---

## Retrofit-Plan

> Implementation is in progress. This section records what has landed and what remains,
> per architectural-discipline §7 (documented = implemented).

### 1. Inventory of affected paths

**Core (implemented — Task 1):**
- `packages/core/narrare_core/agents/series_consistency_agent.py` — `SeriesConsistencyAgent`
  (NarrareAgent subclass, 1-call Output-Function + ADR-035 validator).
- `packages/core/narrare_core/agents/series_consistency_types.py` — `CanonConflict`,
  `SeriesConsistencyDeps`, `SeriesConsistencyOutput`.
- `packages/core/narrare_core/prompts/_bundled/analysis/en/series_consistency/system.md` —
  governed Mode-1 template.
- `packages/core/narrare_core/prompts/route_table.py` — `series_consistency` added to
  `LLMIntent.ANALYSE` `allowed_context_modes`.
- `scripts/architecture/prompt-surface-manifest.yaml` — `series_consistency` context_mode
  registered under ANALYSE.

**Backend (implemented — Tasks 2–3):**
- `apps/api/narrare/series/series_consistency_contracts.py` —
  `SeriesConsistencyServiceProtocol` (RULE-03).
- `apps/api/narrare/series/series_consistency_service.py` — `SeriesConsistencyService`
  (canon fetch + chapter gather + graceful skip + 1 agent call).
- `apps/api/narrare/series/series_consistency_schemas.py` — request/response DTOs.
- `apps/api/narrare/series/series_consistency_prompt.py` — governed `series_consistency`
  prompt (Mode 1).
- `apps/api/narrare/series/series_consistency_runtime_content.py` — Canon + chapter
  formatting (user channel).
- `apps/api/narrare/series/dependencies_consistency.py` — DI factory.
- `apps/api/narrare/series/router_consistency.py` — `POST /api/v1/series/{id}/consistency/check`.
- `apps/api/narrare/series/series_voice_drift_contracts.py` —
  `SeriesVoiceDriftServiceProtocol`.
- `apps/api/narrare/series/series_voice_drift_service.py` — `SeriesVoiceDriftService`
  (reuses ANAL-009 Phase 2B pipeline; series voice as trend baseline).
- `apps/api/narrare/series/series_voice_drift_schemas.py` — request DTO.
- `apps/api/narrare/series/dependencies_voice_drift.py` — DI factory.
- `apps/api/narrare/series/router_voice_drift.py` —
  `POST /api/v1/series/{id}/voice-drift/check`.
- `apps/api/narrare/_app/main.py` — both routers wired.

**Backend (governance):**
- `scripts/architecture/ai-gate-baseline.json` — +4 intentional empty-KB-var entries for
  `series_consistency_prompt.py` (Canon facts flow as runtime user input, ADR-074 binding).

**Frontend (Task 4 — implemented):**
- Bände-Tab `SeriesDriftPanel` + `SeriesConflictList` + `SeriesDriftSummary` components +
  `useSeriesDrift` / `useSeriesConsistency` TanStack hooks + TS types (RULE-17 parity) +
  API client methods (`packages/web/lib/api/series.ts`).
- ✅ Landed (commit `ede62081`).

**i18n (Task 5 — implemented):**
- `series.drift.*` namespace (en/de/fr parity) in
  `packages/i18n/messages/{en,de,fr}/studio.json` (consolidates the consistency + voice-drift
  UI strings under one namespace, rather than the originally-predicted split namespaces).
- ✅ Landed (commit `ede62081`).

### 2. Migration steps (vertical slices)

1. **Slice 1 — Core Agent (Task 1):** `SeriesConsistencyAgent` + types + governed template
   + route/manifest registration. ✅ Landed.
2. **Slice 2 — Backend Canon-Contradiction (Task 2):** `SeriesConsistencyService` +
   contracts + schemas + prompt + runtime-content + DI + router (`POST …/consistency/check`).
   ✅ Landed (stateless — persistence deferred).
3. **Slice 3 — Backend Voice Drift (Task 3):** `SeriesVoiceDriftService` + contracts +
   schemas + DI + router (`POST …/voice-drift/check`); reuses ANAL-009 Phase 2B pipeline.
   ✅ Landed.
4. **Slice 4 — Frontend (Task 4):** Bände-Tab integration + results panel + hooks + types.
   ✅ Landed (commit `ede62081`).
5. **Slice 5 — i18n (Task 5):** `series.drift.*` (en/de/fr). ✅ Landed (commit `ede62081`).
6. **Slice 6 (deferred follow-up):** results repository + `GET …/consistency/{novel_id}`
   retrieval endpoint (persistence). ⏳ Out of v1 scope.

### 3. Breaking-change assessment

- **No schema change in v1** (stateless — no persistence). → fully backward compatible.
- **Both new endpoints are additive** (`POST /series/{id}/consistency/check` +
  `POST /series/{id}/voice-drift/check`). → no existing endpoint changes.
- **Standalone novels see no change.** The canon check is series-scoped (skips for
  standalones — no series → no Canon); the voice-drift endpoint is series-scoped (404/422
  for a standalone novel). The novel-level `AuthorVoiceDriftService` is byte-identical.
- **One new governed template + one new route-table entry** → prompt-surface governance
  change is additive (manifest + route_table updated together, RULE-22).
- **One new agent** → standard agent-registration path (no new evidence-attribution
  modality).

**Net: fully backward compatible (additive agent + additive endpoints + no schema change).**

### 4. Test update plan

- **Core (Task 1 — landed):** 23 tests — type/data-contract (10) + instantiation/Output
  Function (6) + ADR-035 validator + run (7). Regression: consistency + band-summary +
  routes (87 passed).
- **Backend (Tasks 2–3 — landed):** 34 tests — `test_series_consistency_service.py` (7) +
  `test_series_consistency_service_checks.py` (7, graceful + ownership) +
  `test_router_consistency.py` (4) + `test_series_voice_drift_service.py` (12, incl.
  `TestNovelLevelRegression`) + `test_router_voice_drift.py` (4). Combined series + analysis:
  548 passed. All Fake-based (ADR-030).
- **Frontend (Task 4 — landed):** component + hook + integration tests
  (`SeriesConflictList.test.tsx` + `SeriesDriftPanel.test.tsx` + `SeriesDriftSummary.test.tsx`).
- **Regression:** standalone drift (ANAL-009) + per-novel consistency (CONS-001) lanes green.

---

## Risks Surfaced for Coordinator/User Decision

These are NOT blockers for this ADR; they are acknowledged and mitigated:

1. **Plan deviation (Task 3): new `SeriesVoiceDriftService` instead of extending
   `AuthorVoiceDriftService`.** The plan said "extend"; the implementation created a new
   service (root-cause: standalone regression safety + RULE-06). Flagged for coordinator
   confirmation. Low risk (the pipeline is reused, not duplicated).
2. **JSON vs SSE for the new endpoints.** Both new series endpoints return JSON (not SSE),
   matching the design doc's `POST …/check` shape. The novel-level drift endpoint remains
   SSE. If progressive streaming is wanted for series drift, a follow-up adds an SSE variant.
   Low risk.
3. **Stateless v1 — no persistence.** The `GET …/consistency/{novel_id}` retrieval endpoint
   + results repository from the plan are deferred. Each check re-runs the agent. Acceptable
   for v1 (checks are on-demand, rate-limited); persistence is a follow-up slice. Low risk.
4. **`route_table.py` at the hard limit (400/400) — since resolved.** Pre-existing debt
   surfaced by the `series_consistency` addition; the file has since been modularised
   (`route_table_intents.py`). Low risk for this ADR.
5. **Template is EN-only.** Consistent with all existing analysis templates (band_summary,
   coreference, etc. are EN-only). UI-string i18n (de/fr) is Task 5. Low risk.

No decision required a user call beyond approving the design spec.

---

## RULE-XX Compliance

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-01b | ✅ | `SeriesConsistencyAgent` in `core/agents/`, model from ModelRegistry (injected); series-voice drift **reuses** `AuthorVoiceDriftAgent` (no new drift agent). |
| RULE-02/02b | ✅ | No prompt assembly in services; `series_consistency` is a governed Mode-1 template; the series-voice drift reuses the existing `author_voice_drift` governed template via the standard resolver. Canon facts + chapter prose flow as runtime user-channel content (category-3), never in the system prompt. |
| RULE-03 | ✅ | `SeriesConsistencyServiceProtocol` + `SeriesVoiceDriftServiceProtocol` defined before the services; agent types defined before the agent. |
| RULE-04 | ✅ | Modularised: `series_consistency_{contracts,service,schemas,prompt,runtime_content}.py` + `router_consistency.py` + `dependencies_consistency.py`; `series_voice_drift_{contracts,service,schemas}.py` + `router_voice_drift.py` + `dependencies_voice_drift.py` each own one responsibility. Test files split to satisfy the 200-line limit. |
| RULE-05/06 | ✅ | Core owns the agent + types + governed template; Backend owns the services + routers; one responsibility per file; canon-contradiction and series-voice-drift are two separate service families. |
| RULE-07 | ✅ | `router → service → repository → DB`; Canon read via `KBRepository.find_canon_for_series` (no raw SQL); series-voice read via `SeriesRepository` (no raw column access — the ADR-050 "no SSOT bypass" analogue ADR-078's Review Trigger demanded); Core agent has no `apps/` imports. |
| RULE-11 | ✅ | Empty Canon / empty chapters / missing series voice / voice with no metrics → graceful no-op (canon: empty conflicts; voice-drift: `no_profile`) — no LLM call, no crash; ownership errors are 403 (anti-enumeration). |
| RULE-17 | ✅ | TS mirrors preserve snake_case (Task 4 landed in `ede62081`). |
| RULE-22 / CR-04 | ✅ | Cross-feature coherence: Canon + series voice are shared data read through repository contracts; producer + consumer defined together; the read path is read-only and additive (no producer change); descriptive/metric boundary preserved by construction (`author_metric_distances` is comparison-only). |

---

## Review Trigger

- [x] **Design spec approved** (`docs/superpowers/specs/2026-08-02-series-cross-novel-drift-design.md`).
- [x] **Core (Task 1) implemented** — `SeriesConsistencyAgent` + types + governed template.
- [x] **Backend (Tasks 2–3) implemented** — `SeriesConsistencyService` +
      `SeriesVoiceDriftService` + APIs (stateless v1).
- [x] **Frontend (Task 4) implemented** — Bände-Tab integration + results panel + hooks
      (commit `ede62081`).
- [x] **i18n (Task 5) implemented** — `series.drift.*` (en/de/fr) (commit `ede62081`).
- [ ] When **Spec 5 (Series Export)** is implemented — verify the drift/consistency results
      (once persisted) can feed an export-quality report if desired.
- [ ] If **progressive streaming** is wanted on the series drift/consistency checks — add
      SSE variants (the underlying agent + pipeline are stream-capable).
- [ ] If **full-series batch scan** becomes a use-case — add a batch endpoint that iterates
      the current-band check over all bands (the per-band check is the building block).
- [ ] If **persistence** is needed — add the results repository + the
      `GET …/consistency/{novel_id}` retrieval endpoint (deferred from v1).

---

## Cross-References

- **ADR-075** — Series Foundation (the Series-Canon KB layer this ADR's canon-contradiction
  check reads via `KBRepository.find_canon_for_series`).
- **ADR-078** — Series Voice Hierarchy (the `SeriesSettings.author_voice` profile this ADR's
  series-scope voice drift uses as the trend baseline; this ADR closes its Review-Trigger
  Spec-4 drift item).
- **ADR-077** — Series Generation Context (the `BandSummaryAgent` 1-call pattern
  `SeriesConsistencyAgent` mirrors).
- **ADR-074** — Author Voice Storage (the `AuthorVoiceProfile` shape the series voice
  reuses; the runtime-user-content binding for Canon facts).
- **ADR-073** — Character Voice Drift (the drift-scoring pattern; `author_metric_distances`
  is the prose-level analogue).
- **ADR-044** — Staged Consistency (the per-novel `ConsistencyAgent` this ADR's
  `SeriesConsistencyAgent` is the cross-novel complement of).
- **ADR-055 / ADR-057** — descriptive/metric boundary (preserved by construction in the
  series-voice drift).
- **ADR-050** — Cross-Feature Context Contracts (the "no SSOT bypass" principle the Canon +
  series-voice reads honour).
- `docs/superpowers/specs/2026-08-02-series-cross-novel-drift-design.md` — the design spec.
- `docs/features/series/SERIES-004-cross-novel-drift.md` — the user-facing feature spec.
