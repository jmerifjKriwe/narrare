# Bulk KB Extraction over Imported Chapters — F2 (SETUP-003 follow-up) — Design Spec

> **Status:** Approved design record (2026-10-03) — formalizes the F2 design
> exploration; all project-owner rulings are FINAL (D6a, D7a, D8a, D9a, D10a,
> D11a — every ★ recommendation accepted).
> **ADR:** `docs/architecture/decisions/ADR-092-bulk-extraction-job.md`
> **Plan:** `docs/superpowers/plans/2026-10-03-bulk-extraction.md`
> **F3 sibling (IO-002 corpus pass):**
> `docs/superpowers/specs/2026-10-03-io002-corpus-pass-design.md`
> **Language of record:** English (project standard)

---

## §1 Scope

**In scope (F2):**

- A server-side **bulk extraction job**: run the existing
  `ExtractionService.extract_from_chapter` over an explicit list of chapter
  ids (the F2 input is the `ImportCommitResponse.chapters` list
  `apps/api/narrare/importing/schemas.py:64-76` — unchanged by F1).
- Job lifecycle endpoints: **start / status / results / cancel / resume**
  (REST + polling; no SSE).
- A **shared analysis rate pacer**: one budget for interactive + batch calls.
- FE surfaces: **post-commit CTA** (import-modal success card + wizard
  sessionStorage suggestion flag) and a **BulkExtractionPanel** (progress,
  review reusing the existing extraction review components, apply reusing the
  existing apply endpoint, next-unreviewed walking).
- **In-memory resume**: cancelled/failed jobs can be resumed within the
  process lifetime; done outputs are retained.

**Explicitly out of scope (F2):**

- Novel-wide "corpus pass" semantics, caps, estimates, and the ADR-085 dedup
  gate — that is F3 / IO-002 (§ of the corpus-pass spec).
- Any KB write path other than the existing apply endpoint (no auto-apply).
- Persistence of jobs or outputs (no migration; registry is in-memory).
- Cross-chapter chunking or re-chunking — one chapter = one agent call.
- DOCX, folder upload, structure detection, reference documents (ADR-091 /
  IO-002 rulings unchanged).

---

## §2 Decision table (binding)

| # | Decision | Choice |
|---|----------|--------|
| D6 | Execution substrate | **D6a**: server-side batch job as an in-process `asyncio.create_task` (ADR-080 application). In-memory durability trade-off **accepted**: job lost on restart; **nothing is written pre-endorsement**, so a lost job costs only spent AI calls |
| D7 | Rate budget | **D7a**: shared budget — hoist the raw `SelfPruningLimiter` behind `AI_ANALYSIS_LIMITER` to a module-level handle; the batch pacer acquires slots on the same bucket between chapters. Operator env `NARRARE_RATE_LIMIT_ANALYSIS` governs both (restart to apply) |
| D8 | Progress transport | **D8a**: polling (REST). KB extraction is a `run()`-only operation (no `stream()` exists — RULE-13 requires the pair only for streaming-capable ops), so job status stays REST; no SSE surface is introduced |
| D9 | Discovery after import | **D9a**: post-commit CTA — import-modal **success card** with cost transparency + a wizard-side `sessionStorage` suggestion flag `narrare:importSuggestExtract:{novel_id}` mirroring the `narrare:importFailed:{novel_id}` lifecycle |
| D10 | Review UX | **D10a**: dedicated `BulkExtractionPanel` **reusing** the existing extraction review components (`ExtractionReview`, `ExtractionItemCard`, selection hook) and the **existing apply endpoint** (`POST /novels/{novel_id}/kb/extract/apply`) |
| D11 | Resume semantics | **D11a**: in-memory resume — resume re-dispatches the runner over chapters in state `pending` or `failed`; `done` outputs and the job id are retained. No cross-restart resume (poll-404 → FE "interrupted" degrade) |

---

## §3 Module boundary

```
apps/api/narrare/kb/bulk_extraction/          ← NEW sub-package (kb/entity_resolution precedent)
    contracts.py      Protocols FIRST (RULE-03): BulkExtractionJobStore,
                      BulkExtractionDispatcher, BulkChapterReader,
                      BulkExtractionPacer
    schemas.py        Pydantic request/response models (RULE-17 mirror target)
    registry.py       in-memory job records: owner pinning, per-chapter
                      states, cancel flag, resume reset, TTL sweep
    pacer.py          shared-budget acquire (hoisted raw limiter)
    runner.py         asyncio.create_task loop + _INFLIGHT_TASKS GC guard
                      (registered in _app/inflight._DRAIN_SOURCES)
    service.py        start/status/results/cancel/resume orchestration
                      (ownership gate, id∈novel validation, single-active-job)
    router.py         thin novel-scoped routes (RULE-06/12)
    dependencies.py   DI factories (SessionDep-based, RULE-19)

apps/api/narrare/_app/rate_limits.py          MOD  hoist AI_ANALYSIS_LIMITER_RAW
                                                   (dep wraps the SAME instance)
apps/api/narrare/_app/inflight.py             MOD  + drain source entry
apps/api/narrare/kb/router.py or _app router mount
                                               MOD  include bulk router (tags kb-extraction)

packages/web/
    types/bulkExtraction.ts                    NEW  RULE-17 mirror
    lib/api/bulkExtraction.ts                  NEW  api client (start/status/
                                                   results/cancel/resume + poll)
    lib/api/extraction.ts                      MOD  applyExtraction gains optional
                                                   chapterId (provenance, ADR-085)
    components/studio/extraction/
        BulkExtractionPanel.tsx                NEW  progress + review + walking
    components/studio/importing/
        ImportModal.tsx                        MOD  success card CTA (D9a)
    components/studio/wizard/useWizardCompletion.ts
                                               MOD  set suggestion flag on success
    components/studio/SidebarChapterList.tsx   MOD  read suggestion flag → CTA card
        (+ components/studio/importing/ImportSuggestExtractBanner.tsx NEW)
packages/i18n/messages/{en,de,fr}/             MOD  importing.json / studio.json /
                                                   wizard.json keys (RULE-16,
                                                   same task as first use)
```

**Dependency direction (one-way, RULE-07):**

```
router → service → registry / runner / pacer → (runner) ExtractionService → repos → DB
                                   ↓
                       narrare._app.rate_limits (raw limiter handle)
                       narrare._app.database.get_session_factory
```

The runner is the **only** component that opens its own sessions (never the
request session). No DB migration. No new dependency.

---

## §4 Wire contracts (exact shapes)

All routes novel-scoped under `/api/v1/novels/{novel_id}/kb/extract/bulk`,
tag `kb-extraction`, auth-mandatory. Errors keep the app-level shapes:
`NotFoundError` → 404 (foreign novel **and** foreign/unknown job —
foreign≡unknown), `narrare_core.shared.errors.ValidationError` → 422,
active-job conflict → 409. Schemas use `ConfigDict(extra="forbid")`.

### 4.1 `POST …/kb/extract/bulk` — start (201)

Request:

```json
{ "chapter_ids": ["<uuid>", "<uuid>"] }
```

- `chapter_ids`: 1..`BULK_EXTRACT_MAX_CHAPTERS` (200) items; duplicates and
  ids not belonging to `novel_id` → 422 naming the offending id; the job's
  chapter order = chapter `position` order (server-sorted, not request order).

Response `BulkExtractionJobView` (201):

```json
{
  "job_id": "<token_urlsafe(16)>",
  "novel_id": "<uuid>",
  "status": "pending",            // pending | running | cancelling | completed | cancelled | failed
  "created_at": "…", "updated_at": "…",
  "totals": { "total": 42, "done": 0, "failed": 0, "remaining": 42 },
  "error": null
}
```

- 409 while another job for the same novel is
  `pending|running|cancelling` (single active job per novel).
- The start response does **not** echo the chapter list (status does).

### 4.2 `GET …/kb/extract/bulk/{job_id}/status` — poll (200)

```json
{
  "job_id": "…", "novel_id": "…",
  "status": "running",
  "created_at": "…", "updated_at": "…",
  "totals": { "total": 42, "done": 17, "failed": 1, "remaining": 24 },
  "chapters": [
    { "chapter_id": "<uuid>", "title": "Storm", "position": 12,
      "state": "done",     "item_count": 9 },
    { "chapter_id": "<uuid>", "title": "Aftermath", "position": 13,
      "state": "running",  "item_count": null },
    { "chapter_id": "<uuid>", "title": "Coda", "position": 14,
      "state": "pending",  "item_count": null }
  ],
  "error": null
}
```

- Per-chapter `state ∈ pending | running | done | failed` (normative set).
- `item_count` is set (≥ 0) **iff** `state = done` — item counts live in
  status, full items live in results (payload-size boundary).
- `totals.remaining` = `pending + running` counts.
- 404 for unknown **and** foreign jobs (owner pinning, §6).

### 4.3 `GET …/kb/extract/bulk/{job_id}/results` — full outputs (200)

```json
{
  "job_id": "…", "novel_id": "…", "status": "completed",
  "chapters": [
    { "chapter_id": "<uuid>", "title": "Storm", "position": 12, "state": "done",
      "output": {
        "results": [ { "item_type": "new_entity", "name": "Elena", "…": "… (ExtractionItem verbatim)" } ],
        "analysis_notes": "…"
      } },
    { "chapter_id": "<uuid>", "title": "Coda", "position": 14, "state": "failed",
      "output": null }
  ]
}
```

- `output` is the **full `ExtractionOutput`**
  (`packages/core/narrare_core/agents/extraction_types.py:46-55` —
  `results: list[ExtractionItem]`, `analysis_notes: str`) and is present
  **iff** `state = done`; otherwise `null`. Available in any job state
  (partial results of a cancelled job are readable — they are the resume
  baseline and the reviewable set).

### 4.4 `POST …/kb/extract/bulk/{job_id}/cancel` (200)

Sets the cooperative cancel flag. The in-flight chapter **completes** and is
recorded (`done`/`failed`); the loop then stops; the job flips to
`cancelled`; remaining chapters stay `pending`. Response: the job view with
`status: "cancelling"` (transition observed via polling) — calling cancel on
a terminal job is a 409.

### 4.5 `POST …/kb/extract/bulk/{job_id}/resume` (200, D11a)

Allowed only when `status ∈ cancelled | failed`. Chapters in state
`pending` **or** `failed` are reset to `pending`; `done` outputs and
`item_count`s are retained; a new runner task is dispatched on the same
`job_id`. 409 while `pending|running|cancelling|completed`. Response: job
view with `status: "pending"`.

> **Amendment (2026-10-04, post-implementation — the shipped
> `reset_for_resume` is correct and broader than the letter above; the
> original text is retained as the design record):** resume re-pends
> **every** non-`done` chapter — including rows stranded in `running` by the
> graceful-shutdown drain (a drain-cancelled job can carry `running` rows;
> leaving them out of the reset would silently drop them from the runner's
> `pending_chapter_ids` worklist) — and clears each re-pended row's stale
> `error` (a re-pended row must not carry a failure reason from the previous
> attempt). It also clears the job-level `error`, the `cancel_requested`
> flag (a resumed job must not immediately re-cancel itself), and the
> `expires_hint` sweep hint (the job is non-terminal again, so the TTL sweep
> must not collect it mid-run). `done` outputs and `item_count`s are
> retained unchanged. Implementation:
> `apps/api/narrare/kb/bulk_extraction/registry.py::reset_for_resume`;
> pinned by `tests/unit/api/kb/bulk_extraction/test_registry.py` and
> `test_registry_sweep.py::test_resumed_job_is_withdrawn_from_sweep`.

### 4.6 Validation rules (normative)

1. `chapter_ids` non-empty, ≤ 200, no duplicates (422, names the id).
2. Every id must resolve to a chapter of `novel_id` (422, names the id) —
   checked via `ChapterRepository.list_by_novel`
   (`apps/api/narrare/chapters/repository.py:36-42`).
3. Ownership gate first, always: `verify_novel_owned`
   (`apps/api/narrare/kb/_novel_gate.py`, used at
   `kb/extraction_service.py:150`) — foreign novel ≡ unknown novel → 404.
4. One active job per novel (409) — see §6.
5. Unknown/foreign `job_id` → 404 with the same message shape as the export
   registry (`apps/api/narrare/export/registry.py:145-155`).

---

## §5 Service loop (runner semantics)

The runner (`kb/bulk_extraction/runner.py`) mirrors
`apps/api/narrare/export/tasks.py` and `apps/api/narrare/series/tasks.py`:

```
for each job chapter in position order:
    if registry.cancel_requested(job_id):        # cooperative check BETWEEN chapters
        mark remaining pending chapters; job → cancelled; return
    await pacer.acquire()                        # shared budget, §7 (yields the loop)
    async with session_factory() as session:     # OWN session per chapter
        service = build_extraction_service(session, novel_owner_id, novel_id)
        mark chapter running
        try:
            output = await service.extract_from_chapter(novel_id, chapter_id, owner_id)
            record output; chapter → done (item_count = len(output.results))
        except ConfigurationError:               # unconfigured provider — fast-fail
            job → failed(error); return          # no point burning N−1 more calls
        except Exception as exc:                 # per-chapter isolation
            chapter → failed(str(exc)); continue # job continues
mark job completed
```

Binding details:

- **Real service construction** — the runner builds a genuine
  `ExtractionService` exactly as `kb/dependencies_extraction.py:31-98` wires
  it (registry, `LazyModelResolution(LLMIntent.KB_EXTRACT, owner, novel_id)`,
  Chapter/KB/Novel repos, composer, run-limit resolver). No request context
  exists: the owner is read from the novel like
  `apps/api/narrare/series/tasks.py:88-99`. No apply deps are needed
  (extraction only; apply stays a request-path concern).
- **Pacing between chapters** — exactly one pacer acquire per chapter = one
  agent call per acquired slot; the in-flight `agent.run` is never aborted by
  the pacer.
- **Cooperative cancel** — checked between chapters; cancel never interrupts
  an in-flight agent call (a spent call's output is always recorded).
- **Cancellation by drain** — graceful shutdown cancels the task
  (`_DRAIN_SOURCES` entry); `CancelledError` propagates past the runner's
  `except Exception`; the done-callback marks the job
  `cancelled("cancelled (server shutdown)")` — mirroring
  `apps/api/narrare/export/tasks.py:188-212`. A poller sees a terminal state,
  never a hang (RULE-11).
- **Session hygiene** — one session per chapter, closed after the chapter;
  single concurrent session for the whole job.

---

## §6 Registry semantics

`kb/bulk_extraction/registry.py` mirrors
`apps/api/narrare/export/registry.py` (ADR-092 decision 6 — third
module-local registry; no shared abstraction yet):

- `_JOBS: dict[str, _BulkJobRecord]` — process-local; every mutation is
  synchronous (no await between read and write — safe under the single
  asyncio loop; same argument as `export/registry.py:114-118`).
- `_BulkJobRecord`: public job view + `owner_user_id` (pinned at create,
  **after** the ownership gate — trustworthy by construction, mirroring
  `export/registry.py:126-142`), ordered chapter-state list, outputs dict
  (`done` chapters only), `cancel_requested` flag.
- **Owner pinning / foreign≡unknown:** `get`/`cancel`/`resume`/status
  read-paths take `user_id`; an owner mismatch raises the same
  `NotFoundError` as an unknown id (anti-enumeration; mirrors
  `export/registry.py:145-155` and `router_extraction.py`'s 404 rationale).
  Runner-time `mark_*` mutations stay job-id-keyed (they only run for jobs
  the gate admitted).
- **GC guard:** the runner task lives in `runner._INFLIGHT_TASKS` with a
  done-callback discard (pattern:
  `apps/api/narrare/series/tasks.py:36-53`); the registry is data, not a
  task — it is *not* drained, the drained runner flips its job to a terminal
  state (same split as export: `export/registry.py:6-13`).
- **TTL sweep:** terminal jobs (`completed|cancelled|failed`) are swept after
  `BULK_JOB_TTL` (24 h) by `sweep_expired()`, hooked into the same lifespan
  periodic-cleanup loop that calls the export registry's sweep. Nothing is
  lost but re-runnable proposals (ADR-092 decision 2).
- **Single active job per novel:** `find_active_for_novel()` scan; enforced
  in `service.start` (409).

---

## §7 Shared rate budget (D7a — the hoisted raw limiter pacer)

Today `AI_ANALYSIS_LIMITER` is a `_RateLimiterDep` wrapping its own
`SelfPruningLimiter` (`apps/api/narrare/_app/rate_limits.py:164-180`). The
WebSocket limiter already demonstrates the **raw** (non-dep) handle shape
(`rate_limits.py:250-279`, `AI_WS_LIMITER`, used with
`try_acquire(key, blocking=False)` inside a handler).

Change (additive, behavior-preserving for the dep path):

```python
# apps/api/narrare/_app/rate_limits.py
ANALYSIS_RATE: Final[Rate] = Rate(
    _resolve_rate_limit_count(RATE_LIMIT_ANALYSIS_ENV_VAR, RATE_LIMIT_ANALYSIS_DEFAULT),
    LONG_WINDOW_MS,
)
#: Raw handle — the ONE analysis bucket. The FastAPI dep and the in-process
#: bulk pacer acquire on this same instance (shared budget, ADR-092 D7a).
AI_ANALYSIS_LIMITER_RAW: Final[SelfPruningLimiter] = SelfPruningLimiter(ANALYSIS_RATE)
AI_ANALYSIS_LIMITER: Final[_RateLimiterDep] = _RateLimiterDep(AI_ANALYSIS_LIMITER_RAW)
```

Pacer (`kb/bulk_extraction/pacer.py`):

```python
PACER_POLL_SECONDS: Final[float] = 1.0

async def acquire_analysis_pacer_slot(
    key: str = "kb-bulk-extraction",
    limiter: SelfPruningLimiter | None = None,   # test injection seam
) -> None:
    """Cooperatively block until one shared-analysis-budget slot is acquired."""
```

- Non-blocking `try_acquire_async(key, blocking=False)` + `asyncio.sleep`
  retry loop — never blocks the event loop (a blocking acquire would stall
  every request for up to a rate window).
- E2E/test short-circuit: `get_core_settings().e2e_test` → acquire
  immediately, mirroring the dep short-circuit at
  `apps/api/narrare/_app/rate_limiter_dep.py:170-174`.
- Key is informational (single shared bucket —
  `rate_limiter_dep.py:194-203`); isolation comes from separate limiter
  instances, and there is deliberately only **one** analysis instance.
- Consequence (accepted, documented): while a pass runs, interactive
  analysis calls see the same bucket and may 429. The FE estimate surface
  states the pacing honestly (§8.1).

---

## §8 Frontend surfaces

### 8.1 Post-commit CTA (D9a) — cost transparency

**Import modal success card** — `ImportModal.tsx` currently closes the dialog
after `importApi.commit` succeeds (`packages/web/components/studio/importing/ImportModal.tsx:29-46`).
F2 replaces the immediate close with a success card (same AlertDialog):

```
✓ N chapters imported
  N chapters · M words · N AI calls        ← cost transparency line
[ Extract to Knowledge Base ]  [ Not now ]
```

- `N` = `response.chapters.length`, `M` = `Σ chapter.word_count` — both from
  the `ImportCommitResponse` (`apps/api/narrare/importing/schemas.py:64-76`;
  FE type `packages/web/types/importing.ts`, client
  `packages/web/lib/api/importing.ts:20-26`). AI calls = N (one agent call
  per chapter).
- A pacing note ("runs in the background at your analysis rate") sits under
  the buttons.
- **Extract to KB** → opens `BulkExtractionPanel` seeded with
  `response.chapters.map(c => c.id)`; **Not now** → close (unchanged
  invalidation flow).
- The modal still clears `narrare:importFailed:{novelId}` on success
  (`ImportModal.tsx:37`) — unchanged.

**Wizard suggestion flag** — `useWizardCompletion` sets
`narrare:importFailed:{novel_id}` on commit failure
(`packages/web/components/studio/wizard/useWizardCompletion.ts:34-44`). F2
mirrors the lifecycle for success:

```ts
sessionStorage.setItem(
  `narrare:importSuggestExtract:${result.novel_id}`,
  JSON.stringify(chapterIds),      // self-contained: the CTA needs no extra fetch
);
```

`SidebarChapterList` (which already reads/re-evaluates/clears the failed flag
at `packages/web/components/studio/SidebarChapterList.tsx:89-98,161-171,182-196`)
renders a sibling suggestion card (`ImportSuggestExtractBanner`):
"Analyze your imported chapters" → opens `BulkExtractionPanel` with the
stored ids → flag removed on start or dismiss (same two-way clearing as the
failed banner). The flag is a **suggestion** (not an error banner): neutral
tone, one dismiss.

### 8.2 BulkExtractionPanel (D10a — reuse-first)

New `packages/web/components/studio/extraction/BulkExtractionPanel.tsx` — a
modal panel in the visual family of `ExtractionPanel`
(`packages/web/components/studio/extraction/ExtractionPanel.tsx:23-102`).

**Progress mode** (job `pending|running|cancelling`):

- Poll `GET …/status` every 3 s (TanStack Query `refetchInterval`, stops on
  terminal state); render totals + per-chapter state chips
  (`pending|running|done|failed` from status `chapters[]`, titles included).
- `Cancel` → `POST …/cancel`; the button then shows "cancelling…" until the
  poll observes `cancelled` (the in-flight chapter finishes first — §5).
- **Interrupted degrade:** status poll → 404 (job lost on restart) ⇒ switch
  to an "interrupted" state: explanation + "Start over" CTA. Safe because
  nothing was written pre-endorsement — any already-applied chapters stay
  applied (apply is per-item idempotent from the user's perspective:
  re-extraction proposes again; endorsement is always explicit).

**Review mode** (job terminal or user opens results mid-run):

- Chapter rail ordered by position; each done chapter shows
  `title · item_count`. **Next-unreviewed walking:** the panel tracks
  reviewed/applied chapter ids in local state; "Next chapter" advances to
  the next `done` chapter without an applied/skipped marker; the rail badges
  applied (✓) and skipped (–) chapters.
- Per chapter, the review body **reuses the existing components verbatim**:
  `ExtractionReview` (`packages/web/components/studio/extraction/ExtractionReview.tsx:16-32`
  — items, `selectedIndices`, toggle/selectAll/selectNone, analysisNotes)
  with `ExtractionItemCard` underneath; selection state via the
  `useExtractionSelection` pattern (`packages/web/lib/hooks/useExtractionSelection.ts`).
- **Apply** per chapter via the **existing** endpoint and hook
  (`useApplyExtraction`, `packages/web/lib/hooks/useExtraction.ts:88-126`).
  F2 extends `extractionApi.applyExtraction`
  (`packages/web/lib/api/extraction.ts:69-74`) with an optional
  `chapterId` so the request body carries `chapter_id` — ADR-085 provenance
  stamps the chapter position (`apps/api/narrare/kb/schemas_extraction.py:57-74`
  already accepts it; purely additive, old callers unchanged).
- **Resume** button when `status ∈ cancelled|failed` (§4.5) — re-polls after
  200; done outputs stay reviewable across the resume.

### 8.3 Version skew

FE+BE ship in one image. Residual windows follow the Q-012 precedent (no
shims): an old server yields 404 on the bulk routes → the CTA surfaces the
generic error path; a new server with an old FE is unreachable (no FE entry
points exist).

---

## §9 Failure & resume matrix

| Event | Job state | Chapters | FE behavior | Data impact |
|---|---|---|---|---|
| Chapter LLM/validation error | running | one `failed` (+reason) | red chip, item_count stays null; job continues | none (proposals only) |
| Unconfigured provider (`ConfigurationError`) | `failed` fast | processed-so-far kept | error card + "Configure a provider" | none |
| User cancel | `cancelling` → `cancelled` | in-flight chapter recorded; rest `pending` | cancel button → terminal banner; **Resume** offered | none |
| API restart mid-run (drain) | `cancelled ("cancelled (server shutdown)")` | recorded until the cut | next poll → terminal banner; Resume 404s after registry loss | none |
| API restart (hard) | registry gone | — | status 404 → **interrupted** state + restart CTA | none — nothing written pre-endorsement |
| Resume (`cancelled|failed`) | → `pending` → running | `pending`+`failed` reset to pending; `done` retained | panel re-enters progress mode | none |
| Re-run after interrupted | new job id | fresh | new start (user re-confirms cost) | duplicates only if the old run's items were applied AND re-endorsed — endorsement is explicit each time |

---

## §10 Test strategy

| Layer | File | Covers |
|---|---|---|
| API unit | `tests/unit/api/kb/bulk_extraction/test_schemas.py` | extra=forbid; state enums; view invariants (item_count iff done) |
| API unit | `tests/unit/api/kb/bulk_extraction/test_registry.py` | owner pinning (foreign≡unknown→404); mark_* transitions; cancel flag; resume reset (pending+failed→pending, done kept); sweep; single-active scan |
| API unit | `tests/unit/api/kb/bulk_extraction/test_pacer.py` | shared-instance identity (`AI_ANALYSIS_LIMITER.limiter is AI_ANALYSIS_LIMITER_RAW`); acquire-then-sleep loop with fake limiter; e2e short-circuit |
| API unit | `tests/unit/api/kb/bulk_extraction/test_runner.py` | state walk pending→running→done; failure isolation; fast-fail ConfigurationError; cooperative cancel between chapters; CancelledError → shutdown-cancelled; own-session + real-service factory seam (fakes) |
| API unit | `tests/unit/api/kb/bulk_extraction/test_service.py` | start validation (dups, foreign ids, cap, position ordering, 409 active); status counts; results shapes; cancel/resume guards |
| API integration | `tests/integration/kb/test_bulk_extraction_api.py` | start→status→results→cancel→resume over the real router (fake agent runner seam); 404 foreign novel/job |
| FE unit | `packages/web/lib/api/bulkExtraction.test.ts` | client paths; RULE-17 mirror parity; poll-stop on terminal |
| FE unit | `BulkExtractionPanel.test.tsx` | progress rendering; cancel flow; interrupted degrade on 404; review reuses ExtractionReview; apply sends `chapter_id`; next-unreviewed walking; resume |
| FE unit | `ImportModal.test.tsx` / `SidebarChapterList.test.tsx` / wizard tests | success card counts (N·M·N); suggestion flag set/clear lifecycle; CTA opens panel with stored ids |

Coverage per RULE-10 (Core n/a — no Core changes; API ≥ 80 %). Every new
service-ish file lands with its unit test file **in the same task** (the F1
RULE-10 lesson), verified by
`python scripts/check_test_coverage_gaps.py` per task.

---

## §11 Risks & assumptions

| # | Risk | Mitigation / status |
|---|------|---------------------|
| R1 | Batch starves interactive analysis (shared 5/min bucket) | D7a ruling (accepted, single-user); operator raises `NARRARE_RATE_LIMIT_ANALYSIS`; estimate surface states pacing honestly |
| R2 | Long-running asyncio task GC'd mid-flight | `_INFLIGHT_TASKS` strong refs + done-callback (proven pattern: `series/tasks.py:36-53`) |
| R3 | Registry growth unbounded | TTL sweep (24 h terminal jobs) in the lifespan periodic loop |
| R4 | User closes the tab mid-run | The job keeps running server-side, but the `job_id` lives in FE memory only — a tab loss ends *observation*, not the job. Re-entry is a fresh start (chapter ids, not job ids, are persisted in the CTA flag for exactly this reason). Accepted: worst case is re-spent AI calls on chapters the user already applied; endorsement is always explicit, so re-extraction can only propose again |
| R5 | Per-chapter `ExtractionService` construction cost (composer, repos) per chapter | Negligible vs a 10–30 s agent call; keeps sessions bounded (one at a time) |
| R6 | 200-chapter cap vs F1's 100-file guardrail drift | Cap is a protocol constant (like v1 guardrails), 422 names the count; F3's product cap is stricter (120) and layered above |

**Assumption ratified:** `BULK_EXTRACT_MAX_CHAPTERS = 200` and
`BULK_JOB_TTL = 24 h` are protocol constants — no settings surface (RULE-18b:
no new configurable values), pinned by regression tests.
