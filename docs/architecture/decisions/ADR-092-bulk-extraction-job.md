# ADR-092 — In-Process Bulk KB Extraction Job (SETUP-003 Follow-up F2)

> **Status:** ✅ Accepted (implementation tracked in
> `docs/superpowers/plans/2026-10-03-bulk-extraction.md`)
> **Date:** 2026-10-03
> **Deciders:** Architecture Agent, Project Owner (all ★ recommendations accepted —
> rulings D6a, D7a, D8a, D9a, D10a, D11a FINAL)
> **Related:** ADR-080 (in-process execution boundary — applied), ADR-081 (export
> job registry + polling precedent), ADR-084 (second in-memory registry
> precedent), ADR-085 (apply provenance via `chapter_id`), ADR-091 (import v1 —
> `ImportCommitResponse` is the F2 input), KB-007 (extraction endorse/apply
> contract), ADR-065/RULE-13 (run/stream contract — no streaming surface here)

---

## Context

ADR-091 landed project import: chapters enter the novel via a stateless
preview/commit flow, and `ImportCommitResponse`
(`apps/api/narrare/importing/schemas.py:71-76`) returns the created chapter
ids + titles + word counts. ADR-091 §6 explicitly scoped bulk KB extraction
**out** ("no bulk KB extraction — IO-002 stays separate"). The SETUP-003
follow-up program formalizes it as F2: after importing 20–100 chapters, the
user must be able to run KB extraction over exactly those chapters without
clicking "Extract to KB" once per chapter.

The interactive extraction path is unusable for this at batch scale:

- one chapter = one `ExtractionAgent` call taking 10–30 s
  (`apps/api/narrare/kb/extraction_service.py:122-241`);
- the analysis rate budget defaults to 5 requests/minute
  (`apps/api/narrare/_app/rate_limits.py:161-180`) — 60 chapters ≈ ≥12 min of
  paced calls a browser tab would have to survive;
- results arrive one modal at a time with no cross-chapter progress, cancel,
  or resume.

Everything the job needs already exists and is individually production-proven:
the in-process dispatch + GC-guard + drain pattern (ADR-080; three live users:
`narrare.series.tasks`, `narrare.kb.embedding_hooks`,
`narrare.export.tasks`), the in-memory job registry with owner pinning and
poll endpoints (ADR-081 export: `narrare/export/registry.py`,
`router.py`), the raw non-FastAPI limiter handle (the WebSocket limiter
`AI_WS_LIMITER`, `rate_limits.py:250-279`), and the endorse/apply contract
(KB-007 + ADR-085 provenance).

---

## Decision Drivers

- **ADR-080 boundary** — background work runs in-process via
  `asyncio.create_task`; no queue, no worker, no new datastore.
- **Nothing is written pre-endorsement** — extraction *produces proposals*;
  KB mutation happens only through the explicit apply endpoint (KB-007).
  Therefore a lost job costs spent LLM calls, never data integrity. This is
  the fact that makes an in-memory job acceptable.
- **One rate budget** — a batch that bypassed the analysis limiter would
  let imports starve (or 429) every interactive AI feature; a *separate*
  batch budget would double the operator's effective spend silently. The PO
  ruled: one shared budget (D7a).
- **No new streaming surface** — KB extraction is REST-only today
  (`packages/web/lib/api/extraction.ts:4-5`); job progress must not
  introduce the app's first SSE-for-jobs pattern ad hoc.
- **RULE-03/04/06/07** — contracts first; focused modules; thin routers;
  one-way dependencies.

---

## Options Considered

### Option A — Frontend-driven sequential loop (no new backend)

The FE calls the existing per-chapter endpoint
(`POST /novels/{novel_id}/kb/extract/{chapter_id}`,
`apps/api/narrare/kb/router_extraction.py:60-106`) in a loop with delays.

**Pros:** zero backend work.
**Cons:** pacing lives in the tab (tab close/navigation kills the run); no
server-visible job state, so no honest progress, cancel, or resume; the loop
competes with the user's own requests through 429s surfaced as errors; the
shared budget exists but is invisible to the loop. Rejected — durability and
UX are the actual requirements, not code volume.

### Option B — Persisted job table (durable queue-lite)

A `bulk_extraction_jobs` table with per-chapter state rows; polling reads the
DB; restart resumes automatically.

**Pros:** cross-restart durability.
**Cons:** contradicts the ADR-080 in-process boundary (a queue-shaped table is
a queue); requires an Alembic migration + lifecycle rules for state whose only
value is surviving a restart *of a job whose output is advisory proposals that
write nothing*. The durability gain buys re-starting a job the user can
re-start with one click. Rejected — YAGNI against the actual failure cost.

### Option C — In-process job + in-memory registry + polling (chosen)

An `asyncio.create_task` runner owns per-chapter execution (own DB session per
chapter, real `ExtractionService` construction); an in-memory job registry
(owner-pinned, foreign≡unknown→404) serves start/status/results/cancel/resume
REST endpoints; the FE polls. Direct mirror of the ADR-081 export job
(registered job → runner task → registry state machine → poll endpoint), with
ADR-080's drain flipping a cancelled job to a queryable terminal state.

**Pros:** one process, no migration; every ingredient is an established
in-repo pattern with tests; lost-on-restart degrades to an honest FE
"interrupted" state and a safe re-start.
**Cons:** in-memory only (accepted, see D6a); registry is the app's third
module-local registry (noted below).

---

## Decision

**We choose Option C**, in seven decisions:

1. **D6a — Server-side batch job, in-process pacing.** The runner is an
   `asyncio.create_task` coroutine (ADR-080 application): GC-guarded
   `_INFLIGHT_TASKS` set, registered in `_DRAIN_SOURCES`
   (`apps/api/narrare/_app/inflight.py`) so graceful shutdown cancels +
   awaits it before engine disposal, with the done-callback flipping a
   cancelled job to `cancelled ("cancelled (server shutdown)")` — mirroring
   `narrare/export/tasks.py:188-212`. Pacing happens **between chapters** on
   the server, never in the browser.

2. **In-memory durability trade-off accepted.** The job, its per-chapter
   states, and all outputs live in the process; a restart loses them. A
   poller observes this as 404 and the FE renders an "interrupted" state with
   a restart CTA. Because **nothing is written pre-endorsement** (decision 5),
   the worst case is re-spending LLM calls — there is no partially-written KB
   to reconcile. Restart-safe by construction, not by machinery.

3. **D7a — Shared analysis rate budget via a hoisted raw limiter.** The
   `SelfPruningLimiter` instance behind `AI_ANALYSIS_LIMITER` is hoisted to a
   module-level raw handle (`AI_ANALYSIS_LIMITER_RAW`) and the FastAPI dep
   wraps that same instance; the batch pacer acquires slots on the identical
   bucket between chapters (same shape as the raw `AI_WS_LIMITER` handle,
   `rate_limits.py:250-279`). One budget for interactive + batch;
   `NARRARE_RATE_LIMIT_ANALYSIS` governs both (restart to apply). Batch and
   interactive requests contend — accepted for single-user deployment; the
   pacer always yields the event loop while waiting.

4. **D8a — Polling transport (RULE-13 REST consistency).** Extraction is a
   `run()`-path-only operation — it exposes no `stream()` anywhere (RULE-13
   requires the pair only for streaming-capable operations). Job progress is
   therefore delivered by REST polling (`GET …/status`), not SSE: no new
   streaming surface, consistent with the REST-only extraction client and the
   ADR-081 export job precedent.

5. **No auto-apply — KB-007 endorse/reject contract.** The job stores
   proposals; the KB changes only when the user endorses items through the
   **existing** `POST /novels/{novel_id}/kb/extract/apply`
   (`apps/api/narrare/kb/router_extraction.py:30-57`), passing
   `chapter_id` so ADR-085 provenance (chapter position stamping) applies
   unchanged. The bulk feature adds zero write paths.

6. **Third module-local registry — rule of three noted, no premature
   generalization.** In-memory registries: export jobs (ADR-081), WS tickets
   (ADR-084), now bulk-extraction jobs. Three ad-hoc implementations of the
   same idea (dict + owner field + TTL sweep + foreign≡unknown) is the point
   at which a shared abstraction *becomes* a candidate — it is deliberately
   **not** extracted now (the three differ meaningfully: token consumption vs.
   artifact TTL vs. per-chapter state). The fourth registry triggers the
   generalization review (see Review Triggers).

7. **Module home: `apps/api/narrare/kb/bulk_extraction/`** — a vertical
   sub-package (`contracts`, `schemas`, `registry`, `pacer`, `runner`,
   `service`, `router`, `dependencies`), mirroring the
   `kb/entity_resolution/` precedent (ADR-085) instead of growing the already
   60+ flat `kb/` directory. Router mounts under the existing novel-scoped KB
   tag; dependency direction is router → service → runner/registry → repos →
   DB, with the runner the only component that opens its own sessions.

---

## Rationale

Root cause chain (2× why):

1. **Symptom:** import creates dozens of chapters but the KB stays empty;
   filling it requires one guarded modal click per chapter.
2. **Why?** Extraction exists only as a synchronous per-request operation;
   there is no batch execution context.
3. **Why?** ADR-080 (correctly) removed the queue substrate, and nothing has
   needed a batch context since — so none was built on the new boundary.
4. **Design:** build the batch context as a direct application of the
   boundary's own patterns (export job, series task, drain) rather than
   re-introducing infrastructure. The only genuinely new composition is the
   shared pacer (decision 3) — required so the batch cannot exempt itself
   from the budget every interactive feature obeys.

Simplest *correct* solution: Option A is simpler but not correct (no honest
job semantics); Option B is more durable than the problem warrants and
violates the boundary. C composes proven parts.

---

## Consequences

**Positive:**

- Import → extraction becomes one continuous flow at any chapter count.
- The analysis budget finally has a single owner for interactive and batch
  traffic; operators tune one knob (`NARRARE_RATE_LIMIT_ANALYSIS`).
- Honest progress (per-chapter states + item counts), cooperative cancel,
  and in-memory resume (D11a) with zero migrations.
- The export-job pattern gets a second consumer, de-risking its shape.

**Negative / Trade-offs:**

- Jobs lost on restart (accepted — decision 2; FE degrade state).
- Registry is process-local: no cross-restart resume, no cross-process
  visibility (single-user: irrelevant).
- Batch + interactive contend for the same 5/min default budget — a running
  pass makes interactive 429s more likely; operator-mitigable via env var;
  documented in the estimate surface (cost transparency).
- Third duplicated registry shape (deliberate; see decision 6).

**Constraints touched:** RULE-03 (contracts before runner/service), RULE-04
(sub-package split; file limits), RULE-05/06/07 (one-way deps; thin router;
runner builds own sessions via `get_session_factory()`), RULE-08 (no new
dependency — pacer uses the existing pyrate limiter), RULE-10 (per-task test
files in the same task), RULE-11 (every failure flips a queryable job/chapter
state; drain cancellation logged + typed), RULE-12 (novel-scoped REST surface),
RULE-16/17 (TS mirror + i18n in first-use tasks), RULE-18b (no new settings
surface — the operator env var already exists), RULE-20 (each task ships
complete behavior), RULE-22 (provenance flows through the existing apply
path), RULE-23 (no type ignores).

---

## Sustainability Check

1. **Correct in 3 months?** Yes — as long as single-user in-process deployment
   holds (ADR-029/080). Every ingredient is already load-bearing elsewhere.
2. **Hard-to-undo coupling?** None added; the registry + pacer are swappable
   seams if ADR-080 is ever superseded for multi-worker.
3. **Simplest correct solution?** Yes (see Rationale).
4. **Intent clear?** This ADR + the F2 spec
   (`docs/superpowers/specs/2026-10-03-bulk-extraction-design.md`) record the
   durability, budget, and transport decisions explicitly.

---

## Implementation Notes

- **Binding spec:** `docs/superpowers/specs/2026-10-03-bulk-extraction-design.md`
  (wire shapes, per-chapter state machine, registry semantics, FE surfaces).
- **Plan:** `docs/superpowers/plans/2026-10-03-bulk-extraction.md` (T1–T9).
- **Pacer short-circuit:** test/E2E mode (`CoreSettings.e2e_test`) must skip
  pacing, mirroring the dep's short-circuit in
  `apps/api/narrare/_app/rate_limiter_dep.py:170-174`.
- **Background owner resolution:** the runner has no request context; resolve
  the novel's owner from the DB like `series/tasks.py:88-99` and wire
  `LazyModelResolution(LLMIntent.KB_EXTRACT, owner, novel_id)` exactly as
  `kb/dependencies_extraction.py:74-77` does.
- **Single active job per novel:** `start` returns 409 while a job for the
  same novel is `pending|running|cancelling` (accidental double-spend guard).
- **F3 relationship:** IO-002's corpus analysis pass (re-scoped 2026-10-03)
  builds on this engine; its product rulings live in the IO-002 feature doc
  and `docs/superpowers/specs/2026-10-03-io002-corpus-pass-design.md`.

**ADR Implementation Completeness Gate (Gate 12):** flip to "✅ Implemented"
in `INDEX.md` only when T1–T9 are done — engine, endpoints, FE surfaces, docs
closure — and no plan task is skipped.

---

## Review Trigger

- [ ] Narrare moves to multi-user/multi-worker deployment → re-evaluate via
      the ADR-080 re-introduction path (broker/worker) before scaling this job.
- [ ] A **fourth** module-local in-memory registry is proposed → generalize
      the registry shape (owner pinning + foreign≡unknown + TTL sweep) into
      one tested abstraction; retrofit the three existing.
- [ ] Batch-vs-interactive contention produces real user complaints → revisit
      a separate operator-tunable batch budget (own `NARRARE_RATE_LIMIT_*`
      var; still one limiter pattern).
- [ ] Job outputs ever need to outlive the process (e.g. deferred review
      across restarts) → new ADR; do not quietly persist the registry.
