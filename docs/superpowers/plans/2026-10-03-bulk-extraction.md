# Bulk KB Extraction Job (F2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the ADR-092 bulk extraction job — a server-side, paced, in-process batch run of the existing `ExtractionService` over an explicit chapter-id list, with start/status/results/cancel/resume REST endpoints and the two post-import FE call-to-action surfaces.

**Architecture:** New sub-package `apps/api/narrare/kb/bulk_extraction/` (contracts → schemas → registry → pacer → runner → service → router → dependencies) mirroring the ADR-081 export-job shape (in-memory owner-pinned registry + `asyncio.create_task` runner + poll endpoints) and the ADR-080 in-process boundary (own session per chapter, GC-guard set, drain registration). The analysis rate limiter's raw `SelfPruningLimiter` is hoisted so the batch pacer and the interactive FastAPI dep share ONE budget. The FE reuses the existing extraction review components and the existing apply endpoint (with the additive `chapter_id` provenance field). See ADR-092 + spec `docs/superpowers/specs/2026-10-03-bulk-extraction-design.md`.

**Tech Stack:** Python 3.14 · FastAPI · Pydantic v2 (`extra="forbid"`) · pyrate-limiter (existing) · pytest/vitest · React 19 · TanStack Query · next-intl (en/de/fr). No new dependencies.

## Global Constraints

- Project language: **English** — all code, comments, tests; i18n values follow existing locale files.
- **RULE-03:** `kb/bulk_extraction/contracts.py` Protocols land in Task 1, BEFORE any implementation. Every seam the service/runner consumes is a Protocol there.
- **RULE-04:** hard file-size limits (service ≤ 300, router ≤ 150, any module ≤ 400 lines). Each new module lands well under.
- **RULE-06:** router delegates immediately — no business logic, no try/except beyond the router_extraction.py:42-57 re-raise pattern; services hold no SQLAlchemy (repos only); the runner is the ONLY component opening its own sessions (via `get_session_factory()`), never the request session.
- **RULE-07:** `narrare_core` untouched by F2 (no Core changes at all); dependency flow `router → service → registry/runner/pacer → repos → DB`.
- **RULE-08:** no new dependency — the pacer uses the existing `SelfPruningLimiter`.
- **RULE-10 (THE F1 LESSON — hard):** every new service-ish file lands with its unit test file **in the SAME task**. Per-task verification MUST include `python scripts/check_test_coverage_gaps.py --fail-on-missing` (exit 0 required) in addition to the task's pytest/vitest run.
- **RULE-11:** every failure flips a queryable job/chapter state or re-raises; drain cancellation logs at info and marks the job `cancelled ("cancelled (server shutdown)")` — never a hung RUNNING job.
- **RULE-12/13:** novel-scoped REST surface; NO SSE — polling only (extraction is a `run()`-only operation; no `stream()` sibling is created anywhere).
- **RULE-16:** new i18n keys go into the existing `studio`/`importing`/`wizard` namespaces — `en`/`de`/`fr` updated in the SAME task as first use (Tasks 7, 8).
- **RULE-17:** FE type/field names in `packages/web/lib/api/bulkExtraction.ts` EXACTLY match `bulk_extraction/schemas.py` — same commit as the schema-defining task's FE mirror (Task 6; Task 1 does not touch TS).
- **RULE-18b:** no new settings surface. `NARRARE_RATE_LIMIT_ANALYSIS` already exists (`docs/development/deployment-guide.md:825`) — the only knob; do not add another.
- **RULE-19:** DI factories stay `SessionDep`-based (`bulk_extraction/dependencies.py`).
- **RULE-20:** no stubs — each task ships complete, tested behavior.
- **RULE-23:** ZERO new `# type: ignore` / `@ts-ignore`. Fakes implement Protocols properly.
- Errors: `narrare_core.shared.errors.ValidationError` → 422 (names the offending chapter id), `NotFoundError` → 404 (foreign novel, foreign≡unknown job), `ConflictError` → 409 (active job / cancel-or-resume on wrong state), `ConfigurationError` propagates loudly (ADR-086 semantics — fast-fails the job). No router-level try/except beyond NotFoundError re-raise.
- Git writes (add/commit/push) are executed by the coordinator via **NarrarePlatformSpecialist**.
- Frontend: Next.js 16 — components/hooks only; no Next API touched. Read the relevant guide in `node_modules/next/dist/docs/` only if that changes.
- Verification commands (repo root): backend unit `uv run --all-packages pytest <path> -v`; coverage-gap gate `uv run python scripts/check_test_coverage_gaps.py --fail-on-missing`; integration `just _ensure-services` then `uv run --all-packages pytest tests/integration/kb/test_bulk_extraction_api.py -v`; frontend `cd packages/web && pnpm test -- <filter>` (+ `pnpm type-check`); architecture `just check-architecture`; final gate `just verify`.

## Cross-task contract table — names every implementer must share

| Concept | Exact name | Defined | Consumed |
|---|---|---|---|
| Per-chapter state enum | `BulkChapterState` (`pending|running|done|failed`) | T1 schemas | T2 registry, T4 runner, T5 service, T6 FE mirror |
| Job status enum | `BulkJobStatus` (`pending|running|cancelling|completed|cancelled|failed`) | T1 schemas | T2/T4/T5/T6 |
| Engine cap / TTL | `BULK_EXTRACT_MAX_CHAPTERS = 200`, `BULK_JOB_TTL = timedelta(hours=24)` | T1 contracts | T1 schemas (Field max), T5 (422), T2 (sweep) |
| Chapter ref | `BulkChapterRef(chapter_id: UUID, title: str, position: int)` | T1 contracts | T2 create, T5 reader |
| Registry module fns | `create / status / results / request_cancel / reset_for_resume / mark_job_running / mark_chapter_running / mark_chapter_done / mark_chapter_failed / mark_job_completed / mark_job_failed / mark_cancelled / cancel_requested / pending_chapter_ids / find_active_for_novel / sweep_expired` | T2 registry | T4 runner, T5 service, T8 integration driver |
| Pacer | `acquire_analysis_pacer_slot(key=..., limiter=None)` + `PACER_POLL_SECONDS = 1.0` | T3 pacer | T4 runner |
| Raw shared limiter | `AI_ANALYSIS_LIMITER_RAW` (dep `AI_ANALYSIS_LIMITER.limiter is AI_ANALYSIS_LIMITER_RAW`) | T3 rate_limits | T3 pacer default |
| Dispatcher | `async def dispatch(job_id: str, novel_id: UUID, owner_id: UUID) -> None` in `runner.py` + `runner._INFLIGHT_TASKS` | T4 runner | T5 dependencies |
| Job state machine | `pending → running → {completed | cancelled | failed}`; `running → cancelling → cancelled`; resume allowed only from `cancelled|failed` (resets `pending`+`failed` chapters to `pending`, keeps `done`) | spec §4 | ALL |
| FE client | `startBulkExtraction / bulkJobStatus / bulkJobResults / cancelBulkJob / resumeBulkJob` | T6 | T7/T8 |
| Apply provenance | `extractionApi.applyExtraction(novelId, items, chapterId?, signal?)` → body `{items, chapter_id?}` | T6 | T7 review apply |
| Suggestion flag | `narrare:importSuggestExtract:{novel_id}` = JSON array of chapter ids | T8 | T8 sidebar/panel |

**Invariants:** (1) `item_count` is non-null **iff** chapter state is `done`; (2) full `ExtractionOutput` appears **only** in the results endpoint; (3) no code path writes to the KB except the pre-existing apply endpoint; (4) the pacer never blocks the event loop (non-blocking acquire + sleep loop); (5) owner pinning happens at `create` — after `verify_novel_owned`.

## Task sizing deviations (deliberate)

- ≤ 3 *source* files / ≤ 250 *production* LOC per task (tests + i18n data excluded, mirroring the F1/SETUP-003 plan sizing). Deviations:
  - **T4** touches 4 files — the 4th is the one-tuple append in `_app/inflight.py` (drain registration).
  - **T5** touches 4 files — the 4th is `_app/main.py` (two registration lines).
  - **T7** touches 5 files — 3 are the `en`/`de`/`fr` `studio.json` triples (RULE-16 forces same-task).
  - **T8** touches 4 code files (2 are ~10-line edits) + 6 locale/i18n files + tests.

---

### Task 1: `bulk_extraction/` contracts + schemas (RULE-03 first)

**Files:**
- Create: `apps/api/narrare/kb/bulk_extraction/__init__.py` (docstring only)
- Create: `apps/api/narrare/kb/bulk_extraction/contracts.py`
- Create: `apps/api/narrare/kb/bulk_extraction/schemas.py`
- Test: `tests/unit/api/kb/bulk_extraction/test_schemas.py`

**Interfaces:**
- Produces (T2/T3/T4/T5/T6 rely on these exact names):
  - contracts: `BULK_EXTRACT_MAX_CHAPTERS: Final[int] = 200`, `BULK_JOB_TTL: Final[timedelta] = timedelta(hours=24)`, `BulkChapterRef` frozen dataclass, Protocols `BulkChapterReader` (`async def load(self, novel_id: UUID, chapter_ids: Sequence[UUID]) -> list[BulkChapterRef]` — raises `ValidationError` naming unknown/foreign ids), `BulkExtractionPacer` (`async def acquire(self) -> None`), `BulkExtractionDispatcher` (`async def dispatch(self, job_id: str, novel_id: UUID, owner_id: UUID) -> None`), `BulkExtractionJobStore` (async `create_job`, `get_status`, `get_results`, `cancel_job`, `resume_job`, `has_active_for` — signatures mirror the registry functions of T2).
  - schemas: `BulkChapterState(str, Enum)`, `BulkJobStatus(str, Enum)`, `BulkExtractionStartRequest`, `BulkExtractionTotals`, `BulkChapterStatusView`, `BulkExtractionJobView`, `BulkExtractionStatusView`, `BulkExtractionResultChapter`, `BulkExtractionResultsView` — exact fields per spec §4 (`extra="forbid"` on the request model).

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/api/kb/bulk_extraction/test_schemas.py
"""Wire-model invariants for the bulk extraction job (F2, ADR-092)."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError as PydanticValidationError

from narrare.kb.bulk_extraction.contracts import BULK_EXTRACT_MAX_CHAPTERS, BULK_JOB_TTL
from narrare.kb.bulk_extraction.schemas import (
    BulkChapterState,
    BulkExtractionStartRequest,
    BulkExtractionStatusView,
    BulkJobStatus,
)


class TestContracts:
    def test_protocol_constants_pinned(self) -> None:
        assert BULK_EXTRACT_MAX_CHAPTERS == 200
        assert BULK_JOB_TTL.total_seconds() == 24 * 3600


class TestEnums:
    def test_chapter_states_are_the_normative_set(self) -> None:
        assert [s.value for s in BulkChapterState] == ["pending", "running", "done", "failed"]

    def test_job_statuses_are_the_normative_set(self) -> None:
        assert [s.value for s in BulkJobStatus] == [
            "pending", "running", "cancelling", "completed", "cancelled", "failed",
        ]


class TestStartRequest:
    def test_rejects_unknown_field(self) -> None:
        with pytest.raises(PydanticValidationError):
            BulkExtractionStartRequest.model_validate(
                {"chapter_ids": [uuid.uuid4()], "scope": "novel"}
            )

    def test_rejects_empty_and_over_cap(self) -> None:
        with pytest.raises(PydanticValidationError):
            BulkExtractionStartRequest.model_validate({"chapter_ids": []})
        with pytest.raises(PydanticValidationError):
            BulkExtractionStartRequest.model_validate(
                {"chapter_ids": [uuid.uuid4()] * (BULK_EXTRACT_MAX_CHAPTERS + 1)}
            )


class TestStatusView:
    def test_item_count_defaults_to_none(self) -> None:
        view = BulkExtractionStatusView.model_validate(
            {
                "job_id": "j", "novel_id": str(uuid.uuid4()), "status": "running",
                "created_at": "2026-10-03T10:00:00Z", "updated_at": "2026-10-03T10:00:00Z",
                "totals": {"total": 1, "done": 0, "failed": 0, "remaining": 1},
                "chapters": [
                    {"chapter_id": str(uuid.uuid4()), "title": "T", "position": 0,
                     "state": "pending"}
                ],
            }
        )
        assert view.chapters[0].item_count is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --all-packages pytest tests/unit/api/kb/bulk_extraction/test_schemas.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'narrare.kb.bulk_extraction'`

- [ ] **Step 3: Write contracts.py**

```python
# apps/api/narrare/kb/bulk_extraction/contracts.py
"""Bulk extraction contracts — Protocols BEFORE implementation (RULE-03, ADR-092).

The service consumes four seams (store/reader/dispatcher via the service,
pacer via the runner); unit tests substitute Protocol-conformant fakes.
Protocol constants (engine cap, TTL) live here so schemas and registry share
one definition.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Final, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from narrare.kb.bulk_extraction.schemas import (
        BulkExtractionJobView,
        BulkExtractionResultsView,
        BulkExtractionStatusView,
    )

#: Engine cap — protocol constant (like the v1 import guardrails), no settings
#: surface (RULE-18b). 422 names the count when exceeded.
BULK_EXTRACT_MAX_CHAPTERS: Final[int] = 200

#: Terminal jobs are swept from the in-memory registry after this TTL.
BULK_JOB_TTL: Final[timedelta] = timedelta(hours=24)


@dataclass(frozen=True, slots=True)
class BulkChapterRef:
    """Identity slice of one chapter the job will process (position order)."""

    chapter_id: "UUID"
    title: str
    position: int


class BulkChapterReader(Protocol):
    """Load + validate chapters for a novel (raises ValidationError on bad ids)."""

    async def load(self, novel_id: "UUID", chapter_ids: "Sequence[UUID]") -> list[BulkChapterRef]:
        ...


class BulkExtractionPacer(Protocol):
    """Acquire one shared-analysis-budget slot (never blocks the event loop)."""

    async def acquire(self) -> None:
        ...


class BulkExtractionDispatcher(Protocol):
    """Launch the in-process runner for a job (fire-and-forget)."""

    async def dispatch(self, job_id: str, novel_id: "UUID", owner_id: "UUID") -> None:
        ...


class BulkExtractionJobStore(Protocol):
    """Registry operations consumed by the service (T2 implements)."""

    async def create_job(
        self, novel_id: "UUID", owner_user_id: "UUID", chapters: "Sequence[BulkChapterRef]"
    ) -> "BulkExtractionJobView": ...

    async def get_status(self, job_id: str, user_id: "UUID") -> "BulkExtractionStatusView": ...

    async def get_results(self, job_id: str, user_id: "UUID") -> "BulkExtractionResultsView": ...

    async def cancel_job(self, job_id: str, user_id: "UUID") -> "BulkExtractionJobView": ...

    async def resume_job(self, job_id: str, user_id: "UUID") -> "BulkExtractionJobView": ...

    async def has_active_for(self, novel_id: "UUID") -> bool: ...
```

- [ ] **Step 4: Write schemas.py** — the nine models with the exact fields from spec §4 (`chapter_ids: list[UUID] = Field(min_length=1, max_length=BULK_EXTRACT_MAX_CHAPTERS)`; `BulkExtractionTotals{total, done, failed, remaining: int ≥ 0}`; `BulkChapterStatusView{chapter_id: UUID, title: str, position: int ≥ 0, state: BulkChapterState, item_count: int | None = None}`; `BulkExtractionJobView{job_id: str, novel_id: UUID, status: BulkJobStatus, created_at, updated_at, totals, error: str | None = None}`; `BulkExtractionStatusView` = job view + `chapters: list[BulkChapterStatusView]`; `BulkExtractionResultChapter{chapter_id, title, position, state, output: ExtractionOutput | None = None}` importing `ExtractionOutput` from `narrare_core.agents.extraction_types`; `BulkExtractionResultsView{job_id, novel_id, status, chapters}`). All models `model_config = ConfigDict(extra="forbid")`.

- [ ] **Step 5: Run tests + coverage-gap gate**

Run: `uv run --all-packages pytest tests/unit/api/kb/bulk_extraction/ -v`
Expected: PASS
Run: `uv run python scripts/check_test_coverage_gaps.py --fail-on-missing`
Expected: exit 0

- [ ] **Step 6: Commit**

```bash
git add apps/api/narrare/kb/bulk_extraction/ tests/unit/api/kb/bulk_extraction/test_schemas.py
git commit -m "feat(kb): bulk extraction contracts + wire schemas (F2 T1, ADR-092)"
```

---

### Task 2: In-memory job registry

**Files:**
- Create: `apps/api/narrare/kb/bulk_extraction/registry.py`
- Test: `tests/unit/api/kb/bulk_extraction/test_registry.py`

**Interfaces:**
- Consumes: T1 schemas + `BulkChapterRef`; `narrare_core.shared.errors.{NotFoundError, ConflictError}`.
- Produces (T4/T5 rely on exact names): module-level functions
  `create(novel_id, owner_user_id, chapters) -> BulkExtractionJobView` (token id via `secrets.token_urlsafe(16)`, owner pinned),
  `status(job_id, user_id) -> BulkExtractionStatusView`,
  `results(job_id, user_id) -> BulkExtractionResultsView` (`output` present iff `done`),
  `request_cancel(job_id, user_id) -> BulkExtractionJobView` (sets `cancel_requested`, status → `cancelling`; `ConflictError` if terminal),
  `reset_for_resume(job_id, user_id) -> BulkExtractionJobView` (`ConflictError` unless `cancelled|failed`; pending+failed chapters → `pending`, `done` kept, error cleared, status → `pending`),
  `mark_job_running(job_id)`, `mark_chapter_running(job_id, chapter_id)`, `mark_chapter_done(job_id, chapter_id, output: ExtractionOutput)` (sets `item_count = len(output.results)`), `mark_chapter_failed(job_id, chapter_id, error: str)`, `mark_job_completed(job_id)`, `mark_job_failed(job_id, error: str)`, `mark_cancelled(job_id, reason: str)` (terminal; used by drain done-callback),
  `cancel_requested(job_id) -> bool`, `pending_chapter_ids(job_id) -> list[UUID]` (position order, snapshot), `find_active_for_novel(novel_id) -> str | None`, `sweep_expired(now=_now) -> int` (terminal + older than `BULK_JOB_TTL`).
- Semantics: `_JOBS: dict[str, _BulkJobRecord]` process-local; user-facing ops check `owner_user_id` — mismatch raises `NotFoundError(f"Bulk extraction job '{job_id}' not found")` (foreign≡unknown, mirrors `export/registry.py:145-155`); `mark_*` are job-id-keyed no-ops-with-warning on unknown ids (mirrors `export/registry.py:162-169`); all mutations synchronous (single asyncio loop). Test isolation: a fixture clears `registry._JOBS`.

- [ ] **Step 1: Write the failing tests** — `tests/unit/api/kb/bulk_extraction/test_registry.py` covering, as classes:
  - `TestOwnership`: foreign user on `status`/`results`/`request_cancel`/`reset_for_resume` → `NotFoundError` identical to unknown id (same message).
  - `TestLifecycle`: create → pending with totals `{total=n, done=0, failed=0, remaining=n}`; `mark_job_running`; `mark_chapter_running` → state running; `mark_chapter_done` → state done + `item_count == len(results)` + output stored; `mark_job_completed` → totals computed (`remaining == 0`).
  - `TestCancel`: `request_cancel` → `cancelling` + `cancel_requested() is True`; on terminal job → `ConflictError`; `mark_cancelled(job_id, "cancelled (server shutdown)")` → status cancelled.
  - `TestResume`: from `cancelled` with one `done` + one `pending` + one `failed` → `reset_for_resume` resets pending+failed to pending, keeps done output + item_count, status pending; from `completed`/`running` → `ConflictError`.
  - `TestFailureIsolation`: `mark_chapter_failed` records error, job stays running; `mark_job_failed` sets job error + terminal.
  - `TestSweep`: completed job older than `BULK_JOB_TTL` swept; running job never swept; returns count.
  - `TestActiveScan`: `find_active_for_novel` returns the id of a `running` job, `None` when only terminal jobs exist.
  Concrete construction helper `_ref(position)` building `BulkChapterRef(uuid4(), "T", position)`.
- [ ] **Step 2:** Run `uv run --all-packages pytest tests/unit/api/kb/bulk_extraction/test_registry.py -v` — expect FAIL (`ModuleNotFoundError … registry`).
- [ ] **Step 3: Implement `registry.py`** per the Interfaces block (module-level functions + `_BulkJobRecord` dataclass holding `job` state, `chapters: list[_ChapterRecord]`, `outputs: dict[UUID, ExtractionOutput]` on the chapter records, `owner_user_id`, `cancel_requested`, `expires_hint` set when terminal). Status/results views are derived (totals recomputed; `results` includes every chapter with `output` only when `done`).
- [ ] **Step 4:** Re-run the task test file — PASS. Then the coverage-gap gate — exit 0.
- [ ] **Step 5: Commit** — `git add apps/api/narrare/kb/bulk_extraction/registry.py tests/unit/api/kb/bulk_extraction/test_registry.py` · message `feat(kb): in-memory bulk extraction job registry (F2 T2, ADR-092)`

---

### Task 3: Shared analysis budget — limiter hoist + pacer

**Files:**
- Modify: `apps/api/narrare/_app/rate_limits.py` (hoist; ~lines 160-180)
- Create: `apps/api/narrare/kb/bulk_extraction/pacer.py`
- Test: `tests/unit/api/kb/bulk_extraction/test_pacer.py`

**Interfaces:**
- Consumes: `SelfPruningLimiter` (`_app/rate_limiter_dep.py:38-117`), `get_core_settings` (e2e short-circuit, mirrors `rate_limiter_dep.py:170-174`).
- Produces: in `rate_limits.py` — `ANALYSIS_RATE: Final[Rate]`, `AI_ANALYSIS_LIMITER_RAW: Final[SelfPruningLimiter]`, `AI_ANALYSIS_LIMITER: Final[_RateLimiterDep] = _RateLimiterDep(AI_ANALYSIS_LIMITER_RAW)` (same instance; resolved once at import — restart to apply, unchanged semantics). In `pacer.py` — `PACER_POLL_SECONDS: Final[float] = 1.0` and `async def acquire_analysis_pacer_slot(key: str = "kb-bulk-extraction", limiter: SelfPruningLimiter | None = None) -> None`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/api/kb/bulk_extraction/test_pacer.py
"""Shared-budget pacer tests (F2 T3, ADR-092 D7a)."""

from __future__ import annotations

import asyncio

from narrare._app import rate_limits
from narrare._app.rate_limiter_dep import SelfPruningLimiter
from narrare.kb.bulk_extraction.pacer import PACER_POLL_SECONDS, acquire_analysis_pacer_slot
from pyrate_limiter import Duration, Rate


class TestSharedBudget:
    def test_dep_wraps_the_raw_instance(self) -> None:
        # One budget: the FastAPI dep and the pacer MUST hit the same bucket.
        assert rate_limits.AI_ANALYSIS_LIMITER.limiter is rate_limits.AI_ANALYSIS_LIMITER_RAW

    def test_governed_default_unchanged(self) -> None:
        assert rate_limits.RATE_LIMIT_ANALYSIS_DEFAULT == 5
        assert rate_limits.ANALYSIS_RATE.limit == 5
        assert rate_limits.ANALYSIS_RATE.interval == Duration.MINUTE


class _FakeLimiter:
    """Non-pyrate stand-in: denies until `denials` exhausted, then admits."""

    def __init__(self, denials: int) -> None:
        self._denials = denials
        self.calls = 0

    async def try_acquire_async(self, name: str = "p", weight: int = 1,
                                blocking: bool = True, timeout: int | float = -1) -> bool:
        self.calls += 1
        if self._denials > 0:
            self._denials -= 1
            return False
        return True


class TestAcquireLoop:
    async def test_retries_until_admitted_without_loop_block(self) -> None:
        fake = _FakeLimiter(denials=2)
        await asyncio.wait_for(acquire_analysis_pacer_slot(limiter=fake), timeout=5)  # type: ignore[arg-type]
        assert fake.calls == 3

    async def test_poll_interval_is_short(self) -> None:
        assert 0 < PACER_POLL_SECONDS <= 1.0
```

(If the injected fake needs the `SelfPruningLimiter` type for the signature, widen the parameter to a minimal `Protocol` named `PacerLimiter` inside `pacer.py` instead of `SelfPruningLimiter` — RULE-23 forbids the `# type: ignore`; the Protocol is the clean answer and `SelfPruningLimiter` satisfies it structurally.)

- [ ] **Step 2:** Run `uv run --all-packages pytest tests/unit/api/kb/bulk_extraction/test_pacer.py -v` — expect FAIL (no `ANALYSIS_RATE`, no `pacer` module).
- [ ] **Step 3: Hoist in `rate_limits.py`** — replace the `AI_ANALYSIS_LIMITER` construction block with the spec §7 snippet: build `ANALYSIS_RATE` once, `AI_ANALYSIS_LIMITER_RAW = SelfPruningLimiter(ANALYSIS_RATE)`, `AI_ANALYSIS_LIMITER = _RateLimiterDep(AI_ANALYSIS_LIMITER_RAW)`. Docstring note: raw handle shared with the bulk pacer (ADR-092 D7a); existing tests in `tests/unit/api/_app/test_rate_limits.py` must stay green UNCHANGED (same count, same env var, same dep behavior).
- [ ] **Step 4: Implement `pacer.py`** — e2e short-circuit first (`get_core_settings().e2e_test` → return), then `while not await limiter.try_acquire_async(key, blocking=False): await asyncio.sleep(PACER_POLL_SECONDS)`, resolving `limiter` to `AI_ANALYSIS_LIMITER_RAW` when `None`.
- [ ] **Step 5:** Run task tests + `tests/unit/api/_app/test_rate_limits.py` (both PASS) + coverage-gap gate (exit 0).
- [ ] **Step 6: Commit** — `git add apps/api/narrare/_app/rate_limits.py apps/api/narrare/kb/bulk_extraction/pacer.py tests/unit/api/kb/bulk_extraction/test_pacer.py` · message `feat(kb): shared analysis budget — hoisted raw limiter + batch pacer (F2 T3)`

---

### Task 4: Runner — in-process loop, own sessions, cooperative cancel, drain

**Files:**
- Create: `apps/api/narrare/kb/bulk_extraction/runner.py`
- Modify: `apps/api/narrare/_app/inflight.py` (`_DRAIN_SOURCES` += `"narrare.kb.bulk_extraction.runner"`)
- Test: `tests/unit/api/kb/bulk_extraction/test_runner.py`

**Interfaces:**
- Consumes: T2 registry fns; T3 `acquire_analysis_pacer_slot`; `get_session_factory` (`_app/database.py`; own-session precedent `export/tasks.py:251-257`); `ExtractionService` + its wiring shape from `kb/dependencies_extraction.py:61-98` (registry, `LazyModelResolution(LLMIntent.KB_EXTRACT, owner, novel_id)`, Chapter/KB/Novel repos, composer, pipeline, run-limit resolver — apply deps NOT needed).
- Produces: `_INFLIGHT_TASKS: set[asyncio.Task[None]]`; `async def dispatch(job_id: str, novel_id: UUID, owner_id: UUID) -> None` (create_task named `job_id`, GC guard, done-callback, info log — mirrors `export/tasks.py:215-234`); `async def run_bulk_extraction(job_id: str, novel_id: UUID, owner_id: UUID) -> None` — the spec §5 loop. Injectable seams for tests (module attributes, monkeypatch style of `export/tasks.py:94-96`): `_service_factory: Callable[[AsyncSession, UUID, UUID], ExtractionService]`, `_pacer_acquire = acquire_analysis_pacer_slot`.
- Loop (normative): `mark_job_running` → for `chapter_id` in `pending_chapter_ids(job_id)` snapshot: if `cancel_requested(job_id)` → `mark_cancelled(job_id, "cancelled by user")` + return; `await _pacer_acquire()`; `mark_chapter_running`; `async with session_factory() as session:` build real service via `_service_factory(session, owner_id, novel_id)`; `try: output = await service.extract_from_chapter(novel_id, chapter_id, owner_id)` → `mark_chapter_done` `except ConfigurationError → mark_job_failed + return` `except Exception → mark_chapter_failed + continue`. End → `mark_job_completed`. `CancelledError` propagates (NOT caught by `except Exception`); `_on_done` maps `task.cancelled()` → `mark_cancelled(job_id, "cancelled (server shutdown)")` (mirrors `export/tasks.py:188-212`).

- [ ] **Step 1: Write the failing tests** — `tests/unit/api/kb/bulk_extraction/test_runner.py` with a `_RecordingRegistry` fake (monkeypatched onto `runner.registry`), a `_NoopPacer`, and a `_FakeServiceFactory` returning a service whose `extract_from_chapter` is scriptable per chapter:
  - `test_state_walk`: 2 chapters succeed → calls observed `[running, done, running, done]`, job completed, totals `{2,2,0,0}`.
  - `test_failure_isolation`: chapter 1 raises `RuntimeError` → chapter 1 `failed`, chapter 2 `done`, job completed (not failed).
  - `test_configuration_error_fails_job_fast`: first chapter raises `ConfigurationError("NO_AI_PROVIDER")` → `mark_job_failed` called, chapter 2 never attempted.
  - `test_cooperative_cancel_between_chapters`: cancel flag set after chapter 1 → chapter 2 stays pending, job `mark_cancelled("cancelled by user")`; the in-flight chapter is never interrupted.
  - `test_pacer_acquired_per_chapter`: pacer acquire called exactly once per attempted chapter.
  - `test_own_session_per_chapter`: session factory called once per chapter (fake factory).
  - `test_cancelled_error_propagates`: raising `asyncio.CancelledError` from the service is not swallowed by the failure path (assert it propagates out of `run_bulk_extraction`).
  - `test_on_done_marks_shutdown_cancelled`: a cancelled task whose name is a job id flips the registry record (fake registry records `mark_cancelled(job_id, "cancelled (server shutdown)")`).
- [ ] **Step 2:** Run — expect FAIL (no `runner` module).
- [ ] **Step 3: Implement `runner.py`** per Interfaces; real `_service_factory` mirrors `dependencies_extraction.py:61-98` minus apply deps; owner resolution is passed IN (`owner_id` parameter — the service resolves it before dispatch; runner never guesses).
- [ ] **Step 4:** Append the drain source in `_app/inflight.py` `_DRAIN_SOURCES` (+ its docstring list) — one line, mirroring the export entry.
- [ ] **Step 5:** Run task tests + `tests/unit/api/_app/test_inflight.py` (if present) + coverage-gap gate — all green.
- [ ] **Step 6: Commit** — `git add apps/api/narrare/kb/bulk_extraction/runner.py apps/api/narrare/_app/inflight.py tests/unit/api/kb/bulk_extraction/test_runner.py` · message `feat(kb): in-process bulk extraction runner with drain registration (F2 T4)`

---

### Task 5: Service + router + DI + mount (backend complete)

**Files:**
- Create: `apps/api/narrare/kb/bulk_extraction/service.py`
- Create: `apps/api/narrare/kb/bulk_extraction/router.py`
- Create: `apps/api/narrare/kb/bulk_extraction/dependencies.py`
- Modify: `apps/api/narrare/_app/main.py` (import + include, next to `kb_extraction_router` at `main.py:225`/`~:303`)
- Test: `tests/unit/api/kb/bulk_extraction/test_service.py`, `tests/integration/kb/test_bulk_extraction_api.py`

**Interfaces:**
- Consumes: T1 Protocols, T2 registry, T4 `dispatch`, `verify_novel_owned` (`kb/_novel_gate.py`), `ChapterRepository.list_by_novel` (`chapters/repository.py:36-42`).
- Produces: `BulkExtractionService(store, reader, dispatcher, novel_repo)` with `async def start(novel_id, user_id, chapter_ids) -> BulkExtractionJobView` (gate → reader.load validation: duplicates + unknown ids → `ValidationError` naming the id; order = position; cap enforced by the schema + reader; `has_active_for` → `ConflictError("A bulk extraction job is already active for this novel")`; create → `await dispatcher.dispatch(...)` → view), `status`, `results`, `cancel`, `resume` (gate once, delegate; `cancel` idempotence via registry `ConflictError`). Router: five thin routes on `APIRouter(tags=["kb-extraction"])` — `POST …/kb/extract/bulk` (201), `GET …/kb/extract/bulk/{job_id}/status`, `GET …/kb/extract/bulk/{job_id}/results`, `POST …/kb/extract/bulk/{job_id}/cancel`, `POST …/kb/extract/bulk/{job_id}/resume` — ownership via `CurrentUserIdDep`, `NotFoundError` re-raise pattern per `router_extraction.py:42-52`. `dependencies.py`: `get_bulk_extraction_service(session: SessionDep, novel_id: UUID, user_id: str = Depends(get_current_user_id))` wiring the REAL registry module + `ChapterReader` (ChapterRepository-backed) + `runner.dispatch` (test seams stay Protocol-clean).

- [ ] **Step 1: Failing service unit tests** (`test_service.py`, fake store/reader/dispatcher implementing the T1 Protocols):
  - `test_start_validates_and_orders`: reader returns refs out of order → job created in position order; duplicates → `ValidationError` naming the id; unknown id → same.
  - `test_start_rejects_active_job`: store reports active → `ConflictError`, `create_job` never called.
  - `test_start_gates_ownership_first`: foreign novel → `NotFoundError`, reader never touched (gate-before-load, IDOR precedent `extraction_service.py:150`).
  - `test_status_results_cancel_resume_delegate`: each method calls the store with `(job_id, user_id)` and returns the view.
- [ ] **Step 2:** Run — FAIL.
- [ ] **Step 3: Implement service.py + dependencies.py + router.py**; mount in `main.py` next to the extraction router.
- [ ] **Step 4:** Service tests PASS + coverage-gap gate exit 0.
- [ ] **Step 5: Integration test** (`tests/integration/kb/test_bulk_extraction_api.py`; services via `just _ensure-services`): create novel + 3 chapters via existing repos → `POST …/bulk` (201; job view totals) → `GET …/status` (chapter rows in position order, states pending) → drive two chapters to done via `registry.mark_chapter_done` from the test process (the runner is bypassed by overriding `dispatcher` through the DI seam OR by not dispatching — use the app's dependency_overrides to inject a no-op dispatcher) → `GET …/results` (outputs present iff done) → `POST …/cancel` on the dispatched-less job → 409 on second cancel → `POST …/resume` (200; pending reset) → foreign user's `GET …/status` → 404; foreign novel `POST …/bulk` → 404; unknown chapter id → 422 naming it.
- [ ] **Step 6:** Run integration file — PASS. Run `just check-architecture` — exit 0.
- [ ] **Step 7: Commit** — `git add apps/api/narrare/kb/bulk_extraction/ apps/api/narrare/_app/main.py tests/unit/api/kb/bulk_extraction/test_service.py tests/integration/kb/test_bulk_extraction_api.py` · message `feat(kb): bulk extraction endpoints — start/status/results/cancel/resume (F2 T5)`

---

### Task 6: FE API client + RULE-17 mirror + apply provenance field

**Files:**
- Create: `packages/web/lib/api/bulkExtraction.ts`
- Modify: `packages/web/lib/api/extraction.ts:69-74` (optional `chapterId`)
- Test: `packages/web/lib/api/bulkExtraction.test.ts`, `packages/web/lib/api/extraction.test.ts` (extend)

**Interfaces:**
- Produces (T7/T8 rely on exact names): types inline (extraction.ts precedent — no separate `types/` file; documented deviation from the importing.ts pattern): `BulkChapterState`, `BulkJobStatus`, `BulkExtractionTotals`, `BulkChapterStatusView`, `BulkExtractionJobView`, `BulkExtractionStatusView`, `BulkExtractionResultChapter { output: ExtractionOutput | null }`, `BulkExtractionResultsView` — field names EXACTLY matching T1 schemas. Client `bulkExtractionApi = { startBulkExtraction(novelId, chapterIds, signal?), bulkJobStatus(novelId, jobId, signal?), bulkJobResults(novelId, jobId, signal?), cancelBulkJob(novelId, jobId, signal?), resumeBulkJob(novelId, jobId, signal?) }` — REST paths per spec §4. `extractionApi.applyExtraction(novelId, items, chapterId?, signal?)` → body `{ items, ...(chapterId ? { chapter_id: chapterId } : {}) }` (ADR-085 provenance; additive — existing two-arg callers unchanged).

- [ ] **Step 1: Failing vitest** — path assertions (fetch mock): five client paths; body shape of apply with/without `chapterId`; mirror parity test asserting the TS type field list equals the schema field list via a typed fixture object.
- [ ] **Step 2:** `pnpm test -- bulkExtraction` — FAIL.
- [ ] **Step 3: Implement** both files.
- [ ] **Step 4:** `pnpm test -- bulkExtraction extraction` PASS; `pnpm type-check` clean.
- [ ] **Step 5: Commit** — `git add packages/web/lib/api/bulkExtraction.ts packages/web/lib/api/extraction.ts packages/web/lib/api/bulkExtraction.test.ts packages/web/lib/api/extraction.test.ts` · message `feat(web): bulk extraction API client + apply chapter provenance (F2 T6)`

---

### Task 7: BulkExtractionPanel — progress, review reuse, walking (+ i18n)

**Files:**
- Create: `packages/web/components/studio/extraction/useBulkExtractionJob.ts`
- Create: `packages/web/components/studio/extraction/BulkExtractionPanel.tsx`
- Create: `packages/web/components/studio/extraction/BulkChapterReview.tsx` (wraps `ExtractionReview` + apply via `useApplyExtraction` with `chapterId`)
- Modify: `packages/i18n/messages/{en,de,fr}/studio.json` (`kb.bulkExtraction.*`)
- Test: `packages/web/components/studio/extraction/BulkExtractionPanel.test.tsx`

**Interfaces:**
- Consumes: T6 client; existing `ExtractionReview` (`components/studio/extraction/ExtractionReview.tsx:16-32`), `ExtractionItemCard`, `useExtractionSelection` (`lib/hooks/useExtractionSelection.ts`), `useApplyExtraction` (`lib/hooks/useExtraction.ts:88-126`), `ExtractionHeader`, `ExtractionFooter` phase chrome, `useAIOperation` conventions (§16: cancel/abort, connection-lost, actionable errors).
- Produces: `useBulkExtractionJob(novelId: string, jobId: string | null)` — TanStack Query on `bulkJobStatus`, `refetchInterval: 3000` while `status ∈ pending|running|cancelling`, `false` on terminal; `isInterrupted` when the query 404s (degrade per spec §8.2). `BulkExtractionPanel(props: { novelId: string; chapterIds: string[]; onClose: () => void })` — owns the job lifecycle: start on mount (if no job yet), progress mode (totals + per-chapter state chips + cancel), interrupted mode (explanation + restart), review mode (chapter rail by position with ✓ applied / – skipped badges; `BulkChapterReview` renders `ExtractionReview` for the active chapter; **Next chapter** walks to the next `done` chapter without an applied/skipped marker; apply per chapter calls `useApplyExtraction` with that chapter's id).

- [ ] **Step 1: Failing vitest** (RTL + msw/query): progress rendering from a status fixture; poll stops on `completed`; cancel → `cancelling` chip state; 404 status → interrupted copy + restart button; review mode renders `ExtractionReview` for the first done chapter; apply posts `{ items, chapter_id }`; walking advances past an applied chapter; resume button appears for `cancelled|failed` and re-polls.
- [ ] **Step 2:** `pnpm test -- BulkExtractionPanel` — FAIL.
- [ ] **Step 3: Implement** the three files; add `kb.bulkExtraction.*` keys to ALL THREE locales (RULE-16): `title, chaptersDone ("{done} of {total} chapters"), statePending/Running/Done/Failed, cancel, cancelling, cancelled, interruptedTitle, interruptedBody, restart, resume, reviewTitle, nextChapter, applyForChapter ("Apply to Knowledge Base"), applied, skipped, costNote`.
- [ ] **Step 4:** `pnpm test -- BulkExtractionPanel` PASS; `pnpm type-check` clean; `pnpm test` (full web suite) green.
- [ ] **Step 5: Commit** — `git add packages/web/components/studio/extraction/ packages/i18n/messages/` · message `feat(web): BulkExtractionPanel with review reuse + next-unreviewed walking (F2 T7)`

---

### Task 8: Post-commit CTA — modal success card + wizard suggestion flag (+ i18n)

**Files:**
- Modify: `packages/web/components/studio/importing/ImportModal.tsx:29-46` (capture commit result → success card)
- Modify: `packages/web/components/studio/wizard/useWizardCompletion.ts:34-44` (set flag on success)
- Modify: `packages/web/components/studio/SidebarChapterList.tsx:89-98,161-196` (sibling suggestion card)
- Create: `packages/web/components/studio/importing/ImportSuggestExtractBanner.tsx`
- Modify: `packages/i18n/messages/{en,de,fr}/importing.json` + `wizard.json`
- Test: extend `ImportModal.test.tsx`, `SidebarChapterList.test.tsx`, `wizard.test.tsx` / `useWizardCompletion` tests

**Interfaces:**
- Consumes: `ImportCommitResponse` (`types/importing.ts`; server `importing/schemas.py:64-76`), `BulkExtractionPanel` (T7), flag lifecycle of `narrare:importFailed:{novel_id}` (`useWizardCompletion.ts:42`, `SidebarChapterList.tsx:89-98,161-171,182-196`).
- Produces: `ImportSuggestExtractBanner(props: { onStart: (chapterIds: string[]) => void; onDismiss: () => void })`; flag contract `narrare:importSuggestExtract:{novel_id}` = `JSON.stringify(string[])` (chapter ids); ImportModal success card shows `N chapters · M words · N AI calls` (N = `chapters.length`, M = `Σ word_count`) + `[Extract to Knowledge Base]` → `onOpenChange(false)` + opens the panel (parent state in `SidebarChapterList`/editor host) + `[Not now]`; panel open state lifted where `ImportModal` is hosted (`SidebarChapterList.tsx:182-196`) via a `bulkOpen`/`bulkChapterIds` state pair.

- [ ] **Step 1: Failing vitest:** success card renders after a successful commit (mock `importApi.commit` → `{ chapters: [2 items with word_counts] }`) asserting the `2 chapters · 34 words · 2 AI calls` line + both buttons; wizard completion sets the flag with the JSON id array on success and NOT on failure (existing failed-flag test stays green); sidebar renders the suggestion banner when the flag is set, clears it on dismiss AND on start (removeItem + state), absent when unset.
- [ ] **Step 2:** `pnpm test -- ImportModal SidebarChapterList wizard` — FAIL (new assertions).
- [ ] **Step 3: Implement** the four files; add `importing.suggestExtract.*` (title/body/actions + cost line template `"{chapters} chapters · {words} words · {calls} AI calls"`) and `wizard.suggestExtract.*` keys in all three locales.
- [ ] **Step 4:** Full `pnpm test` + `pnpm type-check` green.
- [ ] **Step 5: Commit** — `git add packages/web/components/studio/ packages/i18n/messages/` · message `feat(web): post-import extraction CTA — modal success card + wizard suggestion flag (F2 T8)`

---

### Task 9: Docs closure (no production code)

**Files:**
- Modify: `docs/architecture/decisions/INDEX.md` (ADR-092 row → `✅ Implemented`)
- Modify: `docs/architecture/decisions/ADR-092-bulk-extraction-job.md` (header note: implemented, plan executed)
- Modify: `docs/features/setup/SETUP-003-import.md` (follow-up list: bulk extraction shipped → link ADR-092; IO-002 corpus pass remains)
- Modify: `docs/_shared/CURRENT_STATE.md` (one entry per its volatility policy — facts + links only, no counts)

**Steps:**
- [ ] **Step 1:** Update the four docs (frontmatter/status sections only; CURRENT_STATE entry follows `check_current_state_facts.py` rules — link the ADR + spec, claim no volatile metrics).
- [ ] **Step 2:** Run `just check-architecture` — exit 0 (docs gates: ADR INDEX↔file coverage, frontmatter schema, feature path accuracy, current-state facts).
- [ ] **Step 3:** Run `just verify` (coordinator-triggered, via **NarrarePlatformSpecialist**) — full gate green.
- [ ] **Step 4: Commit** — `git add docs/` · message `docs(kb): ADR-092 implementation closure + SETUP-003 follow-up state (F2 T9)`

---

## Self-review checklist (executed)

- Spec §4 endpoints → T5; §5 loop → T4; §6 registry → T2; §7 pacer → T3; §8.1 CTA → T8; §8.2 panel → T7; RULE-17 mirror → T1/T6; i18n → T7/T8; docs → T9. No spec section untasked.
- Every task's test file is created in the SAME task (RULE-10 lesson) and the coverage-gap gate is a per-task step.
- No placeholders: interface code blocks are complete for T1/T3; T2/T4/T5/T6/T7/T8 carry exact function/type/prop signatures and enumerated test cases with concrete fixtures.
