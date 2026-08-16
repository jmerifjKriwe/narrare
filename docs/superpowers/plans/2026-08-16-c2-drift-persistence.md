# C2 — Drift Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist the SERIES-004 cross-novel drift checks (canon contradictions + series-scope voice drift) as ONE latest-wins snapshot per novel with an input-fingerprint stale flag, retrieved via `GET /api/v1/series/{series_id}/consistency/{novel_id}`, and hydrate the Bände-Tab drift panel from the persisted snapshot instead of an empty state (program item C2 of the Post-Export Follow-ups program, design §5).

**Architecture:** One new novel-scoped table `series_drift_results` (Alembic **0040**, `novel_id` PK like `band_summaries`) whose single JSONB column holds the composite document `{"consistency": SeriesConsistencyCheckResponse, "voice_drift": AuthorVoiceDriftResponse}` — the **existing run-result models serialized verbatim, never re-shaped**. A new `SeriesDriftPersistenceService` **wraps** (does not modify) the two existing run services — `series_voice_drift_service.py` is at **298/300 lines** and `series_consistency_service.py` at **265/300**, so both stay byte-identical (zero regression, the ADR-079 Decision-4 pattern) — storing its section after each successful run via a race-free atomic JSONB-merge upsert (the panel fires both POSTs in parallel; a naive get-or-create would PK-collide). Staleness reuses the ADR-045 fingerprint scheme: a new `fingerprint_chapter_texts()` in `narrare_core/ai_invocation/correlation.py` built on the existing `_hash_payload` (SHA-256 over canonical JSON with the `narrare:adr045:v1` domain separator — **no new hash scheme**), computed over the band's position-ordered non-empty chapter texts (the same read path + filter `SeriesConsistencyService` uses). Frontend: one new GET hook + snapshot hydration + stale badge in `SeriesDriftPanel`.

**Tech Stack:** Python 3.14, SQLAlchemy 2.0 async (`postgresql.insert … ON CONFLICT DO UPDATE`, JSONB `||` merge), Alembic, FastAPI (Depends-chained DI), Pydantic v2, TanStack Query, next-intl (ICU date), Vitest + Testing Library.

**Binding spec:** `docs/superpowers/specs/2026-08-14-post-export-followups-design.md` §5 (C2 — binding decisions: stored payload = **full result set as ONE JSON document**; history model = **latest-wins, exactly one record per novel, new run overwrites, `generated_at` timestamp**; staleness = **fingerprint over the band's chapter texts stored on save, recomputed on GET → `stale: true/false`**; retrieval = **`GET …/consistency/{novel_id}`**, the shape sketched in SERIES-004's deferral — plan `2026-08-02-series-cross-novel-drift.md` line 29: `GET /api/v1/series/{id}/consistency/{novel_id}`; scope = Alembic **0040**, results repository + service extension, frontend snapshot loading, **ADR-079 post-implementation amendment — no new ADR**). §12 C2 gates: **migration round-trip, latest-wins overwrite test, stale-flag flip test**. This plan implements exactly that — nothing more, nothing less.

## Global Constraints

- **Slice semantics (RULE-20):** Tasks 1–10 are sequentially executable sub-slices of ONE coherent slice. The feature is user-visible only after Task 9's gate passes; earlier tasks land typed-but-unused plumbing (mirroring C5/C1 seam-first ordering). Each sub-task is independently testable and commits cleanly.
- **Package sizing:** ≤3 production files and ≤250 new LOC per delegated sub-task (test files, `tests/fakes/`, and docs do not count toward the file cap; i18n message files count as production files — Task 8 is exactly the 3 locale files).
- **Contract-first (RULE-03):** `apps/api/narrare/series/series_drift_contracts.py` + `series_drift_schemas.py` (Task 3) are authored FIRST and are **untouchable** for the remainder of the slice. Any later need to change them = STOP and report to the coordinator.
- **File-size limits** (`pyproject.toml [tool.narrare.architecture.file_size_limits]`; the pre-commit `architecture-constraints` hook BLOCKS the commit on violation). Verified state at plan time: `series_voice_drift_service.py` **298/300** and `series_consistency_service.py` **265/300** — **neither may be touched** (that is why persistence is a wrapper service in a NEW file); `router_consistency.py` 62/150 and `router_voice_drift.py` 70/150 — both may grow modestly; `narrare_core/ai_invocation/correlation.py` 170/400; dependency modules limit **200**; models/schemas/contracts limit **200**; repository limit **250**. All new files in this plan are far under their limits.
- **Zero-regression guarantee:** `SeriesConsistencyService`, `SeriesVoiceDriftService`, their contracts, schemas, prompts, and their existing unit tests stay **byte-identical**. The only production changes to existing run-path files are the two routers' dependency swap (Task 6). Existing service-level test files are NOT modified.
- **Fingerprint reuse (binding):** the ONLY new hashing code is `fingerprint_chapter_texts()` inside `packages/core/narrare_core/ai_invocation/correlation.py`, calling the existing `_hash_payload` (ADR-045 scheme: SHA-256 + canonical JSON + `narrare:adr045:v1` domain separator — file `correlation.py`, `_hash_payload` at the module tail). No other hash utility may be introduced (not `hashlib` elsewhere, not `embeddings/hash.py`). Digest is 64 hex chars; the raw prose is NEVER stored — only the digest.
- **Deterministic fingerprint inputs (binding):** chapter texts come from `ChapterRepositoryProtocol.list_by_novel(novel_id)` (contract: position-ordered) filtered to non-empty prose — the exact read path + filter of `SeriesConsistencyService.check_novel` step 4 (`[c.content for c in chapters if (c.content or "").strip()]`). Store-time and GET-time use the SAME helper in `SeriesDriftPersistenceService` — no second computation path.
- **RULE-14 atomic migration:** `0040_series_drift_results` (down_revision `0039_series_voice` — verified latest) lands in the SAME task batch as the ORM model (`series_drift_models.py`); upgrade = one `create_table`, downgrade = one `drop_table`. No `Base.metadata.create_all()` anywhere. Any test that downgrades/upgrades the shared test DB carries `@pytest.mark.schema_mutating` at MODULE level (the schema guard `tests/_schema_guard.py` detects DDL AST-wide) and restores head in a `finally`.
- **Configurable-defaults checker:** no new module-/class-level numeric literals > 5 (string lengths like `String(length=64)` and call arguments are fine; the checker targets numeric constants).
- **Regression-first TDD:** every new test is written and run (expected FAIL) before the implementation step that satisfies it.
- **Commits:** implementer edits + runs gates, then reports; **Platform specialist commits with the verbatim message in each task's commit step**. No `--no-verify`/`-n`, no push. On hook failure: STOP and report. The pre-commit **openapi-regenerate** hook will auto-stage `docs/reference/openapi.json` changes when Task 6 alters the API surface — let it ride along; NEVER hand-edit `openapi.json`.
- **Language / locating:** English everywhere (code, comments, tests, commit messages; i18n message FILES excepted — en/de/fr values). Locate edit targets by semantic name/text (the code blocks below quote the current text) — never by line number. Where a task says "rg sweep", run the given `rg` command and mechanically update every match.
- **Anti-enumeration / ownership (siblings' contract):** a missing series, a not-owned series, AND a novel not belonging to the series ALL surface as `ForbiddenError` (HTTP 403) — never 404 — inside the service, so the contract holds from non-request contexts too.
- **RULE-11 persistence degradation (documented ruling):** the run endpoints' primary deliverable is the analysis (the LLM cost is already paid when the store runs). If the drift-result store write raises, the wrapper logs a `series_drift_persist_failed` warning and still returns the computed result — mirroring `SeriesVoiceDriftService._load_series_voice`'s malformed-JSONB degradation. The GET path propagates errors normally. This is a documented, tested degradation — not a silent catch (structlog warning with error detail). The degradation is **server-log-only, NOT user-surfaced**: the POST response is byte-identical to the success path (no flag, no error field), and the author discovers the unpersisted state only on the next panel re-open, where the GET returns the 200 all-null empty state — the same warning-only surface as the existing `series_voice_drift_malformed_json` case.
- **i18n:** 3 locales × the new `series.drift.snapshot.*` keys in `packages/i18n/messages/{en,de,fr}/studio.json`, inside the existing `series.drift` object (key parity across locales is enforced by the i18n pre-commit hook).
- **Test commands:** backend focused runs via `just test-file <path>`; per-task backend gate `just test-unit` (use `just test-lowmem` on <12 GB RAM machines). Integration (Tasks 2 + 4) via `just test-file <path>` (needs the Docker test DB; `just _ensure-services` if down). Frontend: `cd packages/web && pnpm test <path-filter>` (scoped), `pnpm type-check`, `pnpm lint:check`; frontend gate `just test-frontend`. Architecture checker: `just check-architecture`. Slice-final gates (Task 10): `just check-architecture`, `just typecheck`, `just lint-check`, `just test-unit`, `just test-integration`, frontend `pnpm type-check` + `pnpm lint:check`, `just test-frontend`.
- **Design-interpretation rulings (locked for this plan — read before executing):**
  1. **"ONE JSON document" + parallel runs.** The design stores canon conflicts AND voice drift as one JSON document, but the two checks are SEPARATE POSTs the panel fires in parallel. Ruling: ONE JSONB column `result` holding the composite document with exactly the keys `consistency` and `voice_drift`; each run upserts ONLY its own key via a PostgreSQL `INSERT … ON CONFLICT (novel_id) DO UPDATE` with a JSONB shallow-merge (`result = series_drift_results.result || excluded.result`). A wholesale document overwrite would destroy the sibling section (the panel's own usage pattern) — the per-key merge is what "new run overwrites" means at section granularity. Atomicity also makes the parallel panel fire race-free (a naive ORM get-or-create would PK-collide).
  2. **`generated_at` is record-level** (the design's singular timestamp): refreshed by whichever check wrote last. The response docstring states this explicitly; per-section timestamps are YAGNI (the staleness signal is the fingerprint, not age). Honest residual of the record-level fingerprint: if the band's texts are edited between two check runs, the later write's fingerprint masks the older sibling section — the GET reports `stale: false` while one section predates the edit (faithful to the design's single-fingerprint model, carried into the ADR-079 amendment).
  3. **Stale semantics.** `stale = stored_input_fingerprint != fingerprint(current chapter texts)`. When no record exists, the GET returns `generated_at: null`, both sections `null`, `stale: false` (nothing persisted can be stale — a 200-with-null snapshot, NOT a 404; the panel treats it as the empty state without error-channel special-casing).
  4. **Graceful-skip results are persisted too** (empty conflicts / `no_profile` are valid analysis outcomes — storing them is what makes the snapshot honest).
  5. **Fingerprint scope = the whole band.** A `chapter_ids`-filtered voice-drift run still fingerprints the band's full chapter-text list (the design hashes "the band's chapter texts"; the band is the staleness unit).

---

### Task 1: Core — `fingerprint_chapter_texts` (ADR-045 scheme reuse)

**Files:**
- Modify: `packages/core/narrare_core/ai_invocation/correlation.py` (170/400 lines — headroom verified)
- Test: `tests/unit/core/ai_invocation/test_correlation_chapter_fingerprint.py` (new)

**Interfaces:**
- Consumes: `_hash_payload` (existing, same module — the ADR-045 hashing utility, SHA-256 over canonical JSON with the `narrare:adr045:v1` domain separator).
- Produces (verbatim for Task 5): `fingerprint_chapter_texts(chapter_texts: Sequence[str]) -> str` exported from `narrare_core.ai_invocation.correlation` — 64-hex digest over `{"kind": "series_drift_chapter_texts", "chapter_texts": [...]}` via `_hash_payload`.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/core/ai_invocation/test_correlation_chapter_fingerprint.py`:

```python
"""Tests for fingerprint_chapter_texts (C2 — drift-persistence staleness).

Pins the ADR-045 scheme reuse: the digest is exactly ``_hash_payload`` over a
kind-discriminated payload (no new hash scheme), deterministic for identical
ordered input, order-sensitive, and valid for the empty band.
"""

from __future__ import annotations

from collections.abc import Sequence

from narrare_core.ai_invocation.correlation import (
    _hash_payload,
    fingerprint_chapter_texts,
)


class TestFingerprintChapterTexts:
    def test_deterministic_for_same_ordered_inputs(self) -> None:
        texts: Sequence[str] = ["Alpha prose.", "Beta prose.", "Gamma prose."]

        assert fingerprint_chapter_texts(texts) == fingerprint_chapter_texts(
            list(texts)
        )

    def test_order_sensitive(self) -> None:
        """Chapter order is load-bearing (list_by_novel position order)."""
        first = fingerprint_chapter_texts(["Alpha.", "Beta."])
        second = fingerprint_chapter_texts(["Beta.", "Alpha."])

        assert first != second

    def test_content_sensitive(self) -> None:
        assert fingerprint_chapter_texts(["One."]) != fingerprint_chapter_texts(
            ["One. Edited."]
        )

    def test_empty_list_is_valid_and_stable(self) -> None:
        assert fingerprint_chapter_texts([]) == fingerprint_chapter_texts([])

    def test_reuses_adr045_hash_payload_scheme(self) -> None:
        """The digest IS _hash_payload over the kind-discriminated payload —
        the ADR-045 correlation scheme, applied to a new payload shape."""
        digest = fingerprint_chapter_texts(["Alpha.", "Beta."])

        expected = _hash_payload(
            {
                "kind": "series_drift_chapter_texts",
                "chapter_texts": ["Alpha.", "Beta."],
            }
        )
        assert digest == expected

    def test_kind_discriminator_separates_domains(self) -> None:
        """A drift digest never equals a bare payload digest of the same texts
        (no accidental cross-context collision)."""
        texts = ["Alpha.", "Beta."]

        assert fingerprint_chapter_texts(texts) != _hash_payload(list(texts))

    def test_digest_is_64_hex_chars(self) -> None:
        digest = fingerprint_chapter_texts(["Alpha."])

        assert len(digest) == 64
        int(digest, 16)  # hex-decodable
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `just test-file tests/unit/core/ai_invocation/test_correlation_chapter_fingerprint.py`
Expected: FAIL — `ImportError: cannot import name 'fingerprint_chapter_texts'`.

- [ ] **Step 3: Implement the fingerprint function**

In `packages/core/narrare_core/ai_invocation/correlation.py`:

3a. Directly after the `if TYPE_CHECKING:` line (before the existing `from narrare_core.ai_invocation.budgets import OutputBudgetDecision` import), insert:

```python
    from collections.abc import Sequence
```

3b. Directly BEFORE the `def _hash_payload(payload: object) -> str:` definition (the module tail), insert:

```python
def fingerprint_chapter_texts(chapter_texts: Sequence[str]) -> str:
    """Privacy-safe staleness fingerprint over a band's ordered chapter texts.

    C2 drift persistence (SERIES-004 Slice 6): reuses the ADR-045 fingerprint
    scheme (:func:`_hash_payload` — SHA-256 over canonical JSON with the
    ``narrare:adr045:v1`` domain separator) — **no new hash scheme**. The
    ``kind`` discriminator keeps drift-staleness digests distinct from
    invocation-correlation digests. Determinism requires callers to pass the
    texts in a stable order with a stable filter: backend callers use
    ``ChapterRepository.list_by_novel`` (position order) filtered to non-empty
    prose — the exact inputs ``SeriesConsistencyService`` analyses. Only the
    digest is persisted; raw prose never is.
    """
    return _hash_payload(
        {"kind": "series_drift_chapter_texts", "chapter_texts": list(chapter_texts)}
    )
```

- [ ] **Step 4: Run the fingerprint tests to verify they pass**

Run: `just test-file tests/unit/core/ai_invocation/test_correlation_chapter_fingerprint.py`
Expected: PASS — 7 tests.

- [ ] **Step 5: Run the existing correlation suites to prove no regression**

Run: `just test-file tests/unit/core/ai_invocation/`
Expected: PASS — the new function is purely additive (`_hash_payload` and its callers are untouched).

- [ ] **Step 6: Commit (via Platform, verbatim)**

```bash
git add packages/core/narrare_core/ai_invocation/correlation.py \
        tests/unit/core/ai_invocation/test_correlation_chapter_fingerprint.py
```

Commit message:

```
feat(core): add fingerprint_chapter_texts — drift staleness fingerprint

C2 (Post-Export Follow-ups program, design §5): the drift-persistence
stale flag needs a hash over the band's chapter texts at save time that
GET can recompute and compare.

- fingerprint_chapter_texts(chapter_texts) -> 64-hex digest, added to the
  ADR-045 correlation module and built ON the existing _hash_payload
  (SHA-256 + canonical JSON + "narrare:adr045:v1" domain separator) —
  the binding is REUSE of the evidence-pipeline fingerprint precedent,
  no new hash scheme. A "kind": "series_drift_chapter_texts" payload
  discriminator separates the domains.
- Determinism contract: callers pass list_by_novel position-ordered
  texts filtered to non-empty prose (the SeriesConsistencyService read
  path). Only the digest is persisted — raw prose never is.

Tests: determinism, order/content sensitivity, empty band, scheme pin
against _hash_payload, domain separation, digest shape.

Refs: docs/superpowers/specs/2026-08-14-post-export-followups-design.md §5 (C2), ADR-045
```

---

### Task 2: Migration 0040 + ORM model (RULE-14 atomic)

**Files:**
- Create: `apps/api/narrare/series/series_drift_models.py`
- Create: `apps/api/alembic/versions/0040_series_drift_results.py`
- Test: `tests/integration/test_migration_0040_round_trip.py` (new)

**Interfaces:**
- Consumes: nothing from Task 1 (the model stores the digest as an opaque string).
- Produces (verbatim for Tasks 3–5): `SeriesDriftResult` ORM class, table `series_drift_results`, columns `novel_id` (UUID PK + unique + FK `novels.id` CASCADE), `result` (JSONB NOT NULL, ORM default `dict`), `input_fingerprint` (`String(64)` NOT NULL), `generated_at` (`DateTime(timezone=True)` NOT NULL, `server_default=func.now()`).

- [ ] **Step 1: Write the round-trip integration test (fail-first)**

Create `tests/integration/test_migration_0040_round_trip.py` (mirrors `test_migration_0037_round_trip.py` — subprocess alembic + own connections + `finally` restore head + `schema_mutating` serial phase). The test lands BEFORE the model + migration (regression-first): with neither file existing, the Step-2 run must fail on the missing table.

```python
"""Round-trip safety test for migration 0040 (C2 — drift persistence).

Verifies the 0040 upgrade/downgrade is round-trip safe: with a seeded
``series_drift_results`` row present, downgrading to the parent revision
(0039) drops the table with its rows, and re-upgrading rebuilds the schema.
Uses subprocess alembic + its own connections (NOT the rolled-back
``db_session``, which assumes head) and always restores head in a
``finally``.

NOTE: mutates the shared test DB schema mid-run; the ``finally`` always
restores head. Carries ``@pytest.mark.schema_mutating`` so ``just test`` and
CI run it in a dedicated SERIAL phase — it must never run concurrently with
other tests.
"""

from __future__ import annotations

import os
import subprocess
import uuid as _uuid
from pathlib import Path

import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine
from sqlalchemy.pool import NullPool as _NullPool

# The parent revision: downgrading to it applies ONLY 0040's downgrade (the
# focused round-trip under test), rather than ``base``.
_PARENT_REVISION = "0039_series_voice"


def _alembic_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "apps" / "api" / "alembic"


def _run_alembic(*args: str) -> None:
    """Run an alembic command against the test DB (mirrors integration conftest)."""
    alembic_dir = _alembic_dir()
    alembic_ini = alembic_dir.parent / "alembic.ini"
    db_url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://narrare:narrare@localhost:5433/narrare_test",
    )
    env = {**os.environ, "DATABASE_URL": db_url, "PGOPTIONS": "-c lock_timeout=10s"}
    subprocess.run(
        [
            "python",
            "-m",
            "alembic",
            "-c",
            str(alembic_ini) if alembic_ini.exists() else "alembic.ini",
            *args,
        ],
        env=env,
        cwd=alembic_dir.parent,
        check=True,
        capture_output=True,
    )


async def _table_exists(conn: sqlalchemy.ext.asyncio.AsyncConnection) -> bool:
    return bool(
        (
            await conn.execute(
                sqlalchemy.text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                    "WHERE table_name = 'series_drift_results')"
                )
            )
        ).scalar()
    )


@pytest.mark.schema_mutating
class TestMigration0040RoundTrip:
    """The 0040 upgrade/downgrade is round-trip safe with a seeded row."""

    async def test_seed_drift_row_then_downgrade_then_upgrade(self) -> None:
        db_url = os.environ.get(
            "TEST_DATABASE_URL",
            "postgresql+asyncpg://narrare:narrare@localhost:5433/narrare_test",
        )

        # 1. Ensure we start at head (0040 applied).
        _run_alembic("upgrade", "head")

        # 2. Seed user + novel + one drift row (the data shape 0040 owns).
        user_id = _uuid.uuid4()
        novel_id = _uuid.uuid4()
        eng = _create_async_engine(db_url, poolclass=_NullPool)
        try:
            async with eng.begin() as conn:
                await conn.execute(
                    sqlalchemy.text(
                        "INSERT INTO users (id, email, hashed_password, created_at, updated_at) "
                        "VALUES (:id, :email, 'fake_hash', now(), now())"
                    ),
                    {"id": user_id, "email": f"u-{user_id.hex[:10]}@example.com"},
                )
                await conn.execute(
                    sqlalchemy.text(
                        "INSERT INTO novels (id, user_id, title, author, genre, "
                        "writing_language, tone, story_structure, logline, synopsis, is_demo) "
                        "VALUES (:id, :uid, 'RT Novel', '', '', 'en', '', 'three_act', '', '', false)"
                    ),
                    {"id": novel_id, "uid": user_id},
                )
                await conn.execute(
                    sqlalchemy.text(
                        "INSERT INTO series_drift_results (novel_id, result, input_fingerprint) "
                        "VALUES (:nid, '{\"consistency\": {\"summary\": \"rt\"}}'::jsonb, :fp)"
                    ),
                    {"nid": novel_id, "fp": "a" * 64},
                )
                assert (
                    await conn.execute(
                        sqlalchemy.text("SELECT COUNT(*) FROM series_drift_results")
                    )
                ).scalar() == 1
        finally:
            await eng.dispose()

        try:
            # 3. Downgrade to the parent revision — drops the table with its rows.
            _run_alembic("downgrade", _PARENT_REVISION)

            eng = _create_async_engine(db_url, poolclass=_NullPool)
            try:
                async with eng.begin() as conn:
                    assert not await _table_exists(conn), "table must be gone after downgrade"
            finally:
                await eng.dispose()

            # 4. Upgrade back to head — rebuilds the table (rows do not return:
            #    derived analysis artifacts, safe to lose).
            _run_alembic("upgrade", "head")

            eng = _create_async_engine(db_url, poolclass=_NullPool)
            try:
                async with eng.begin() as conn:
                    assert await _table_exists(conn), "table must exist at head"
                    count = (
                        await conn.execute(
                            sqlalchemy.text("SELECT COUNT(*) FROM series_drift_results")
                        )
                    ).scalar()
                    assert count == 0, "seeded rows do not survive the round trip"
            finally:
                await eng.dispose()
        finally:
            # Safety net: ALWAYS leave the shared test DB at head.
            _run_alembic("upgrade", "head")
```

> **Note on the raw-SQL novel insert:** the `novels` NOT NULL columns beyond id/user_id/title (`author`, `genre`, `writing_language`, `tone`, `story_structure`, `logline`, `synopsis`, `is_demo`) carry ORM-level Python defaults but NO server defaults, so a raw insert must supply them explicitly (values above). If the INSERT fails with a different NOT NULL violation, run `rg -n "nullable=False" apps/api/narrare/novels/models.py` and add the missing column to BOTH raw-SQL inserts in this test file and in Task 4's seeder.

- [ ] **Step 2: Run the round-trip test — expected FAIL (missing table)**

Run: `just test-file tests/integration/test_migration_0040_round_trip.py`
Expected: FAIL — the seed INSERT fails with an undefined-table error (`relation "series_drift_results" does not exist`): migration 0040 does not exist yet, so alembic head is 0039 and the table is absent. Requires the Docker test DB (`just _ensure-services` if needed). This failing run satisfies the regression-first rule; Steps 3–4 create the model + migration and the Step-5 rerun turns the test green.

- [ ] **Step 3: Create the ORM model**

Create `apps/api/narrare/series/series_drift_models.py`:

```python
"""SeriesDriftResult SQLAlchemy model (SERIES-004 Slice 6 — C2 drift persistence).

A ``SeriesDriftResult`` is the LATEST persisted drift snapshot for one novel
(band): canon-contradiction result AND series-voice-drift result as ONE
composite JSON document. It is a strict 1:1 companion to ``Novel``
(``novel_id`` is both the primary key and the unique key — the
``band_summaries`` pattern), enforcing the latest-wins history model:
exactly one record per novel, new runs overwrite their section, no history
rows.

``result`` holds the keys ``consistency`` (a serialized
``SeriesConsistencyCheckResponse``) and ``voice_drift`` (a serialized
``AuthorVoiceDriftResponse``); each check run upserts only its own key (the
repository's atomic JSONB-merge upsert — the panel fires both checks in
parallel). ``input_fingerprint`` is the privacy-safe ADR-045-scheme digest
over the band's chapter texts at write time; ``generated_at`` stamps the
last completed write of either check.

This model is intentionally separate from ``series/models.py`` (RULE-06: one
responsibility per file) — that file owns series membership/settings, while
persisted drift snapshots are a Slice-6 persistence concern (the
``band_summary_models.py`` precedent).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from narrare._app.database import Base


class SeriesDriftResult(Base):
    """Latest persisted drift snapshot for one novel (1:1 to Novel).

    ``novel_id`` is the primary key (and unique), enforcing the latest-wins
    model. Deletion cascades from the novel, so a deleted novel takes its
    snapshot with it.
    """

    __tablename__ = "series_drift_results"

    novel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("novels.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        primary_key=True,
    )
    result: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    input_fingerprint: Mapped[str] = mapped_column(String(length=64), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"SeriesDriftResult(novel_id={self.novel_id})"
```

- [ ] **Step 4: Create migration 0040**

Create `apps/api/alembic/versions/0040_series_drift_results.py`:

```python
"""series_drift_results table (SERIES-004 Slice 6 — C2 drift persistence).

Creates the latest-wins persistence target for the SERIES-004 cross-novel
drift checks: ONE record per novel (``novel_id`` PK + UNIQUE + FK
``novels.id ON DELETE CASCADE`` — the ``band_summaries`` 1:1 pattern from
0038), holding the composite JSON document (canon conflicts + voice drift as
serialized run-result models) plus the ADR-045-scheme input fingerprint and
the record-level ``generated_at``.

``result`` gets a ``server_default`` of empty jsonb so non-ORM inserts
(backfill tooling) succeed; ORM-initiated inserts carry the matching Python
``default=dict`` (mirroring the 0038/0039 server_default backfill convention).

RULE-14: this migration lands in the SAME task batch as the
``SeriesDriftResult`` model change. A model change without a migration is a
build failure. The upgrade/downgrade pair is atomic: one create_table vs one
drop_table — symmetric by construction.

See:
    docs/superpowers/specs/2026-08-14-post-export-followups-design.md §5 (C2).
    ADR-079 — Series Cross-Novel Drift (Slice 6 amendment).
    0038_band_summaries — the 1:1 novel-companion table pattern mirrored here.

Revision ID: 0040_series_drift_results
Revises: 0039_series_voice
Create Date: 2026-08-16 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0040_series_drift_results"
down_revision: str | None = "0039_series_voice"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── series_drift_results table (1:1 to novels, novel_id IS the PK) ──────
    op.create_table(
        "series_drift_results",
        sa.Column(
            "novel_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("novels.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            primary_key=True,
        ),
        sa.Column(
            "result",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    # Reverse of upgrade(): drop the drift-snapshot table (rows are derived
    # analysis artifacts — safe to lose on downgrade, mirrors 0038).
    op.drop_table("series_drift_results")
```

- [ ] **Step 5: Run the round-trip test**

Run: `just test-file tests/integration/test_migration_0040_round_trip.py`
Expected: PASS (requires the Docker test DB; `just _ensure-services` if needed).

- [ ] **Step 6: Run the existing integration round-trip for regressions**

Run: `just test-file tests/integration/test_migration_0037_round_trip.py`
Expected: PASS — 0040 chains onto 0039 without disturbing earlier round-trips.

- [ ] **Step 7: Commit (via Platform, verbatim)**

```bash
git add apps/api/narrare/series/series_drift_models.py \
        apps/api/alembic/versions/0040_series_drift_results.py \
        tests/integration/test_migration_0040_round_trip.py
```

Commit message:

```
feat(api/series): add series_drift_results table — migration 0040 + model

C2 (design §5): the persistence target for the SERIES-004 drift checks.
Latest-wins — exactly one record per novel (novel_id PK + UNIQUE + FK
novels.id CASCADE, the band_summaries 1:1 pattern from 0038).

- series_drift_models.SeriesDriftResult: novel_id PK; result JSONB (the
  composite document — serialized SeriesConsistencyCheckResponse under
  "consistency" + AuthorVoiceDriftResponse under "voice_drift"); the
  64-char ADR-045-scheme input fingerprint; record-level generated_at
  (server_default now, mirroring the 0038/0039 backfill convention).
- Migration 0040_series_drift_results (down_revision 0039_series_voice):
  atomic RULE-14 pair — one create_table / one drop_table; result gets a
  server_default of empty jsonb for non-ORM inserts.
- Round-trip integration test (schema_mutating serial phase): seed a row,
  downgrade to 0039 (table + rows gone), re-upgrade (schema back, derived
  rows do not return), finally always restores head.

Refs: docs/superpowers/specs/2026-08-14-post-export-followups-design.md §5 (C2), ADR-079 (Slice 6 amendment), ADR-077 (band_summaries pattern)
```

---

### Task 3: Drift-persistence contracts + snapshot schema + fake (contract-first, untouchable after)

**Files:**
- Create: `apps/api/narrare/series/series_drift_contracts.py`
- Create: `apps/api/narrare/series/series_drift_schemas.py`
- Create: `tests/fakes/fake_series_drift_repo.py`
- Test: `tests/unit/api/series/test_series_drift_contracts.py` (new)

**Interfaces:**
- Consumes: `SeriesDriftResult` (Task 2); `SeriesConsistencyCheckResponse` (`narrare.series.series_consistency_schemas`); `AuthorVoiceDriftResponse` / `AuthorVoiceDriftRequest` (`narrare.analysis.schemas_author_voice_drift`).
- Produces (verbatim for Tasks 4–6 — untouchable after this task):
  - `DriftSection = Literal["consistency", "voice_drift"]` (in contracts).
  - `SeriesDriftRepositoryProtocol` — `async get(novel_id: uuid.UUID) -> SeriesDriftResult | None`; `async store_section(novel_id: uuid.UUID, *, section: DriftSection, document: dict, fingerprint: str) -> None`.
  - `SeriesDriftPersistenceServiceProtocol` — `async check_and_store_consistency(series_id, novel_id, user_id) -> SeriesConsistencyCheckResponse`; `async check_and_store_voice_drift(series_id, novel_id, user_id, request: AuthorVoiceDriftRequest) -> AuthorVoiceDriftResponse`; `async get_snapshot(series_id, novel_id, user_id) -> SeriesDriftSnapshotResponse`.
  - `SeriesDriftSnapshotResponse(BaseModel)` — fields `series_id: uuid.UUID`, `novel_id: uuid.UUID`, `generated_at: datetime | None`, `stale: bool`, `consistency: SeriesConsistencyCheckResponse | None`, `voice_drift: AuthorVoiceDriftResponse | None`.
  - `FakeSeriesDriftRepository` (tests/fakes) — in-memory, `seed(*rows)`, `store_section` mirrors the merge semantics, `raise_on_store` test hook, `calls` + assertion helpers.

- [ ] **Step 1: Write the failing contract tests**

Create `tests/unit/api/series/test_series_drift_contracts.py`:

```python
"""Contract tests for the C2 drift-persistence surface (RULE-03).

Pins the repository + persistence-service Protocols and the snapshot
response schema BEFORE the implementations (the contract files are
untouchable for the remainder of the slice).
"""

from __future__ import annotations

import typing
from datetime import UTC, datetime

from narrare.series.series_drift_contracts import (
    DriftSection,
    SeriesDriftPersistenceServiceProtocol,
    SeriesDriftRepositoryProtocol,
)
from narrare.series.series_drift_schemas import SeriesDriftSnapshotResponse


class TestDriftSection:
    def test_literal_members(self) -> None:
        # Typing-time contract; the runtime set mirrors the JSONB keys.
        args = typing.get_args(DriftSection)
        assert set(args) == {"consistency", "voice_drift"}


class TestSnapshotSchema:
    def test_holds_both_sections_plus_staleness(self) -> None:
        response = SeriesDriftSnapshotResponse(
            series_id="00000000-0000-0000-0000-000000000001",
            novel_id="00000000-0000-0000-0000-000000000002",
            generated_at=datetime(2026, 8, 16, 12, 0, tzinfo=UTC),
            stale=True,
            consistency=None,
            voice_drift=None,
        )
        assert response.stale is True
        assert response.consistency is None
        assert response.voice_drift is None

    def test_empty_snapshot_shape(self) -> None:
        response = SeriesDriftSnapshotResponse(
            series_id="00000000-0000-0000-0000-000000000001",
            novel_id="00000000-0000-0000-0000-000000000002",
            generated_at=None,
            stale=False,
            consistency=None,
            voice_drift=None,
        )
        assert response.generated_at is None

    def test_sections_carry_the_run_result_models(self) -> None:
        from narrare.analysis.schemas_author_voice_drift import (
            AuthorVoiceDriftResponse,
        )
        from narrare.series.series_consistency_schemas import (
            SeriesConsistencyCheckResponse,
        )

        consistency = SeriesConsistencyCheckResponse(
            series_id="00000000-0000-0000-0000-000000000001",
            novel_id="00000000-0000-0000-0000-000000000002",
        )
        voice = AuthorVoiceDriftResponse(novel_id="00000000-0000-0000-0000-000000000002")
        response = SeriesDriftSnapshotResponse(
            series_id=consistency.series_id,
            novel_id=consistency.novel_id,
            generated_at=None,
            stale=False,
            consistency=consistency,
            voice_drift=voice,
        )
        assert response.consistency is consistency
        assert response.voice_drift is voice


class TestProtocols:
    def test_repository_protocol_surface(self) -> None:
        for method in ("get", "store_section"):
            assert hasattr(SeriesDriftRepositoryProtocol, method)

    def test_service_protocol_surface(self) -> None:
        for method in (
            "check_and_store_consistency",
            "check_and_store_voice_drift",
            "get_snapshot",
        ):
            assert hasattr(SeriesDriftPersistenceServiceProtocol, method)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `just test-file tests/unit/api/series/test_series_drift_contracts.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'narrare.series.series_drift_contracts'`.

- [ ] **Step 3: Create the contracts file**

Create `apps/api/narrare/series/series_drift_contracts.py`:

```python
"""Contracts for C2 drift persistence (SERIES-004 Slice 6 — RULE-03 first).

Two Protocols fix the persistence surface before any implementation:

- :class:`SeriesDriftRepositoryProtocol` — the ``series_drift_results`` query
  surface. ``store_section`` is an ATOMIC per-section upsert: it merges its
  ``section`` key into the composite JSON document (JSONB ``||``) and
  refreshes the fingerprint + ``generated_at``, so the panel's two parallel
  check POSTs never PK-collide and never clobber each other's section.
- :class:`SeriesDriftPersistenceServiceProtocol` — the wrapper orchestration:
  run a check via the UNCHANGED run services, persist the result, return it
  verbatim; plus the snapshot read with staleness.

Ownership contract (mirrors ``SeriesConsistencyServiceProtocol``):
``get_snapshot`` verifies the caller owns the series AND the novel belongs to
it BEFORE any read; missing/not-owned/non-member ALL surface as
``ForbiddenError`` (HTTP 403, anti-enumeration — never 404). The
``check_and_store_*`` methods inherit verification from the wrapped run
services (they raise before any store happens).

RULE-04: separate file because ``series/contracts.py`` is at its 200-line
limit (``band_summary_contracts.py`` precedent).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid

    from narrare.analysis.schemas_author_voice_drift import (
        AuthorVoiceDriftRequest,
        AuthorVoiceDriftResponse,
    )
    from narrare.series.series_consistency_schemas import (
        SeriesConsistencyCheckResponse,
    )
    from narrare.series.series_drift_models import SeriesDriftResult
    from narrare.series.series_drift_schemas import SeriesDriftSnapshotResponse

DriftSection = Literal["consistency", "voice_drift"]
"""The two composite-document keys — one per check run."""


@runtime_checkable
class SeriesDriftRepositoryProtocol(Protocol):
    """Query surface for the ``series_drift_results`` table (1:1 to Novel)."""

    async def get(self, novel_id: uuid.UUID) -> SeriesDriftResult | None:
        """Load the persisted snapshot row for a novel (``None`` if none)."""
        ...


    async def store_section(
        self,
        novel_id: uuid.UUID,
        *,
        section: DriftSection,
        document: dict,
        fingerprint: str,
    ) -> None:
        """Atomically upsert ONE section of the composite document.

        Merges ``document`` under ``result[section]`` (JSONB shallow merge),
        sets ``input_fingerprint`` to the save-time fingerprint, and refreshes
        record-level ``generated_at``. Safe under concurrency (ON CONFLICT).
        """
        ...


@runtime_checkable
class SeriesDriftPersistenceServiceProtocol(Protocol):
    """Run-then-persist orchestration + snapshot read (C2)."""

    async def check_and_store_consistency(
        self, series_id: uuid.UUID, novel_id: uuid.UUID, user_id: uuid.UUID
    ) -> SeriesConsistencyCheckResponse:
        """Run the canon-contradiction check, persist its section, return it.

        Delegates to the UNCHANGED ``SeriesConsistencyService.check_novel``
        (ownership + membership verified there — a 403 raises BEFORE any
        store). The response is returned verbatim even when the store write
        degrades (RULE-11 — see the service docstring).
        """
        ...


    async def check_and_store_voice_drift(
        self,
        series_id: uuid.UUID,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        request: AuthorVoiceDriftRequest,
    ) -> AuthorVoiceDriftResponse:
        """Run the series-voice-drift check, persist its section, return it.

        Same contract as :meth:`check_and_store_consistency`, delegating to
        the UNCHANGED ``SeriesVoiceDriftService.check``.
        """
        ...


    async def get_snapshot(
        self, series_id: uuid.UUID, novel_id: uuid.UUID, user_id: uuid.UUID
    ) -> SeriesDriftSnapshotResponse:
        """Read the persisted snapshot with the staleness flag.

        Recomputes the current chapter-texts fingerprint and compares it with
        the stored one: ``stale=True`` means the band's texts changed since
        the last completed write. No record → all-null snapshot with
        ``stale=False`` (never an error). Missing/not-owned series and
        non-member novel → ``ForbiddenError`` (403, anti-enumeration).
        """
        ...
```

- [ ] **Step 4: Create the schemas file**

Create `apps/api/narrare/series/series_drift_schemas.py`:

```python
"""Snapshot schema for C2 drift persistence (SERIES-004 Slice 6).

One response backs ``GET /api/v1/series/{series_id}/consistency/{novel_id}``.
The sections REUSE the existing run-result models verbatim (RULE-22 — the
stored JSON serializes THOSE models; no re-shaping): ``consistency`` is a
``SeriesConsistencyCheckResponse``, ``voice_drift`` an
``AuthorVoiceDriftResponse``.

RULE-04: separate file because ``series/schemas.py`` is at its 200-line
limit (``series_voice_schemas.py`` precedent).
"""

from __future__ import annotations

import uuid  # noqa: TC003 - needed at runtime for Pydantic model resolution
from datetime import datetime

from pydantic import BaseModel

# Runtime imports (not TYPE_CHECKING): these are Pydantic field types —
# Pydantic resolves field annotations at class-definition time. noqa: TC001
# (mirrors series_consistency_schemas importing CanonConflict).
from narrare.analysis.schemas_author_voice_drift import (  # noqa: TC001
    AuthorVoiceDriftResponse,
)
from narrare.series.series_consistency_schemas import (  # noqa: TC001
    SeriesConsistencyCheckResponse,
)


class SeriesDriftSnapshotResponse(BaseModel):
    """GET /api/v1/series/{series_id}/consistency/{novel_id} response.

    The persisted latest-wins snapshot for one band, fetched as ONE document
    with the staleness verdict.

    Attributes:
        series_id: The series whose checks produced the snapshot.
        novel_id: The novel (band) the snapshot belongs to.
        generated_at: Record-level timestamp of the LAST completed write of
            either check (refreshed on every section upsert — the design's
            singular ``generated_at``). ``None`` when nothing is persisted.
        stale: ``True`` when the band's current chapter-texts fingerprint
            differs from the fingerprint stored at save time — the results
            predate text edits. Always ``False`` when nothing is persisted.
        consistency: The persisted canon-contradiction result (``None`` when
            that check never completed a run for this band).
        voice_drift: The persisted series-voice-drift result (``None`` when
            that check never completed a run for this band).
    """

    series_id: uuid.UUID
    novel_id: uuid.UUID
    generated_at: datetime | None
    stale: bool
    consistency: SeriesConsistencyCheckResponse | None
    voice_drift: AuthorVoiceDriftResponse | None
```

- [ ] **Step 5: Create the fake repository**

Create `tests/fakes/fake_series_drift_repo.py`:

```python
"""Fake SeriesDrift repository for unit tests (ADR-030 — Fake-based).

Implements ``SeriesDriftRepositoryProtocol`` with in-memory storage keyed by
``novel_id``. ``store_section`` mirrors the real repository's semantics:
per-section document merge (shallow dict merge under ``result[section]``),
fingerprint overwrite, ``generated_at`` refresh. Records every call.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from narrare.series.series_drift_models import SeriesDriftResult
from tests.fakes._shared import CallRecord

if TYPE_CHECKING:
    import uuid

    from narrare.series.series_drift_contracts import DriftSection


class FakeSeriesDriftRepository:
    """In-memory fake for ``SeriesDriftRepositoryProtocol``."""

    def __init__(self) -> None:
        self._store: dict[uuid.UUID, SeriesDriftResult] = {}
        self.calls: list[CallRecord] = []
        # Test hook: when set, store_section raises this instead of storing.
        self.raise_on_store: Exception | None = None

    def seed(self, *rows: SeriesDriftResult) -> None:
        """Pre-populate the store with drift-result rows."""
        for row in rows:
            self._store[row.novel_id] = row

    async def get(self, novel_id: uuid.UUID) -> SeriesDriftResult | None:
        self.calls.append(CallRecord("get", kwargs={"novel_id": novel_id}))
        return self._store.get(novel_id)

    async def store_section(
        self,
        novel_id: uuid.UUID,
        *,
        section: DriftSection,
        document: dict,
        fingerprint: str,
    ) -> None:
        self.calls.append(
            CallRecord(
                "store_section",
                kwargs={
                    "novel_id": novel_id,
                    "section": section,
                    "document": document,
                    "fingerprint": fingerprint,
                },
            )
        )
        if self.raise_on_store is not None:
            raise self.raise_on_store
        row = self._store.get(novel_id)
        if row is None:
            row = SeriesDriftResult(novel_id=novel_id, result={})
            self._store[novel_id] = row
        merged = dict(row.result or {})
        merged[section] = document
        row.result = merged
        row.input_fingerprint = fingerprint
        # Stamp generated_at so callers reading it don't hit server defaults.
        row.generated_at = datetime.now(UTC)

    # -- assertion helpers (mirrors fake_band_summary_repo) ----------------

    def call_count(self, method: str) -> int:
        return sum(1 for c in self.calls if c.method == method)

    def assert_called(self, method: str, **kwargs: Any) -> None:
        for call in self.calls:
            if call.method == method and call.matches(kwargs):
                return
        raise AssertionError(f"No call to {method} with {kwargs}")

    def assert_not_called(self, method: str) -> None:
        count = self.call_count(method)
        if count > 0:
            raise AssertionError(f"Expected 0 calls to {method}, got {count}")
```

- [ ] **Step 6: Run the contract tests to verify they pass**

Run: `just test-file tests/unit/api/series/test_series_drift_contracts.py`
Expected: PASS — 7 tests.

- [ ] **Step 7: Run the architecture checker**

Run: `just check-architecture`
Expected: PASS (new files under their contracts/schemas size limits; import direction one-way).

- [ ] **Step 8: Commit (via Platform, verbatim)**

```bash
git add apps/api/narrare/series/series_drift_contracts.py \
        apps/api/narrare/series/series_drift_schemas.py \
        tests/fakes/fake_series_drift_repo.py \
        tests/unit/api/series/test_series_drift_contracts.py
```

Commit message:

```
feat(api/series): add drift-persistence contracts + snapshot schema + fake

C2 contract-first step (RULE-03): the persistence surface authored before
the repository/service implementations. Contract files are untouchable for
the remainder of the C2 slice.

- series_drift_contracts.py: DriftSection literal ("consistency" |
  "voice_drift" — the composite-document keys); SeriesDriftRepositoryProtocol
  (get + ATOMIC per-section store_section — JSONB merge upsert, concurrency-
  safe for the panel's parallel checks); SeriesDriftPersistenceServiceProtocol
  (check_and_store_consistency / check_and_store_voice_drift / get_snapshot)
  with the module ownership contract (403 anti-enumeration on
  missing/not-owned/non-member, mirroring the run-service siblings).
- series_drift_schemas.py: SeriesDriftSnapshotResponse — ONE snapshot with
  generated_at (record-level, null when nothing persisted), stale, and the
  two sections reusing SeriesConsistencyCheckResponse + AuthorVoiceDriftResponse
  verbatim (RULE-22 — the stored JSON serializes the existing run-result
  models, never re-shaped).
- tests/fakes/fake_series_drift_repo.py: in-memory fake mirroring the merge
  semantics + a raise_on_store hook for the RULE-11 degradation test.

Refs: docs/superpowers/specs/2026-08-14-post-export-followups-design.md §5 (C2)
```

---

### Task 4: Repository — atomic per-section JSONB-merge upsert

**Files:**
- Create: `apps/api/narrare/series/series_drift_repository.py`
- Create: `tests/integration/series/__init__.py` (empty)
- Test: `tests/integration/series/test_series_drift_repository.py` (new)

**Interfaces:**
- Consumes: `SeriesDriftResult` (Task 2); `SeriesDriftRepositoryProtocol` / `DriftSection` (Task 3); `BaseRepository` (`narrare._app.base_repository`).
- Produces (verbatim for Tasks 5–6): `SeriesDriftRepository(session)` with `async get(novel_id) -> SeriesDriftResult | None` and `async store_section(novel_id, *, section, document, fingerprint) -> None` (atomic `ON CONFLICT (novel_id) DO UPDATE` + JSONB `||` merge; satisfies `SeriesDriftRepositoryProtocol`).

- [ ] **Step 1: Write the failing integration tests**

Create `tests/integration/series/__init__.py` (empty) and `tests/integration/series/test_series_drift_repository.py`:

```python
"""Integration tests for SeriesDriftRepository (C2 — design §12 latest-wins gate).

Real PostgreSQL (rolled-back db_session fixture; schema from the real Alembic
chain — RULE-14). Pins the atomic upsert semantics the design's latest-wins
model rests on: per-section merge, sibling survival, fingerprint/generated_at
refresh, and novel-delete cascade.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select, text

from narrare.novels.models import Novel
from narrare.series.series_drift_contracts import SeriesDriftRepositoryProtocol
from narrare.series.series_drift_models import SeriesDriftResult
from narrare.series.series_drift_repository import SeriesDriftRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def _seed_user_and_novel(db_session: AsyncSession) -> Novel:
    """Seed one user + one novel (the novel via ORM — Python-side defaults)."""
    user_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO users (id, email, hashed_password, created_at, updated_at) "
            "VALUES (:id, :email, 'fake_hash', now(), now())"
        ),
        {"id": user_id, "email": f"u-{user_id.hex[:10]}@example.com"},
    )
    novel = Novel(id=uuid.uuid4(), user_id=user_id, title="Repo Test Novel")
    db_session.add(novel)
    await db_session.flush()
    return novel


async def _fetch_row(db_session: AsyncSession) -> SeriesDriftResult:
    return (
        await db_session.execute(select(SeriesDriftResult))
    ).scalar_one()


class TestStoreSection:
    async def test_first_store_creates_row_with_single_section(
        self, db_session: AsyncSession
    ) -> None:
        novel = await _seed_user_and_novel(db_session)
        repo = SeriesDriftRepository(db_session)

        await repo.store_section(
            novel.id,
            section="consistency",
            document={"summary": "first"},
            fingerprint="f" * 64,
        )

        row = await _fetch_row(db_session)
        assert row.novel_id == novel.id
        assert row.result == {"consistency": {"summary": "first"}}
        assert row.input_fingerprint == "f" * 64
        assert row.generated_at is not None

    async def test_sibling_section_merge_survives_parallel_writes(
        self, db_session: AsyncSession
    ) -> None:
        """The composite-document ruling: each run upserts ONLY its key — the
        sibling section from the other parallel check survives."""
        novel = await _seed_user_and_novel(db_session)
        repo = SeriesDriftRepository(db_session)

        await repo.store_section(
            novel.id,
            section="consistency",
            document={"summary": "c1"},
            fingerprint="a" * 64,
        )
        await repo.store_section(
            novel.id,
            section="voice_drift",
            document={"novel_id": str(novel.id)},
            fingerprint="b" * 64,
        )

        row = await _fetch_row(db_session)
        assert set(row.result.keys()) == {"consistency", "voice_drift"}
        assert row.result["consistency"] == {"summary": "c1"}
        assert row.input_fingerprint == "b" * 64  # latest write wins

    async def test_latest_wins_overwrites_own_section_only(
        self, db_session: AsyncSession
    ) -> None:
        """Design §12 gate: latest-wins overwrite — a new run of the SAME
        check replaces its section; the sibling section survives and the
        fingerprint + generated_at refresh."""
        novel = await _seed_user_and_novel(db_session)
        repo = SeriesDriftRepository(db_session)

        await repo.store_section(
            novel.id,
            section="consistency",
            document={"summary": "old"},
            fingerprint="a" * 64,
        )
        first_generated_at = (await _fetch_row(db_session)).generated_at
        await repo.store_section(
            novel.id,
            section="voice_drift",
            document={"novel_id": "x"},
            fingerprint="b" * 64,
        )
        await repo.store_section(
            novel.id,
            section="consistency",
            document={"summary": "new"},
            fingerprint="c" * 64,
        )

        row = await _fetch_row(db_session)
        assert row.result["consistency"] == {"summary": "new"}
        assert row.result["voice_drift"] == {"novel_id": "x"}
        assert row.input_fingerprint == "c" * 64
        assert row.generated_at >= first_generated_at

    async def test_get_returns_row_or_none(self, db_session: AsyncSession) -> None:
        novel = await _seed_user_and_novel(db_session)
        repo = SeriesDriftRepository(db_session)

        assert await repo.get(novel.id) is None

        await repo.store_section(
            novel.id, section="consistency", document={}, fingerprint="a" * 64
        )
        row = await repo.get(novel.id)
        assert row is not None and row.novel_id == novel.id


class TestCascade:
    async def test_deleting_novel_removes_snapshot(
        self, db_session: AsyncSession
    ) -> None:
        novel = await _seed_user_and_novel(db_session)
        repo = SeriesDriftRepository(db_session)
        await repo.store_section(
            novel.id, section="consistency", document={}, fingerprint="a" * 64
        )

        await db_session.delete(novel)
        await db_session.flush()

        assert await repo.get(novel.id) is None


def test_repository_exposes_protocol_surface() -> None:
    """Structural check: the repository carries the Protocol's methods."""
    assert hasattr(SeriesDriftRepository, "get")
    assert hasattr(SeriesDriftRepository, "store_section")
    assert callable(SeriesDriftRepository.store_section)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `just test-file tests/integration/series/test_series_drift_repository.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'narrare.series.series_drift_repository'`.

- [ ] **Step 3: Implement the repository**

Create `apps/api/narrare/series/series_drift_repository.py`:

```python
"""SeriesDrift repository — DB queries only (SERIES-004 Slice 6, C2).

Implements ``SeriesDriftRepositoryProtocol`` (``series_drift_contracts.py``).
Query-only: no business decisions (RULE-06).

``store_section`` is a single atomic PostgreSQL ``INSERT … ON CONFLICT
(novel_id) DO UPDATE``: the composite ``result`` document is merged with a
JSONB shallow concat (``series_drift_results.result || excluded.result``) —
exactly the two top-level keys ``consistency`` / ``voice_drift`` — so the
panel's two PARALLEL check POSTs never PK-collide and never clobber each
other's section. A load-or-create loop here would race (both requests would
INSERT the missing row; one would fail on the PK). ``input_fingerprint`` and
record-level ``generated_at`` are refreshed on every write (latest-wins).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from narrare._app.base_repository import BaseRepository
from narrare.series.series_drift_models import SeriesDriftResult

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.series.series_drift_contracts import DriftSection


class SeriesDriftRepository(BaseRepository):
    """DB-query surface for the ``series_drift_results`` table (1:1 to Novel)."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get(self, novel_id: uuid.UUID) -> SeriesDriftResult | None:
        """Load the persisted snapshot row for a novel (``None`` if no row)."""
        result = await self._session.execute(
            select(SeriesDriftResult).where(SeriesDriftResult.novel_id == novel_id)
        )
        return result.scalar_one_or_none()

    async def store_section(
        self,
        novel_id: uuid.UUID,
        *,
        section: DriftSection,
        document: dict,
        fingerprint: str,
    ) -> None:
        """Atomically upsert ONE section of the composite document.

        Args:
            novel_id: The band whose snapshot row is written (created on
                demand by the conflict clause).
            section: The composite-document key this run owns
                (``"consistency"`` or ``"voice_drift"``).
            document: The serialized run-result model (JSON-ready dict).
            fingerprint: Save-time chapter-texts fingerprint (ADR-045 scheme).
        """
        stmt = pg_insert(SeriesDriftResult).values(
            novel_id=novel_id,
            result={section: document},
            input_fingerprint=fingerprint,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[SeriesDriftResult.novel_id],
            set_={
                # JSONB shallow merge: this run's section overlays the stored
                # document; the sibling section survives.
                "result": SeriesDriftResult.result.op("||")(stmt.excluded.result),
                "input_fingerprint": stmt.excluded.input_fingerprint,
                "generated_at": func.now(),
            },
        )
        await self._session.execute(stmt)
```

- [ ] **Step 4: Run the integration tests to verify they pass**

Run: `just test-file tests/integration/series/test_series_drift_repository.py`
Expected: PASS — first-store row shape, parallel sibling-section survival, latest-wins overwrite of the own section, get row-or-None, novel-delete cascade, protocol surface.

- [ ] **Step 5: Run the architecture checker**

Run: `just check-architecture`
Expected: PASS.

- [ ] **Step 6: Commit (via Platform, verbatim)**

```bash
git add apps/api/narrare/series/series_drift_repository.py \
        tests/integration/series/__init__.py \
        tests/integration/series/test_series_drift_repository.py
```

Commit message:

```
feat(api/series): add SeriesDriftRepository — atomic section upsert

C2: the series_drift_results query surface (implements
SeriesDriftRepositoryProtocol, the Task-3 contracts).

- store_section: ONE atomic INSERT ... ON CONFLICT (novel_id) DO UPDATE
  with a JSONB shallow-merge (result || excluded.result) — the panel fires
  both check POSTs in parallel, so a load-or-create loop would PK-collide
  and a wholesale document overwrite would destroy the sibling section.
  Each run overlays only its own key; input_fingerprint + record-level
  generated_at refresh on every write (latest-wins).
- get: PK lookup, None when nothing is persisted.

Integration tests (real PG, rolled-back session): first-store row shape,
parallel sibling-section survival, latest-wins overwrite of the own
section (§12 gate), get row-or-None, novel-delete cascade, protocol
surface.

Refs: docs/superpowers/specs/2026-08-14-post-export-followups-design.md §5 + §12 (latest-wins gate)
```

### Task 5: Persistence service — store-on-run wrapper + snapshot read with staleness

**Files:**
- Create: `apps/api/narrare/series/series_drift_persistence_service.py`
- Test: `tests/unit/api/series/test_series_drift_persistence_service.py` (new)

**Interfaces:**
- Consumes: `fingerprint_chapter_texts` (Task 1); `SeriesDriftResult` + table (Task 2); `DriftSection`, `SeriesDriftRepositoryProtocol`, `SeriesDriftPersistenceServiceProtocol` (Task 3); `SeriesConsistencyService.check_novel` + `SeriesVoiceDriftService.check` (existing, unchanged); `ChapterRepositoryProtocol.list_by_novel`; `SeriesRepositoryProtocol.get`; `NovelRepositoryProtocol.get`; `ForbiddenError`.
- Produces (verbatim for Task 6): `SeriesDriftPersistenceService(*, consistency_service, voice_drift_service, series_repo, novel_repo, chapter_repo, drift_repo)` with `check_and_store_consistency`, `check_and_store_voice_drift`, `get_snapshot` per the Task-3 Protocol.

- [ ] **Step 1: Write the failing service tests**

Create `tests/unit/api/series/test_series_drift_persistence_service.py`:

```python
"""Tests for SeriesDriftPersistenceService (C2 — store-on-run + stale read).

The wrapped run services are mocked with AsyncMock at the delegation seam
(the same ADR-030 allowance the router tests use — the run services have
their own exhaustive Fake-based suites and are byte-identical in this slice);
everything else is real: FakeSeriesRepository / FakeNovelRepository /
FakeChapterRepository / FakeSeriesDriftRepository, the REAL fingerprint
(C2 binding: store-time and GET-time share one computation path), and the
REAL Pydantic round-trip through the composite document.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from narrare.analysis.schemas_author_voice_drift import (
    AuthorVoiceDriftRequest,
    AuthorVoiceDriftResponse,
)
from narrare.chapters.models import Chapter
from narrare.novels.models import Novel
from narrare.series.series_consistency_schemas import (
    SeriesConsistencyCheckResponse,
)
from narrare.series.series_drift_contracts import (
    SeriesDriftPersistenceServiceProtocol,
)
from narrare.series.series_drift_persistence_service import (
    SeriesDriftPersistenceService,
)
from narrare_core.series.schemas import Series
from narrare_core.shared.errors import ForbiddenError
from tests.fakes.fake_chapter_repo import FakeChapterRepository
from tests.fakes.fake_novel_repo import FakeNovelRepository
from tests.fakes.fake_series_drift_repo import FakeSeriesDriftRepository
from tests.fakes.fake_series_repo import FakeSeriesRepository


def _series(owner: uuid.UUID) -> Series:
    return Series(id=uuid.uuid4(), user_id=owner, title="Chronicles")


def _novel(series_id: uuid.UUID) -> Novel:
    return Novel(
        id=uuid.uuid4(), user_id=uuid.uuid4(), title="Band 1", series_id=series_id
    )


def _chapter(novel_id: uuid.UUID, content: str, position: int) -> Chapter:
    chapter = Chapter()
    chapter.id = uuid.uuid4()
    chapter.novel_id = novel_id
    chapter.title = f"Chapter {position}"
    chapter.content = content
    chapter.position = position
    return chapter


def _consistency_response(
    series_id: uuid.UUID, novel_id: uuid.UUID
) -> SeriesConsistencyCheckResponse:
    return SeriesConsistencyCheckResponse(
        series_id=series_id,
        novel_id=novel_id,
        conflicts=[],
        summary="No contradictions found.",
        canon_entry_count=2,
        chapter_count=2,
    )


def _make_service(
    *,
    series_repo: FakeSeriesRepository,
    novel_repo: FakeNovelRepository,
    chapter_repo: FakeChapterRepository,
    drift_repo: FakeSeriesDriftRepository,
    consistency_return: SeriesConsistencyCheckResponse | None = None,
    voice_return: AuthorVoiceDriftResponse | None = None,
) -> SeriesDriftPersistenceService:
    consistency = AsyncMock()
    consistency.check_novel.return_value = consistency_return
    voice = AsyncMock()
    voice.check.return_value = voice_return
    return SeriesDriftPersistenceService(
        consistency_service=consistency,
        voice_drift_service=voice,
        series_repo=series_repo,
        novel_repo=novel_repo,
        chapter_repo=chapter_repo,
        drift_repo=drift_repo,
    )


def _seeded(owner: uuid.UUID) -> tuple[
    FakeSeriesRepository,
    FakeNovelRepository,
    FakeChapterRepository,
    FakeSeriesDriftRepository,
    Series,
    Novel,
]:
    """Seed series + member novel; empty chapter/drift fakes for the caller."""
    series = _series(owner)
    novel = _novel(series.id)
    series_repo = FakeSeriesRepository()
    series_repo.seed(series)
    novel_repo = FakeNovelRepository()
    novel_repo.seed(novel)
    return (
        series_repo,
        novel_repo,
        FakeChapterRepository(),
        FakeSeriesDriftRepository(),
        series,
        novel,
    )


class TestCheckAndStoreConsistency:
    async def test_runs_then_stores_its_section(self) -> None:
        owner = uuid.uuid4()
        series_repo, novel_repo, chapter_repo, drift_repo, series, novel = _seeded(
            owner
        )
        chapter_repo.seed(_chapter(novel.id, "Prose one.", 1))
        response = _consistency_response(series.id, novel.id)
        service = _make_service(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            drift_repo=drift_repo,
            consistency_return=response,
        )

        result = await service.check_and_store_consistency(series.id, novel.id, owner)

        assert result is response  # returned verbatim
        drift_repo.assert_called(
            "store_section",
            novel_id=novel.id,
            section="consistency",
            document=response.model_dump(mode="json"),
        )

    async def test_forbidden_before_check_propagates_without_store(self) -> None:
        drift_repo = FakeSeriesDriftRepository()
        consistency = AsyncMock()
        consistency.check_novel.side_effect = ForbiddenError("no access")
        service = SeriesDriftPersistenceService(
            consistency_service=consistency,
            voice_drift_service=AsyncMock(),
            series_repo=FakeSeriesRepository(),
            novel_repo=FakeNovelRepository(),
            chapter_repo=FakeChapterRepository(),
            drift_repo=drift_repo,
        )

        with pytest.raises(ForbiddenError):
            await service.check_and_store_consistency(
                uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
            )
        drift_repo.assert_not_called("store_section")

    async def test_store_failure_degrades_gracefully_result_still_returned(
        self,
    ) -> None:
        """RULE-11 ruling: the LLM cost is paid; a store failure must not
        destroy the check result — log + return."""
        owner = uuid.uuid4()
        series_repo, novel_repo, chapter_repo, drift_repo, series, novel = _seeded(
            owner
        )
        chapter_repo.seed(_chapter(novel.id, "Prose one.", 1))
        drift_repo.raise_on_store = RuntimeError("db down")
        response = _consistency_response(series.id, novel.id)
        service = _make_service(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            drift_repo=drift_repo,
            consistency_return=response,
        )

        result = await service.check_and_store_consistency(series.id, novel.id, owner)

        assert result is response


class TestCheckAndStoreVoiceDrift:
    async def test_runs_then_stores_its_section(self) -> None:
        owner = uuid.uuid4()
        series_repo, novel_repo, chapter_repo, drift_repo, series, novel = _seeded(
            owner
        )
        chapter_repo.seed(_chapter(novel.id, "Prose one.", 1))
        voice_response = AuthorVoiceDriftResponse(novel_id=str(novel.id))
        service = _make_service(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            drift_repo=drift_repo,
            voice_return=voice_response,
        )

        result = await service.check_and_store_voice_drift(
            series.id, novel.id, owner, AuthorVoiceDriftRequest()
        )

        assert result is voice_response
        drift_repo.assert_called(
            "store_section",
            novel_id=novel.id,
            section="voice_drift",
            document=voice_response.model_dump(mode="json"),
        )

    async def test_graceful_no_profile_result_is_stored(self) -> None:
        """Ruling: graceful-skip outcomes are valid analysis results."""
        owner = uuid.uuid4()
        series_repo, novel_repo, chapter_repo, drift_repo, series, novel = _seeded(
            owner
        )
        voice_response = AuthorVoiceDriftResponse.model_validate(
            {"novel_id": str(novel.id), "no_profile": {"reason": "no_stored_series_voice"}}
        )
        service = _make_service(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            drift_repo=drift_repo,
            voice_return=voice_response,
        )

        await service.check_and_store_voice_drift(
            series.id, novel.id, owner, AuthorVoiceDriftRequest()
        )

        drift_repo.assert_called("store_section", section="voice_drift")


class TestGetSnapshot:
    async def test_no_record_returns_all_null_snapshot(self) -> None:
        owner = uuid.uuid4()
        series_repo, novel_repo, chapter_repo, drift_repo, series, novel = _seeded(
            owner
        )
        chapter_repo.seed(_chapter(novel.id, "Prose one.", 1))
        service = _make_service(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            drift_repo=drift_repo,
        )

        snapshot = await service.get_snapshot(series.id, novel.id, owner)

        assert snapshot.generated_at is None
        assert snapshot.consistency is None
        assert snapshot.voice_drift is None
        assert snapshot.stale is False

    async def test_unchanged_texts_are_fresh(self) -> None:
        owner = uuid.uuid4()
        series_repo, novel_repo, chapter_repo, drift_repo, series, novel = _seeded(
            owner
        )
        # One prose chapter + one whitespace-only chapter (excluded from the
        # fingerprint by the non-empty filter, like the consistency check).
        chapter_repo.seed(
            _chapter(novel.id, "Prose one.", 1), _chapter(novel.id, "   ", 2)
        )
        service = _make_service(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            drift_repo=drift_repo,
            consistency_return=_consistency_response(series.id, novel.id),
        )
        await service.check_and_store_consistency(series.id, novel.id, owner)

        snapshot = await service.get_snapshot(series.id, novel.id, owner)

        assert snapshot.stale is False
        assert snapshot.consistency is not None
        assert snapshot.consistency.summary == "No contradictions found."

    async def test_edited_texts_flip_stale(self) -> None:
        """Design §12 gate: the stale-flag flip."""
        owner = uuid.uuid4()
        series_repo, novel_repo, chapter_repo, drift_repo, series, novel = _seeded(
            owner
        )
        chapter = _chapter(novel.id, "Original prose.", 1)
        chapter_repo.seed(chapter)
        service = _make_service(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            drift_repo=drift_repo,
            consistency_return=_consistency_response(series.id, novel.id),
        )
        await service.check_and_store_consistency(series.id, novel.id, owner)

        assert (await service.get_snapshot(series.id, novel.id, owner)).stale is False

        chapter.content = "Edited prose."  # the band's texts changed

        assert (await service.get_snapshot(series.id, novel.id, owner)).stale is True

    async def test_unknown_series_raises_forbidden(self) -> None:
        service = _make_service(
            series_repo=FakeSeriesRepository(),
            novel_repo=FakeNovelRepository(),
            chapter_repo=FakeChapterRepository(),
            drift_repo=FakeSeriesDriftRepository(),
        )

        with pytest.raises(ForbiddenError):
            await service.get_snapshot(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())

    async def test_foreign_series_raises_forbidden(self) -> None:
        owner, stranger = uuid.uuid4(), uuid.uuid4()
        series_repo, novel_repo, chapter_repo, drift_repo, series, novel = _seeded(
            owner
        )
        service = _make_service(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            drift_repo=drift_repo,
        )

        with pytest.raises(ForbiddenError):
            await service.get_snapshot(series.id, novel.id, stranger)

    async def test_non_member_novel_raises_forbidden(self) -> None:
        owner = uuid.uuid4()
        series_repo, novel_repo, chapter_repo, drift_repo, series, _ = _seeded(owner)
        outsider = _novel(uuid.uuid4())  # belongs to another series
        novel_repo.seed(outsider)
        service = _make_service(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            drift_repo=drift_repo,
        )

        with pytest.raises(ForbiddenError):
            await service.get_snapshot(series.id, outsider.id, owner)

    async def test_snapshot_sections_round_trip_through_the_document(self) -> None:
        """Both sections coexist in ONE document and deserialize back into
        the run-result models (the reuse-don't-reshape binding)."""
        owner = uuid.uuid4()
        series_repo, novel_repo, chapter_repo, drift_repo, series, novel = _seeded(
            owner
        )
        chapter_repo.seed(_chapter(novel.id, "Prose.", 1))
        voice_response = AuthorVoiceDriftResponse.model_validate(
            {"novel_id": str(novel.id), "no_profile": {"reason": "no_stored_series_voice"}}
        )
        service = _make_service(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            drift_repo=drift_repo,
            consistency_return=_consistency_response(series.id, novel.id),
            voice_return=voice_response,
        )
        await service.check_and_store_consistency(series.id, novel.id, owner)
        await service.check_and_store_voice_drift(
            series.id, novel.id, owner, AuthorVoiceDriftRequest()
        )

        snapshot = await service.get_snapshot(series.id, novel.id, owner)

        assert snapshot.generated_at is not None
        assert snapshot.consistency is not None
        assert snapshot.voice_drift is not None
        assert snapshot.voice_drift.no_profile is not None
        assert snapshot.voice_drift.no_profile.reason == "no_stored_series_voice"

    def test_service_satisfies_protocol(self) -> None:
        service = _make_service(
            series_repo=FakeSeriesRepository(),
            novel_repo=FakeNovelRepository(),
            chapter_repo=FakeChapterRepository(),
            drift_repo=FakeSeriesDriftRepository(),
        )
        assert isinstance(service, SeriesDriftPersistenceServiceProtocol)
```

> **Note on the `Chapter()` construction:** `Chapter` is the ORM model with Python-side defaults; constructing it and assigning `id`/`novel_id`/`title`/`content`/`position` mirrors how `fake_chapter_repo` consumers build seeds (the fake never touches the DB). If `Chapter()` requires additional NOT NULL attributes in your checkout, run `rg -n "nullable=False" apps/api/narrare/chapters/models.py` and set the missing attributes in `_chapter` the same way.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `just test-file tests/unit/api/series/test_series_drift_persistence_service.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'narrare.series.series_drift_persistence_service'`.

- [ ] **Step 3: Implement the service**

Create `apps/api/narrare/series/series_drift_persistence_service.py`:

```python
"""SeriesDriftPersistenceService — store-on-run + stale-aware snapshot read
(SERIES-004 Slice 6, C2 — design §5).

Business logic only (RULE-06): no SQL, no HTTP. This service WRAPS the two
UNCHANGED run services (``SeriesConsistencyService`` /
``SeriesVoiceDriftService`` — both at their RULE-04 file-size ceilings and
kept byte-identical for zero regression, the ADR-079 Decision-4 wrapper
pattern): each ``check_and_store_*`` runs the check, then persists the
result as its section of the composite ``series_drift_results`` document,
then returns the result verbatim.

Staleness (design §5): ``get_snapshot`` recomputes the chapter-texts
fingerprint with the SAME helper + read path used at save time
(``list_by_novel`` position order, non-empty-prose filter — identical to
``SeriesConsistencyService.check_novel`` step 4) and compares it with the
stored digest: ``stale=True`` means the band's texts changed after the last
completed write.

RULE-11 persistence degradation (documented ruling): the check's LLM cost is
already paid when the store runs, so a store failure logs a
``series_drift_persist_failed`` warning and the computed result is still
returned — mirroring ``SeriesVoiceDriftService._load_series_voice``'s
malformed-JSONB degradation. The GET path propagates errors normally.

Ownership (anti-enumeration, mirrors the run services): ``get_snapshot``
verifies series ownership + novel membership itself; the ``check_and_store_*``
methods inherit verification from the wrapped services (a 403 raises BEFORE
any store).

Pattern: router → this service → run services + repositories (RULE-07).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.analysis.schemas_author_voice_drift import AuthorVoiceDriftResponse
from narrare.series.series_consistency_schemas import SeriesConsistencyCheckResponse
from narrare.series.series_drift_schemas import SeriesDriftSnapshotResponse
from narrare_core.ai_invocation.correlation import fingerprint_chapter_texts
from narrare_core.shared.errors import ForbiddenError

if TYPE_CHECKING:
    import uuid

    from narrare.analysis.schemas_author_voice_drift import AuthorVoiceDriftRequest
    from narrare.chapters.contracts import ChapterRepositoryProtocol
    from narrare.novels.contracts import NovelRepositoryProtocol
    from narrare.series.contracts import SeriesRepositoryProtocol
    from narrare.series.series_consistency_service import SeriesConsistencyService
    from narrare.series.series_drift_contracts import (
        DriftSection,
        SeriesDriftRepositoryProtocol,
    )
    from narrare.series.series_voice_drift_service import SeriesVoiceDriftService
    from narrare_core.series.schemas import Series

logger = structlog.get_logger(__name__)

_CONSISTENCY_SECTION: DriftSection = "consistency"
_VOICE_DRIFT_SECTION: DriftSection = "voice_drift"


class SeriesDriftPersistenceService:
    """Run-then-persist orchestration + stale-aware snapshot read (C2)."""

    def __init__(
        self,
        *,
        consistency_service: SeriesConsistencyService,
        voice_drift_service: SeriesVoiceDriftService,
        series_repo: SeriesRepositoryProtocol,
        novel_repo: NovelRepositoryProtocol,
        chapter_repo: ChapterRepositoryProtocol,
        drift_repo: SeriesDriftRepositoryProtocol,
    ) -> None:
        """Initialise with all dependencies injected (RULE-07).

        Args:
            consistency_service: The UNCHANGED canon-contradiction run service.
            voice_drift_service: The UNCHANGED series-voice-drift run service.
            series_repo: Series lookup (snapshot ownership verification).
            novel_repo: Novel lookup (membership verification).
            chapter_repo: Chapter prose fetch for the fingerprint.
            drift_repo: ``series_drift_results`` persistence (Task 4).
        """
        self._consistency_service = consistency_service
        self._voice_drift_service = voice_drift_service
        self._series_repo = series_repo
        self._novel_repo = novel_repo
        self._chapter_repo = chapter_repo
        self._drift_repo = drift_repo

    async def check_and_store_consistency(
        self, series_id: uuid.UUID, novel_id: uuid.UUID, user_id: uuid.UUID
    ) -> SeriesConsistencyCheckResponse:
        """Run the canon check, persist its section, return the result.

        Full contract on
        :meth:`SeriesDriftPersistenceServiceProtocol.check_and_store_consistency`.
        """
        result = await self._consistency_service.check_novel(series_id, novel_id, user_id)
        await self._store_section(
            series_id, novel_id, _CONSISTENCY_SECTION, result.model_dump(mode="json")
        )
        return result

    async def check_and_store_voice_drift(
        self,
        series_id: uuid.UUID,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        request: AuthorVoiceDriftRequest,
    ) -> AuthorVoiceDriftResponse:
        """Run the voice-drift check, persist its section, return the result.

        Full contract on
        :meth:`SeriesDriftPersistenceServiceProtocol.check_and_store_voice_drift`.
        """
        result = await self._voice_drift_service.check(series_id, novel_id, user_id, request)
        await self._store_section(
            series_id, novel_id, _VOICE_DRIFT_SECTION, result.model_dump(mode="json")
        )
        return result

    async def get_snapshot(
        self, series_id: uuid.UUID, novel_id: uuid.UUID, user_id: uuid.UUID
    ) -> SeriesDriftSnapshotResponse:
        """Read the persisted snapshot with the staleness flag.

        Full contract on
        :meth:`SeriesDriftPersistenceServiceProtocol.get_snapshot`.
        """
        # 1-2. Verify series ownership + novel membership (anti-enumeration).
        await self._verify_series_ownership(series_id, user_id)
        novel = await self._novel_repo.get(novel_id)
        if novel is None or novel.series_id != series_id:
            raise ForbiddenError("You do not have access to this series")

        # 3. No record -> the honest all-null snapshot (never an error).
        row = await self._drift_repo.get(novel_id)
        if row is None:
            return SeriesDriftSnapshotResponse(
                series_id=series_id,
                novel_id=novel_id,
                generated_at=None,
                stale=False,
                consistency=None,
                voice_drift=None,
            )

        # 4. Deserialize the stored sections back into the run-result models
        #    (RULE-22 — the document serializes THOSE models) + the stale
        #    verdict from ONE fingerprint computation path.
        document = row.result or {}
        consistency_doc = document.get(_CONSISTENCY_SECTION)
        voice_doc = document.get(_VOICE_DRIFT_SECTION)
        current_fingerprint = await self._compute_fingerprint(novel_id)
        return SeriesDriftSnapshotResponse(
            series_id=series_id,
            novel_id=novel_id,
            generated_at=row.generated_at,
            stale=row.input_fingerprint != current_fingerprint,
            consistency=(
                SeriesConsistencyCheckResponse.model_validate(consistency_doc)
                if consistency_doc is not None
                else None
            ),
            voice_drift=(
                AuthorVoiceDriftResponse.model_validate(voice_doc)
                if voice_doc is not None
                else None
            ),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _store_section(
        self,
        series_id: uuid.UUID,
        novel_id: uuid.UUID,
        section: DriftSection,
        document: dict,
    ) -> None:
        """Persist one run's section (RULE-11: degrade, never fail the check).

        The wrapped service already verified ownership + membership before
        this runs (a 403 raises before any store), and the LLM cost of the
        result is paid — a persistence failure logs a warning and the caller
        still returns the computed result to the author.
        """
        try:
            fingerprint = await self._compute_fingerprint(novel_id)
            await self._drift_repo.store_section(
                novel_id, section=section, document=document, fingerprint=fingerprint
            )
        except Exception as exc:  # documented degradation ruling (RULE-11)
            logger.warning(
                "series_drift_persist_failed",
                feature_id="series_drift_persistence",
                series_id=str(series_id),
                novel_id=str(novel_id),
                section=section,
                error=str(exc),
            )

    async def _compute_fingerprint(self, novel_id: uuid.UUID) -> str:
        """Fingerprint the band's chapter texts (ONE path for save + GET).

        Same read path and filter as ``SeriesConsistencyService.check_novel``
        step 4: ``list_by_novel`` (position-ordered per its contract), keeping
        only chapters with non-empty prose. Deterministic by construction.
        """
        chapters = await self._chapter_repo.list_by_novel(novel_id)
        texts = [c.content for c in chapters if (c.content or "").strip()]
        return fingerprint_chapter_texts(texts)

    async def _verify_series_ownership(
        self, series_id: uuid.UUID, user_id: uuid.UUID
    ) -> Series:
        """Load a series and verify the caller owns it (anti-enumeration).

        Mirrors ``SeriesConsistencyService._verify_series_ownership``: a
        *missing* series and a *not-owned* series both surface as
        ``ForbiddenError`` (HTTP 403) — never 404.
        """
        series = await self._series_repo.get(series_id)
        if series is None or series.user_id != user_id:
            raise ForbiddenError("You do not have access to this series")
        return series
```

- [ ] **Step 4: Run the service tests to verify they pass**

Run: `just test-file tests/unit/api/series/test_series_drift_persistence_service.py`
Expected: PASS — store-on-run (both sections), pre-check 403 without store, graceful store degradation, all-null snapshot, fresh vs stale flip (§12 gate), ownership triple-403, document round-trip, protocol satisfaction.

- [ ] **Step 5: Run the sibling suites to prove zero regression**

Run: `just test-file tests/unit/api/series/`
Expected: PASS — the run services, their contracts, and their existing tests are untouched.

- [ ] **Step 6: Commit (via Platform, verbatim)**

```bash
git add apps/api/narrare/series/series_drift_persistence_service.py \
        tests/unit/api/series/test_series_drift_persistence_service.py
```

Commit message:

```
feat(api/series): add SeriesDriftPersistenceService — store-on-run + stale read

C2 (design §5): the service extension that makes the SERIES-004 checks
persistent. WRAPS the two unchanged run services (both at their RULE-04
ceilings — series_voice_drift_service.py 298/300, series_consistency_service.py
265/300 — kept byte-identical, ADR-079 Decision-4 wrapper pattern).

- check_and_store_consistency / check_and_store_voice_drift: run the check
  via the unchanged services, persist the result as the run's section of
  the composite document (model_dump(mode="json") — the run-result models
  are the stored shape, never re-shaped), return the result verbatim.
  Graceful-skip outcomes are stored too (valid analysis results).
- get_snapshot: ownership + membership 403s (anti-enumeration), all-null
  snapshot when nothing is persisted (200, never an error), sections
  deserialized back into SeriesConsistencyCheckResponse /
  AuthorVoiceDriftResponse, and stale = stored fingerprint vs the
  recomputed current one.
- _compute_fingerprint: ONE path for save-time and GET-time —
  list_by_novel position order + non-empty-prose filter (identical to the
  consistency check's chapter read), hashed via the Task-1 ADR-045-scheme
  helper.
- RULE-11 ruling: store failure logs series_drift_persist_failed and the
  paid-for check result is still returned (documented degradation, tested).

Tests: Fake-based units incl. the §12 stale-flip gate + document round-trip.

Refs: docs/superpowers/specs/2026-08-14-post-export-followups-design.md §5 + §12
```

### Task 6: DI factory + router wiring — GET endpoint + POST dependency swap

**Files:**
- Create: `apps/api/narrare/series/dependencies_drift_persistence.py`
- Modify: `apps/api/narrare/series/router_consistency.py` (62/150 — swap POST dependency, add GET)
- Modify: `apps/api/narrare/series/router_voice_drift.py` (70/150 — swap dependency)
- Test: extend `tests/unit/api/series/test_router_consistency.py` + `tests/unit/api/series/test_router_voice_drift.py`

**Interfaces:**
- Consumes: `SeriesDriftPersistenceService` (Task 5); `get_series_consistency_service` / `get_series_voice_drift_service` (existing factories); `SeriesDriftSnapshotResponse` (Task 3).
- Produces: `get_series_drift_persistence_service` (Depends-chained factory); `GET /api/v1/series/{series_id}/consistency/{novel_id}` → `SeriesDriftSnapshotResponse`; both POST endpoints delegate to `check_and_store_*` (HTTP response shapes UNCHANGED).

- [ ] **Step 1: Write the failing GET router tests**

In `tests/unit/api/series/test_router_consistency.py`, extend the imports (the file already imports `AsyncMock`, `uuid4`, `status`, `ForbiddenError`, `FastAPI`/`AsyncClient` under TYPE_CHECKING; the conftest provides the `app`/`client` fixtures) and append:

```python
from narrare.series.dependencies_drift_persistence import (
    get_series_drift_persistence_service,
)
from narrare.series.series_drift_schemas import SeriesDriftSnapshotResponse


def _make_snapshot(series_id, novel_id) -> SeriesDriftSnapshotResponse:  # type: ignore[no-untyped-def]
    """A minimal all-null snapshot for the mock return value."""
    return SeriesDriftSnapshotResponse(
        series_id=series_id,
        novel_id=novel_id,
        generated_at=None,
        stale=False,
        consistency=None,
        voice_drift=None,
    )


class TestGetSeriesDriftSnapshot:
    """GET /api/v1/series/{series_id}/consistency/{novel_id} (C2 Slice 6)."""

    def _use_service(self, app: FastAPI, mock: AsyncMock) -> None:
        """Override the drift-persistence dependency with ``mock``."""
        app.dependency_overrides[get_series_drift_persistence_service] = lambda: mock

    async def test_get_returns_200_and_delegates(
        self, app: FastAPI, client: AsyncClient
    ) -> None:
        series_id = uuid4()
        novel_id = uuid4()
        mock = AsyncMock()
        mock.get_snapshot.return_value = _make_snapshot(series_id, novel_id)
        self._use_service(app, mock)

        response = await client.get(
            f"/api/v1/series/{series_id}/consistency/{novel_id}"
        )

        assert response.status_code == status.HTTP_200_OK
        mock.get_snapshot.assert_awaited_once()
        assert mock.get_snapshot.await_args.kwargs["series_id"] == series_id
        assert mock.get_snapshot.await_args.kwargs["novel_id"] == novel_id
        assert response.json()["stale"] is False
        assert response.json()["generated_at"] is None

    async def test_get_maps_forbidden_to_403(
        self, app: FastAPI, client: AsyncClient
    ) -> None:
        mock = AsyncMock()
        mock.get_snapshot.side_effect = ForbiddenError("no access")
        self._use_service(app, mock)

        response = await client.get(
            f"/api/v1/series/{uuid4()}/consistency/{uuid4()}"
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    async def test_get_rejects_non_uuid_novel_id(
        self, app: FastAPI, client: AsyncClient
    ) -> None:
        mock = AsyncMock()
        self._use_service(app, mock)

        response = await client.get(
            f"/api/v1/series/{uuid4()}/consistency/not-a-uuid"
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        mock.get_snapshot.assert_not_awaited()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `just test-file tests/unit/api/series/test_router_consistency.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'narrare.series.dependencies_drift_persistence'` (collection error).

- [ ] **Step 3: Create the DI factory**

Create `apps/api/narrare/series/dependencies_drift_persistence.py`:

```python
"""DI factory for drift persistence (SERIES-004 Slice 6, C2).

Split into its own module (RULE-04 — the ``dependencies_{consistency,
voice_drift}.py`` precedent; ``dependencies.py`` is at 179/200 lines, NOT at
the limit — the split follows the established per-feature dependency-module
pattern rather than a size necessity). The factory
CHAINS the two existing run-service factories via ``Depends`` (their wiring is
not duplicated) and adds the snapshot read/write dependencies: series + novel
+ chapter repositories (ownership + fingerprint reads) and the drift-results
repository.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends

from narrare._app.dependencies import SessionDep
from narrare.chapters.repository import ChapterRepository
from narrare.novels.repository import NovelRepository
from narrare.series.dependencies_consistency import get_series_consistency_service
from narrare.series.dependencies_voice_drift import get_series_voice_drift_service
from narrare.series.repository import SeriesRepository
from narrare.series.series_drift_repository import SeriesDriftRepository

if TYPE_CHECKING:
    from narrare.series.series_consistency_service import SeriesConsistencyService
    from narrare.series.series_drift_persistence_service import (
        SeriesDriftPersistenceService,
    )
    from narrare.series.series_voice_drift_service import SeriesVoiceDriftService


def get_series_drift_persistence_service(
    session: SessionDep,
    consistency_service: SeriesConsistencyService = Depends(
        get_series_consistency_service
    ),
    voice_drift_service: SeriesVoiceDriftService = Depends(
        get_series_voice_drift_service
    ),
) -> SeriesDriftPersistenceService:
    """Request-scoped SeriesDriftPersistenceService (C2 drift persistence).

    Wraps the two run services (wired by their existing factories — Depends-
    chained, not duplicated) with the snapshot persistence dependencies.
    """
    from narrare.series.series_drift_persistence_service import (
        SeriesDriftPersistenceService,
    )

    return SeriesDriftPersistenceService(
        consistency_service=consistency_service,
        voice_drift_service=voice_drift_service,
        series_repo=SeriesRepository(session),
        novel_repo=NovelRepository(session),
        chapter_repo=ChapterRepository(session),
        drift_repo=SeriesDriftRepository(session),
    )
```

(The return type resolves via the `TYPE_CHECKING` import while the function-body import performs the runtime construction — exactly the `dependencies_consistency.py` pattern.)

- [ ] **Step 4: Wire router_consistency.py — swap dependency + add GET**

In `apps/api/narrare/series/router_consistency.py`:

4a. Replace the import block:

```python
from narrare.series.dependencies_consistency import get_series_consistency_service
from narrare.series.series_consistency_schemas import (
    SeriesConsistencyCheckRequest,
    SeriesConsistencyCheckResponse,
)
from narrare.series.series_consistency_service import SeriesConsistencyService
```

with:

```python
from narrare.series.dependencies_drift_persistence import (
    get_series_drift_persistence_service,
)
from narrare.series.series_consistency_schemas import (
    SeriesConsistencyCheckRequest,
    SeriesConsistencyCheckResponse,
)
from narrare.series.series_drift_persistence_service import (
    SeriesDriftPersistenceService,
)
from narrare.series.series_drift_schemas import SeriesDriftSnapshotResponse
```

4b. In the `check_series_consistency` handler, replace the dependency line:

```python
    service: SeriesConsistencyService = Depends(get_series_consistency_service),
```

with:

```python
    service: SeriesDriftPersistenceService = Depends(get_series_drift_persistence_service),
```

and replace the delegation tail:

```python
    return await service.check_novel(
        series_id=series_id,
        novel_id=request.novel_id,
        user_id=uuid.UUID(user_id),
    )
```

with:

```python
    return await service.check_and_store_consistency(
        series_id=series_id,
        novel_id=request.novel_id,
        user_id=uuid.UUID(user_id),
    )
```

Also update the handler docstring sentence `Read-only — nothing is persisted.` to `The result is persisted as the band's latest drift snapshot (C2) before it is returned.` (keep the ownership sentences).

4c. Append the GET route (after the existing POST handler):

```python
@router.get(
    "/{series_id}/consistency/{novel_id}",
    response_model=SeriesDriftSnapshotResponse,
)
async def get_series_drift_snapshot(
    series_id: uuid.UUID,
    novel_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: SeriesDriftPersistenceService = Depends(get_series_drift_persistence_service),
) -> SeriesDriftSnapshotResponse:
    """Fetch the persisted drift snapshot for one band (SERIES-004 Slice 6).

    Returns the latest-wins composite snapshot (canon contradictions +
    voice drift as stored by the check runs) plus the staleness verdict:
    ``stale=true`` when the band's chapter texts changed since the last
    completed write. Nothing persisted yet → an all-null snapshot with
    ``stale=false`` (never an error).

    Note: a GET to ``…/consistency/check`` (the POST-only run path) matches
    this route with a non-UUID ``novel_id`` and surfaces as 422 — there is no
    GET route on ``check`` by design.

    Ownership + novel-membership are verified inside the service
    (anti-enumeration: a missing/not-owned series and a non-member novel both
    surface as ``403``).
    """
    return await service.get_snapshot(
        series_id=series_id,
        novel_id=novel_id,
        user_id=uuid.UUID(user_id),
    )
```

- [ ] **Step 5: Wire router_voice_drift.py — swap dependency**

In `apps/api/narrare/series/router_voice_drift.py`:

5a. Replace the import:

```python
from narrare.series.dependencies_voice_drift import get_series_voice_drift_service
```

with:

```python
from narrare.series.dependencies_drift_persistence import (
    get_series_drift_persistence_service,
)
```

and replace:

```python
from narrare.series.series_voice_drift_service import SeriesVoiceDriftService
```

with:

```python
from narrare.series.series_drift_persistence_service import (
    SeriesDriftPersistenceService,
)
```

5b. In the handler signature replace:

```python
    service: SeriesVoiceDriftService = Depends(get_series_voice_drift_service),
```

with:

```python
    service: SeriesDriftPersistenceService = Depends(get_series_drift_persistence_service),
```

and replace the delegation tail:

```python
    return await service.check(
        series_id=series_id,
        novel_id=request.novel_id,
        user_id=uuid.UUID(user_id),
        request=AuthorVoiceDriftRequest(chapter_ids=request.chapter_ids),
    )
```

with:

```python
    return await service.check_and_store_voice_drift(
        series_id=series_id,
        novel_id=request.novel_id,
        user_id=uuid.UUID(user_id),
        request=AuthorVoiceDriftRequest(chapter_ids=request.chapter_ids),
    )
```

Also update the handler docstring sentence `Read-only — nothing is persisted.` to `The result is persisted as the band's latest drift snapshot (C2) before it is returned.` (keep the ownership sentences).

- [ ] **Step 6: Update the existing POST router tests to the new dependency**

Boundary-anchored sweep — run:

```bash
rg -n "get_series_consistency_service|get_series_voice_drift_service|check_novel|\.check\(" tests/unit/api/series/test_router_consistency.py tests/unit/api/series/test_router_voice_drift.py
```

For every match, mechanically apply:
- The dependency-override key becomes `get_series_drift_persistence_service` (import from `narrare.series.dependencies_drift_persistence`); the `_use_service` helpers re-target it.
- The mocked method for the consistency POST becomes `check_and_store_consistency` (was `check_novel`); for the voice-drift POST becomes `check_and_store_voice_drift` (was `check`).
- If a mock is constructed with `AsyncMock(spec=…)`, change the spec to `SeriesDriftPersistenceService`.
- Response-shape assertions stay untouched — the POST responses are unchanged.

- [ ] **Step 7: Run the router tests to verify they pass**

Run: `just test-file tests/unit/api/series/test_router_consistency.py tests/unit/api/series/test_router_voice_drift.py`
Expected: PASS — existing POST tests (renamed delegation) + new GET tests (200 delegation / 403 / 422).

- [ ] **Step 8: Run the full unit gate + architecture checker**

Run: `just test-unit` then `just check-architecture`
Expected: PASS both (the openapi-regenerate pre-commit hook will stage `docs/reference/openapi.json` at commit time — let it ride).

- [ ] **Step 9: Commit (via Platform, verbatim)**

```bash
git add apps/api/narrare/series/dependencies_drift_persistence.py \
        apps/api/narrare/series/router_consistency.py \
        apps/api/narrare/series/router_voice_drift.py \
        docs/reference/openapi.json \
        tests/unit/api/series/test_router_consistency.py \
        tests/unit/api/series/test_router_voice_drift.py
```

Commit message:

```
feat(api/series): wire drift persistence — GET snapshot endpoint + run swap

C2: the SERIES-004 sketched retrieval shape lands (plan line 29):
GET /api/v1/series/{series_id}/consistency/{novel_id} -> the latest-wins
composite snapshot + stale flag; all-null snapshot (200, stale=false) when
nothing is persisted. Route-ordering note documented in the handler
docstring (GET .../consistency/check -> 422 via the non-UUID novel_id).

- dependencies_drift_persistence.py: factory CHAINS the two existing
  run-service factories via Depends (no duplicated wiring) + the snapshot
  dependencies (series/novel/chapter repos + SeriesDriftRepository).
- router_consistency.py / router_voice_drift.py: the two POST handlers swap
  their dependency to SeriesDriftPersistenceService and delegate to
  check_and_store_consistency / check_and_store_voice_drift. Response shapes
  UNCHANGED; the run services themselves stay byte-identical.
- Router tests: existing POST tests re-target the new dependency + method
  names (response assertions untouched); new GET tests pin 200 delegation,
  403 anti-enumeration, and 422 on a non-UUID novel_id.

openapi.json regenerated by the pre-commit hook (rides along).

Refs: docs/superpowers/plans/2026-08-02-series-cross-novel-drift.md (GET shape), design §5, ADR-079 Slice 6
```

### Task 7: Web types + API client (snapshot reaches the frontend)

**Files:**
- Create: `packages/web/types/seriesDrift.ts`
- Modify: `packages/web/types/index.ts` (export)
- Modify: `packages/web/lib/api/series.ts` (add `getDriftSnapshot`; file at 216 lines)

**Interfaces:**
- Consumes: `SeriesConsistencyResult`, `SeriesVoiceDriftResult` (existing in `packages/web/types/series.ts`).
- Produces (verbatim for Tasks 8–9): `SeriesDriftSnapshot` interface (exported from `@/types`); `seriesApi.getDriftSnapshot(seriesId: string, novelId: string)`.

- [ ] **Step 1: Create the type file**

Create `packages/web/types/seriesDrift.ts`:

```typescript
/**
 * GET /api/v1/series/{id}/consistency/{novelId} response (SERIES-004 Slice 6 / C2).
 *
 * The persisted latest-wins drift snapshot for one band, fetched as ONE
 * document. RULE-17 contract parity: mirrors
 * ``apps/api/narrare/series/series_drift_schemas.SeriesDriftSnapshotResponse``
 * — snake_case preserved, the sections reuse the run-result mirrors from
 * ./series (the stored JSON serializes those models; no re-shaping).
 * ``generated_at`` is an ISO string (or null when nothing is persisted);
 * ``stale`` is true when the band's chapter texts changed since the last
 * completed write (server-side fingerprint comparison).
 */
import type { SeriesConsistencyResult, SeriesVoiceDriftResult } from "./series";

export interface SeriesDriftSnapshot {
  series_id: string;
  novel_id: string;
  /** ISO timestamp of the last completed write (either check); null = none. */
  generated_at: string | null;
  /** True when the band's texts changed after the persisted results. */
  stale: boolean;
  /** Persisted canon-contradiction result (null when never run). */
  consistency: SeriesConsistencyResult | null;
  /** Persisted series-voice-drift result (null when never run). */
  voice_drift: SeriesVoiceDriftResult | null;
}
```

- [ ] **Step 2: Export it from the types barrel**

In `packages/web/types/index.ts`, locate the export block ending with (the C1 addition):

```typescript
} from "./seriesContextPreview";
```

Directly after that block, insert:

```typescript
export type { SeriesDriftSnapshot } from "./seriesDrift";
```

- [ ] **Step 3: Add the API client method**

In `packages/web/lib/api/series.ts`:

3a. Extend the `import type { … } from "@/types";` list (alphabetical position after `SeriesCreate`) with:

```typescript
  SeriesDriftSnapshot,
```

3b. In the `// --- Series Cross-Novel Drift (Spec 4 Tasks 2–3) ---` section, after the `checkSeriesVoiceDrift` entry and before the closing `};`, append:

```typescript
  /**
   * GET /series/{id}/consistency/{novelId} — the persisted drift snapshot
   * (SERIES-004 Slice 6 / C2): both check results as one document plus the
   * server-computed stale flag. `generated_at` is null when nothing was
   * persisted yet (200 with an all-null body — never an error).
   */
  getDriftSnapshot: (seriesId: string, novelId: string) =>
    fetchApi<SeriesDriftSnapshot>(`/series/${seriesId}/consistency/${novelId}`),
```

- [ ] **Step 4: Type-check + lint**

Run: `cd packages/web && pnpm type-check && pnpm lint:check`
Expected: PASS.

- [ ] **Step 5: Commit (via Platform, verbatim)**

```bash
git add packages/web/types/seriesDrift.ts packages/web/types/index.ts \
        packages/web/lib/api/series.ts
```

Commit message:

```
feat(web): add SeriesDriftSnapshot type + getDriftSnapshot API client

C2: the frontend contract for the persisted drift snapshot. RULE-17 parity
with SeriesDriftSnapshotResponse (snake_case, sections reuse the existing
SeriesConsistencyResult / SeriesVoiceDriftResult mirrors — no re-shaping);
new types/seriesDrift.ts file (RULE-04 split, seriesContextPreview.ts
precedent). seriesApi.getDriftSnapshot hits GET /series/{id}/consistency/
{novelId}; the all-null body when nothing is persisted is a 200, not an
error, so the hook needs no 404 special-casing.
```

---

### Task 8: i18n — snapshot keys (en/de/fr)

**Files:**
- Modify: `packages/i18n/messages/en/studio.json`
- Modify: `packages/i18n/messages/de/studio.json`
- Modify: `packages/i18n/messages/fr/studio.json`

**Interfaces:**
- Consumes: the existing `series.drift` object in each locale (verified: its last member is the `noProfileReason` object).
- Produces (verbatim for Task 9): keys `series.drift.snapshot.restored` (ICU date param `generatedAt`) and `series.drift.snapshot.stale`.

- [ ] **Step 1: Add the keys to all three locales**

In each file, locate the `"noProfileReason": { … }` object inside `series` → `drift` (its `no_chapters_with_prose` entry is the last member). Directly after that object's closing `}`, add a comma and the new `snapshot` object.

en (`packages/i18n/messages/en/studio.json`):

```json
"snapshot": {
  "restored": "Saved result from {generatedAt, date, medium}",
  "stale": "Chapter texts changed since this check — run it again for current results."
}
```

de (`packages/i18n/messages/de/studio.json`):

```json
"snapshot": {
  "restored": "Gespeichertes Ergebnis vom {generatedAt, date, medium}",
  "stale": "Die Kapiteltexte haben sich seit dieser Prüfung geändert — für aktuelle Ergebnisse erneut prüfen."
}
```

fr (`packages/i18n/messages/fr/studio.json`):

```json
"snapshot": {
  "restored": "Résultat enregistré du {generatedAt, date, medium}",
  "stale": "Les textes des chapitres ont changé depuis cette vérification — relancez-la pour des résultats à jour."
}
```

- [ ] **Step 2: Verify JSON validity + key parity**

Run: `python3 -c "import json; [json.load(open(f'packages/i18n/messages/{l}/studio.json')) for l in ('en','de','fr')]; print('ok')"`
Expected: `ok` (the i18n pre-commit hook enforces locale parity again at commit time).

- [ ] **Step 3: Commit (via Platform, verbatim)**

```bash
git add packages/i18n/messages/en/studio.json \
        packages/i18n/messages/de/studio.json \
        packages/i18n/messages/fr/studio.json
```

Commit message:

```
feat(i18n): add series.drift.snapshot keys (en/de/fr)

C2: UI copy for the persisted drift snapshot in the Bände-Tab panel —
the "restored" hint (ICU date param generatedAt) when saved results are
shown, and the stale warning when the band's chapter texts changed since
the persisted check ran.
```

### Task 9: Query key + hooks + panel — snapshot hydration + stale badge

**Files:**
- Modify: `packages/web/lib/hooks/seriesKeys.ts` (37 lines)
- Modify: `packages/web/lib/hooks/useSeriesDrift.ts` (42 lines)
- Modify: `packages/web/components/series/SeriesDriftPanel.tsx` (190 lines; no enforced web file limit — RULE-04 discipline keeps the additions lean)
- Test: extend `packages/web/components/series/__tests__/SeriesDriftPanel.test.tsx`; create `packages/web/lib/hooks/__tests__/useSeriesDriftSnapshot.test.tsx`

**Interfaces:**
- Consumes: `seriesApi.getDriftSnapshot` + `SeriesDriftSnapshot` (Task 7); i18n keys `series.drift.snapshot.restored` / `.stale` (Task 8); the existing `SeriesConflictList` + `SeriesDriftSummary` renderers (reused verbatim — the snapshot sections have the same shapes as the run results).
- Produces: `seriesKeys.driftSnapshot(seriesId, novelId)`; `useSeriesDriftSnapshot(seriesId, novelId)`; both run mutations invalidate the snapshot query on success; `SeriesDriftPanel` renders persisted results + `data-testid="series-drift-snapshot-hint"`.

- [ ] **Step 1: Add the query key**

In `packages/web/lib/hooks/seriesKeys.ts`, directly after the `bandSummary` entry, insert:

```typescript
  /** Persisted drift snapshot for one band (SERIES-004 Slice 6 / C2). */
  driftSnapshot: (seriesId: string, novelId: string) =>
    [...seriesKeys.novels(seriesId), novelId, "driftSnapshot"] as const,
```

- [ ] **Step 2: Write the failing hook tests**

Create `packages/web/lib/hooks/__tests__/useSeriesDriftSnapshot.test.tsx`:

```tsx
/**
 * Tests for the C2 drift-snapshot hook + run-mutation invalidation.
 *
 * Self-contained QueryClient wrapper (mirrors the useBandSummary test
 * pattern): the API client is module-mocked; the REAL seriesKeys module
 * provides the expected key, so the invalidation assertion does not
 * restate the key shape.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  getDriftSnapshot: vi.fn(),
  checkSeriesConsistency: vi.fn(),
  checkSeriesVoiceDrift: vi.fn(),
}));

vi.mock("@/lib/api/series", () => ({
  seriesApi: api,
}));

import { seriesKeys } from "@/lib/hooks/seriesKeys";
import {
  useSeriesConsistency,
  useSeriesDriftSnapshot,
  useSeriesVoiceDrift,
} from "@/lib/hooks/useSeriesDrift";

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return { wrapper: Wrapper, queryClient };
}

const EMPTY_SNAPSHOT = {
  series_id: "s1",
  novel_id: "n1",
  generated_at: null,
  stale: false,
  consistency: null,
  voice_drift: null,
};

describe("useSeriesDriftSnapshot", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("is disabled until both ids are set", () => {
    api.getDriftSnapshot.mockResolvedValue(EMPTY_SNAPSHOT);
    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useSeriesDriftSnapshot("s1", ""), {
      wrapper,
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(api.getDriftSnapshot).not.toHaveBeenCalled();
  });

  it("fetches the snapshot when enabled", async () => {
    api.getDriftSnapshot.mockResolvedValue({ ...EMPTY_SNAPSHOT, stale: true });
    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useSeriesDriftSnapshot("s1", "n1"), {
      wrapper,
    });

    await waitFor(() => expect(result.current.data?.stale).toBe(true));
    expect(api.getDriftSnapshot).toHaveBeenCalledWith("s1", "n1");
  });
});

describe("run mutations invalidate the snapshot (C2)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("useSeriesConsistency invalidates driftSnapshot on success", async () => {
    api.checkSeriesConsistency.mockResolvedValue({ conflicts: [] });
    const { wrapper, queryClient } = createWrapper();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = renderHook(() => useSeriesConsistency("s1"), { wrapper });

    await act(async () => {
      await result.current.mutateAsync("n1");
    });

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: seriesKeys.driftSnapshot("s1", "n1"),
    });
  });

  it("useSeriesVoiceDrift invalidates driftSnapshot on success", async () => {
    api.checkSeriesVoiceDrift.mockResolvedValue({ result: null, no_profile: null });
    const { wrapper, queryClient } = createWrapper();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = renderHook(() => useSeriesVoiceDrift("s1"), { wrapper });

    await act(async () => {
      await result.current.mutateAsync("n1");
    });

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: seriesKeys.driftSnapshot("s1", "n1"),
    });
  });
});
```

- [ ] **Step 3: Run the hook tests to verify they fail**

Run: `cd packages/web && pnpm test lib/hooks/__tests__/useSeriesDriftSnapshot.test.tsx`
Expected: FAIL — `useSeriesDriftSnapshot` is not exported from `useSeriesDrift.ts` yet (the module rewrite in the NEXT step, Step 4, adds the export; the Step-6 rerun then turns the hook tests green).

- [ ] **Step 4: Extend the hooks (snapshot query + run invalidations)**

Rewrite `packages/web/lib/hooks/useSeriesDrift.ts` as:

```typescript
"use client";

/**
 * TanStack Query hooks for the Series Cross-Novel Drift checks (Spec 4 Task 4
 * + Slice 6 / C2 persistence).
 *
 * Three hooks back the drift surface for one series:
 *
 * - ``useSeriesConsistency``  — POST check a band's chapter prose vs the series
 *   Canon KB (returns the canon contradictions found, possibly empty).
 * - ``useSeriesVoiceDrift``   — POST analyse a band's narrator drift against the
 *   series voice baseline (reuses the novel-level response shape).
 * - ``useSeriesDriftSnapshot`` — GET the persisted latest-wins snapshot for the
 *   selected band (C2): both results as one document + the server-computed
 *   stale flag. Nothing persisted → a 200 with an all-null body (never an
 *   error state), so the panel shows the empty state.
 *
 * Since C2 the two run mutations PERSIST their result server-side; each
 * invalidates the per-band snapshot query on success so the panel refetches
 * the saved state (mirrors ``useBandSummary``'s invalidation pattern).
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { seriesApi } from "@/lib/api/series";
import { seriesKeys } from "./seriesKeys";

/**
 * POST /api/v1/series/{id}/consistency/check.
 * Call `.mutate(novelId)`; the result lands in `.data` (a graceful empty
 * `conflicts` list means no contradictions were found).
 */
export function useSeriesConsistency(seriesId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (novelId: string) => seriesApi.checkSeriesConsistency(seriesId, novelId),
    onSuccess: (_data, novelId) => {
      void queryClient.invalidateQueries({
        queryKey: seriesKeys.driftSnapshot(seriesId, novelId),
      });
    },
  });
}

/**
 * POST /api/v1/series/{id}/voice-drift/check.
 * Call `.mutate(novelId)`; the result lands in `.data` (exactly one of
 * `result` / `no_profile` is set — `no_profile` is the RULE-11 graceful skip).
 */
export function useSeriesVoiceDrift(seriesId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (novelId: string) => seriesApi.checkSeriesVoiceDrift(seriesId, novelId),
    onSuccess: (_data, novelId) => {
      void queryClient.invalidateQueries({
        queryKey: seriesKeys.driftSnapshot(seriesId, novelId),
      });
    },
  });
}

/**
 * GET /api/v1/series/{id}/consistency/{novelId} — the persisted drift
 * snapshot (C2). Disabled until a band is selected. Refetches automatically
 * when the band changes (the novelId is part of the query key).
 */
export function useSeriesDriftSnapshot(seriesId: string, novelId: string) {
  return useQuery({
    queryKey: seriesKeys.driftSnapshot(seriesId, novelId),
    queryFn: () => seriesApi.getDriftSnapshot(seriesId, novelId),
    enabled: !!seriesId && !!novelId,
  });
}
```

- [ ] **Step 5: Extend the panel — snapshot hydration + stale badge + band-change reset**

In `packages/web/components/series/SeriesDriftPanel.tsx`:

5a. Extend the hook import:

```typescript
import { useSeriesConsistency, useSeriesVoiceDrift } from "@/lib/hooks/useSeriesDrift";
```

becomes:

```typescript
import {
  useSeriesConsistency,
  useSeriesDriftSnapshot,
  useSeriesVoiceDrift,
} from "@/lib/hooks/useSeriesDrift";
```

5b. Replace the state/derivation block:

```typescript
  const consistency = useSeriesConsistency(seriesId);
  const drift = useSeriesVoiceDrift(seriesId);

  const [selectedNovelId, setSelectedNovelId] = useState("");
  const isChecking = consistency.isPending || drift.isPending;
  const hasAnyActivity =
    consistency.isPending ||
    drift.isPending ||
    Boolean(consistency.data) ||
    Boolean(drift.data) ||
    consistency.isError ||
    drift.isError;

  function handleCheck(): void {
    if (!selectedNovelId || isChecking) return;
    // Reset so stale results from a previous band clear while the new checks run.
    consistency.reset();
    drift.reset();
    void consistency.mutate(selectedNovelId);
    void drift.mutate(selectedNovelId);
  }
```

with:

```typescript
  const consistency = useSeriesConsistency(seriesId);
  const drift = useSeriesVoiceDrift(seriesId);

  const [selectedNovelId, setSelectedNovelId] = useState("");
  // C2: the persisted snapshot for the selected band (all-null when nothing
  // was saved yet). Fresh run data takes precedence over it below.
  const snapshot = useSeriesDriftSnapshot(seriesId, selectedNovelId);

  const consistencyView = consistency.data ?? snapshot.data?.consistency ?? null;
  const driftView = drift.data ?? snapshot.data?.voice_drift ?? null;

  const isChecking = consistency.isPending || drift.isPending;
  const hasAnyActivity =
    consistency.isPending ||
    drift.isPending ||
    Boolean(consistencyView) ||
    Boolean(driftView) ||
    consistency.isError ||
    drift.isError;

  // The snapshot hint shows only while the persisted snapshot is the visible
  // source (no fresh run data this session). Invariant: sections non-null
  // implies generated_at non-null (a persisted record always carries it).
  const snapshotVisible =
    !consistency.data &&
    !drift.data &&
    !isChecking &&
    (snapshot.data?.consistency != null || snapshot.data?.voice_drift != null);

  function handleSelect(novelId: string): void {
    setSelectedNovelId(novelId);
    // Clear the previous band's fresh results so the panel never mixes
    // bands; the snapshot query re-keys automatically.
    consistency.reset();
    drift.reset();
  }

  function handleCheck(): void {
    if (!selectedNovelId || isChecking) return;
    // Reset so the (now stale) persisted display clears while the checks run.
    consistency.reset();
    drift.reset();
    void consistency.mutate(selectedNovelId);
    void drift.mutate(selectedNovelId);
  }
```

5c. In the band selector, replace:

```tsx
            onChange={(e) => setSelectedNovelId(e.target.value)}
```

with:

```tsx
            onChange={(e) => handleSelect(e.target.value)}
```

5d. Directly after the idle-hint block (`{!hasAnyActivity ? ( … ) : null}` inside the selector card), insert the snapshot hint:

```tsx
        {snapshotVisible && snapshot.data ? (
          <p
            data-testid="series-drift-snapshot-hint"
            className="pt-1 text-xs text-muted-foreground"
          >
            {snapshot.data.stale
              ? t("series.drift.snapshot.stale")
              : t("series.drift.snapshot.restored", {
                  generatedAt: new Date(snapshot.data.generated_at ?? 0),
                })}
          </p>
        ) : null}
```

5e. In the consistency result section, replace:

```tsx
          {consistency.data ? (
            <SeriesConflictList
              conflicts={consistency.data.conflicts}
              summary={consistency.data.summary}
            />
          ) : null}
```

with:

```tsx
          {consistencyView ? (
            <SeriesConflictList
              conflicts={consistencyView.conflicts}
              summary={consistencyView.summary}
            />
          ) : null}
```

and in the voice-drift section, replace:

```tsx
          {drift.data ? <SeriesDriftSummary response={drift.data} /> : null}
```

with:

```tsx
          {driftView ? <SeriesDriftSummary response={driftView} /> : null}
```

Also extend the component header comment's hook list (the doc block that currently lists `useSeriesConsistency` and `useSeriesVoiceDrift` — there is no "stateless" bullet to update) with: `- ``useSeriesDriftSnapshot`` — GET the persisted latest-wins snapshot (C2); the panel hydrates from it instead of an empty state and badges it stale when the band's texts changed.`

- [ ] **Step 6: Run all new/affected web tests**

Run: `cd packages/web && pnpm test lib/hooks/__tests__/useSeriesDriftSnapshot.test.tsx components/series/__tests__/SeriesDriftPanel.test.tsx`
Expected: hook tests PASS (3); panel tests FAIL (the panel test's module mock does not yet export `useSeriesDriftSnapshot` — Step 7 fixes that).

- [ ] **Step 7: Extend the panel component tests**

In `packages/web/components/series/__tests__/SeriesDriftPanel.test.tsx`:

7a. Extend the hoisted `mock` state with a snapshot member (inside the `vi.hoisted(() => ({ … }))` object, after `drift`):

```typescript
  snapshot: {
    data: undefined as
      | {
          stale: boolean;
          generated_at: string | null;
          consistency?: unknown;
          voice_drift?: unknown;
        }
      | undefined,
  },
```

7b. Extend the module mock:

```typescript
vi.mock("@/lib/hooks/useSeriesDrift", () => ({
  useSeriesConsistency: () => mock.consistency,
  useSeriesVoiceDrift: () => mock.drift,
}));
```

becomes:

```typescript
vi.mock("@/lib/hooks/useSeriesDrift", () => ({
  useSeriesConsistency: () => mock.consistency,
  useSeriesVoiceDrift: () => mock.drift,
  useSeriesDriftSnapshot: () => ({ data: mock.snapshot.data }),
}));
```

7c. In `resetMocks()`, after the `mock.drift = { … }` assignment, add:

```typescript
  mock.snapshot = { data: undefined };
```

7d. Append the new test class (inside the existing `describe("SeriesDriftPanel", …)`):

```typescript
  it("renders the persisted snapshot sections before any run (C2)", async () => {
    mock.snapshot = {
      data: {
        stale: false,
        generated_at: "2026-08-16T12:00:00.000Z",
        consistency: consistencyData,
        voice_drift: driftData,
      },
    };

    const user = userEvent.setup();
    render(<SeriesDriftPanel seriesId={SERIES_ID} />);
    await user.selectOptions(screen.getByTestId("series-drift-band-select"), "novel-2");

    expect(screen.getByTestId("series-drift-consistency-section")).toBeDefined();
    expect(screen.getByTestId("series-drift-summary-stub")).toBeDefined();
    expect(screen.getByTestId("series-drift-snapshot-hint").textContent).toContain(
      "series.drift.snapshot.restored",
    );
  });

  it("shows the stale warning when the snapshot is stale", async () => {
    mock.snapshot = {
      data: {
        stale: true,
        generated_at: "2026-08-16T12:00:00.000Z",
        consistency: consistencyData,
        voice_drift: driftData,
      },
    };

    const user = userEvent.setup();
    render(<SeriesDriftPanel seriesId={SERIES_ID} />);
    await user.selectOptions(screen.getByTestId("series-drift-band-select"), "novel-2");

    expect(screen.getByTestId("series-drift-snapshot-hint").textContent).toContain(
      "series.drift.snapshot.stale",
    );
  });

  it("prefers fresh run data over the persisted snapshot", async () => {
    mock.snapshot = {
      data: {
        stale: true,
        generated_at: "2026-08-16T12:00:00.000Z",
        consistency: consistencyData,
        voice_drift: driftData,
      },
    };
    mock.consistency = {
      data: { ...consistencyData, summary: "Fresh run." },
      isPending: false,
      isError: false,
      mutate: vi.fn(),
      reset: vi.fn(),
    };

    const user = userEvent.setup();
    render(<SeriesDriftPanel seriesId={SERIES_ID} />);
    await user.selectOptions(screen.getByTestId("series-drift-band-select"), "novel-2");

    // Fresh run summary wins over the snapshot's "All clear."
    expect(
      (screen.getByTestId("series-conflict-list-stub") as HTMLElement).dataset.summary,
    ).toBe("Fresh run.");
    // And the snapshot hint is hidden (fresh data is the visible source).
    expect(screen.queryByTestId("series-drift-snapshot-hint")).toBeNull();
  });

  it("resets fresh results when the band selection changes", async () => {
    mock.consistency = {
      data: consistencyData,
      isPending: false,
      isError: false,
      mutate: vi.fn(),
      reset: vi.fn(),
    };
    const user = userEvent.setup();
    render(<SeriesDriftPanel seriesId={SERIES_ID} />);
    await user.selectOptions(screen.getByTestId("series-drift-band-select"), "novel-2");

    await user.selectOptions(screen.getByTestId("series-drift-band-select"), "novel-1");

    expect(mock.consistency.reset).toHaveBeenCalled();
  });
```

- [ ] **Step 8: Run the web gates**

Run: `cd packages/web && pnpm test components/series/__tests__/SeriesDriftPanel.test.tsx lib/hooks/__tests__/useSeriesDriftSnapshot.test.tsx && pnpm type-check && pnpm lint:check`
Expected: PASS all.

- [ ] **Step 9: Commit (via Platform, verbatim)**

```bash
git add packages/web/lib/hooks/seriesKeys.ts \
        packages/web/lib/hooks/useSeriesDrift.ts \
        packages/web/components/series/SeriesDriftPanel.tsx \
        packages/web/components/series/__tests__/SeriesDriftPanel.test.tsx \
        packages/web/lib/hooks/__tests__/useSeriesDriftSnapshot.test.tsx
```

Commit message:

```
feat(web/series): hydrate drift panel from persisted snapshot + stale badge

C2: the Bände-Tab drift panel loads the persisted latest-wins snapshot
instead of an empty state when one exists (design §5 "frontend loads
persisted snapshot").

- seriesKeys.driftSnapshot(seriesId, novelId) — the per-band snapshot key.
- useSeriesDriftSnapshot — GET query, disabled until a band is selected;
  the all-null body (nothing persisted) is a 200, so no error state.
  Both run mutations now invalidate the snapshot on success (the server
  persisted their section) — the useBandSummary invalidation pattern.
- SeriesDriftPanel: fresh run data takes precedence, then the snapshot
  (consistencyView/driftView); the snapshot hint shows "Saved result
  from {date}" (ICU) or the stale warning when the band's texts changed
  since the persisted check; selecting a different band resets the fresh
  results so the panel never mixes bands; renderers (SeriesConflictList +
  SeriesDriftSummary) reused verbatim — the snapshot sections carry the
  same shapes as the run results.
- Tests: hook (enabled-gating, fetch, both invalidations — key asserted
  via the real seriesKeys module) + panel (snapshot sections render,
  stale badge, fresh-data precedence, band-change reset).

Refs: docs/superpowers/specs/2026-08-14-post-export-followups-design.md §5 (C2)
```

### Task 10: ADR-079 amendment + SERIES-004 + CURRENT_STATE + slice gates

**Files:**
- Modify: `docs/architecture/decisions/ADR-079-series-cross-novel-drift.md`
- Modify: `docs/features/series/SERIES-004-cross-novel-drift.md`
- Modify: `docs/_shared/CURRENT_STATE.md`

**Interfaces:**
- Consumes: everything landed in Tasks 1–9.
- Produces: the post-implementation amendment (design §5: "ADR-079 anticipated Slice 6 — documented as a post-implementation amendment to ADR-079, no new ADR"); honest doc state; the slice-final gate run.

- [ ] **Step 1: Amend ADR-079**

In `docs/architecture/decisions/ADR-079-series-cross-novel-drift.md`:

1a. In the status header block, replace the sentence:

```
> Slice 6 (persistence —
> `GET …/consistency/{novel_id}` + results repository) is a deferred out-of-v1 follow-up, not
> part of this ADR's decision.
```

with:

```
> Slice 6 (persistence —
> `GET …/consistency/{novel_id}` + results repository) landed 2026-08-16 as a
> post-implementation amendment (C2) — see *Amendment* below.
```

1b. In the **Decision** section, replace the bullet:

```
- **Persistence — stateless (v1).** The v1 check runs the agent and returns the result; it
  persists nothing. A results repository + the `GET …/consistency/{novel_id}` retrieval
  endpoint from the plan are deferred to a follow-up slice.
```

with:

```
- **Persistence — stateless (v1), amended 2026-08-16.** The v1 check ran the agent and
  returned the result without persisting. Slice 6 (C2) added the results repository +
  the `GET …/consistency/{novel_id}` retrieval endpoint — see the *Amendment* section.
```

1c. In the **Retrofit-Plan → 2. Migration steps (vertical slices)** list, replace:

```
6. **Slice 6 (deferred follow-up):** results repository + `GET …/consistency/{novel_id}`
   retrieval endpoint (persistence). ⏳ Out of v1 scope.
```

with:

```
6. **Slice 6 — Drift Persistence (C2):** results repository + `GET …/consistency/{novel_id}`
   retrieval endpoint. ✅ Landed 2026-08-16 — see the *Amendment* section.
```

1d. In the **Review Trigger** checklist, replace the open item:

```
- [ ] If **persistence** is needed — add the results repository + the
      `GET …/consistency/{novel_id}` retrieval endpoint (deferred from v1).
```

with:

```
- [x] ~~If **persistence** is needed — add the results repository + the
      `GET …/consistency/{novel_id}` retrieval endpoint (deferred from v1).~~
      **Landed 2026-08-16 (C2 / Slice 6)** — see the *Amendment* section.
```

1e. Directly BEFORE the `## Cross-References` heading, insert the amendment section:

```markdown
## Amendment (2026-08-16) — Slice 6: Drift Persistence (C2)

Post-implementation amendment per the Post-Export Follow-ups program design §5
(`docs/superpowers/specs/2026-08-14-post-export-followups-design.md`). The v1
decision's stateless persistence bullet is superseded as follows; every other
decision of this ADR stands unchanged.

- **Storage — `series_drift_results` (migration 0040).** ONE record per novel
  (`novel_id` PK + UNIQUE + FK `novels.id` CASCADE — the `band_summaries` 1:1
  pattern). Latest-wins: a new run overwrites its section; no history rows
  (trajectory comparison is YAGNI, design §5.1). The single JSONB column holds
  the composite document `{consistency, voice_drift}` — the **existing run-result
  models serialized verbatim** (`SeriesConsistencyCheckResponse` +
  `AuthorVoiceDriftResponse`, RULE-22 reuse — never re-shaped).
- **Wrapper service, not service edits.** `SeriesDriftPersistenceService` wraps the
  two UNCHANGED run services (both at their RULE-04 file-size ceilings; zero
  regression surface — the Decision-4 pattern applied to persistence). Each check
  POST runs its check, persists its section via an ATOMIC per-section JSONB-merge
  upsert (`ON CONFLICT (novel_id) DO UPDATE`, `result || excluded.result` — the
  panel fires both POSTs in parallel; a load-or-create would PK-collide), and
  returns the result verbatim. A store failure degrades gracefully (RULE-11:
  the LLM cost is paid; `series_drift_persist_failed` warning; result returned).
- **Staleness — input fingerprint (ADR-045 scheme reuse).** On save, the band's
  position-ordered non-empty chapter texts (`list_by_novel`, the consistency
  check's read path) are hashed with `fingerprint_chapter_texts` — built on the
  ADR-045 `_hash_payload` (SHA-256 + canonical JSON + `narrare:adr045:v1`
  domain separator); no new hash scheme, raw prose never stored. `GET` recomputes
  and returns `stale: true/false`. Record-level `generated_at` stamps the last
  completed write of either check. Known residual of the single record-level
  fingerprint: if the band's texts are edited between two check runs, the later
  write's fingerprint masks the older sibling section — `stale: false` while one
  section predates the edit (accepted; faithful to the design's
  single-fingerprint model).
- **Retrieval — `GET /api/v1/series/{series_id}/consistency/{novel_id}`** (the
  plan's originally sketched shape): one fetch returns the composite snapshot +
  staleness; nothing persisted → a 200 all-null snapshot (never an error).
- **Frontend.** The Bände-Tab `SeriesDriftPanel` hydrates from the persisted
  snapshot instead of an empty state (fresh run data takes precedence) and shows
  a stale badge when the band's texts changed since the persisted check.
```

- [ ] **Step 2: Update the SERIES-004 feature spec**

In `docs/features/series/SERIES-004-cross-novel-drift.md`:

2a. In the API list, replace the deferred entry:

```markdown
  - `GET /api/v1/series/{id}/consistency/{novel_id}` — *(deferred)* results
    retrieval (persistence is a follow-up)
```

with:

```markdown
  - `GET /api/v1/series/{id}/consistency/{novel_id}` — the persisted latest-wins
    drift snapshot (both check results as one document) + a `stale` flag that
    flips when the band's chapter texts changed since the check (C2 / Slice 6)
```

2b. Sweep the remaining stateless mentions and update each honestly:

Run: `rg -n "stateless|Stateless" docs/features/series/SERIES-004-cross-novel-drift.md`

Expected: exactly the three verified anchors — the "Persistence — stateless (v1)" bullet, the "Stateless v1" limitation line, and the status-note "**Stateless v1** — Slice 6 (persistence: …) is deferred" sentence. Rewrite each to state that Slice 6 landed 2026-08-16 — checks persist their latest result per band (`series_drift_results`, migration 0040), the panel restores the saved snapshot with a stale badge, and re-running a check is still explicit (the check button re-pays the LLM cost only on demand). The pattern deliberately does NOT include `deferred`: that term over-matches unrelated deferrals in the file (e.g. the "Full-series batch scan is deferred (YAGNI)" sentence), which must stay untouched.

- [ ] **Step 3: Add the CURRENT_STATE entry**

In `docs/_shared/CURRENT_STATE.md`, add a new dated entry ABOVE the current top entry (the 2026-08-16 C1 context-window-slider entry — the program-approval entry from 2026-08-15 is already two entries down), following the file's established single-paragraph style:

```markdown
Date: 2026-08-16 (**C2 — SERIES-004 Slice 6 Drift Persistence — implemented**; [ADR-079](architecture/decisions/ADR-079-series-cross-novel-drift.md) amended (post-implementation Amendment section — no new ADR); plan [2026-08-16-c2-drift-persistence.md](superpowers/plans/2026-08-16-c2-drift-persistence.md), design §5. The SERIES-004 cross-novel drift checks are now persistent: new table `series_drift_results` (migration `0040_series_drift_results`, novel_id PK + FK CASCADE — the `band_summaries` 1:1 pattern) holds ONE latest-wins record per band whose single JSONB column is the composite document `{consistency, voice_drift}` — the existing run-result models (`SeriesConsistencyCheckResponse` + `AuthorVoiceDriftResponse`) serialized verbatim (RULE-22), each parallel check run upserting only its own key via an atomic `ON CONFLICT DO UPDATE` JSONB `||` merge. New `SeriesDriftPersistenceService` WRAPS the two unchanged run services (`series_voice_drift_service.py` 298/300 and `series_consistency_service.py` 265/300 — byte-identical, zero regression); store failures degrade gracefully (RULE-11 — the paid-for result is returned, `series_drift_persist_failed` logged). Staleness via input fingerprint REUSING the ADR-045 scheme: `fingerprint_chapter_texts` in `narrare_core/ai_invocation/correlation.py` on `_hash_payload` (SHA-256 + canonical JSON + `narrare:adr045:v1` domain — no new hash scheme) over the band's position-ordered non-empty chapter texts (`list_by_novel`, the consistency check's read path); `GET /api/v1/series/{series_id}/consistency/{novel_id}` (the SERIES-004-sketched shape) recomputes and returns `stale: true/false`; nothing persisted → 200 all-null snapshot. Frontend: `seriesKeys.driftSnapshot` + `useSeriesDriftSnapshot` + run-mutation invalidations; `SeriesDriftPanel` hydrates from the persisted snapshot instead of the empty state (fresh run data wins), shows `series.drift.snapshot.{restored,stale}` (en/de/fr, ICU date). §12 gates: migration round-trip (schema_mutating serial phase), latest-wins overwrite (integration), stale-flag flip (unit). Program C2 of C0→C5→C1→C2→C3→C4→B complete; next: C3 DOCX export.)
```

- [ ] **Step 4: Run the slice-final gates**

Run, in order:

```bash
just check-architecture
just typecheck
just lint-check
just test-unit
just test-integration
cd packages/web && pnpm type-check && pnpm lint:check && cd ../..
just test-frontend
```

Expected: PASS on every gate. Additionally verify the design §12 C2 gates are covered by named tests (they are, by construction): round-trip — `tests/integration/test_migration_0040_round_trip.py`; latest-wins — `tests/integration/series/test_series_drift_repository.py::TestStoreSection::test_latest_wins_overwrites_own_section_only`; stale flip — `tests/unit/api/series/test_series_drift_persistence_service.py::TestGetSnapshot::test_edited_texts_flip_stale`.

- [ ] **Step 5: Commit (via Platform, verbatim)**

```bash
git add docs/architecture/decisions/ADR-079-series-cross-novel-drift.md \
        docs/features/series/SERIES-004-cross-novel-drift.md \
        docs/_shared/CURRENT_STATE.md
```

Commit message:

```
docs(series): C2 closure — ADR-079 Slice 6 amendment + SERIES-004 + CURRENT_STATE

C2 (design §5): documents the drift-persistence slice that landed SERIES-004
Slice 6.

- ADR-079: post-implementation Amendment section (no new ADR, per the
  binding decision) — series_drift_results latest-wins storage, the
  wrapper-service pattern (run services byte-identical), the ADR-045
  fingerprint reuse for staleness, the GET retrieval shape, and the
  frontend hydration; status header, Decision persistence bullet, Retrofit
  Slice 6, and the Review-Trigger item updated to landed.
- SERIES-004: the GET endpoint entry un-deferred; every stateless mention
  rewritten to the persisted reality (stale badge, explicit re-run).
- CURRENT_STATE: dated C2 entry (program order C0→C5→C1→C2→…; next C3).

Refs: docs/superpowers/specs/2026-08-14-post-export-followups-design.md §5 + §12
```

---

## Self-Review (performed at plan time — findings recorded honestly)

**1. Spec coverage (design §5 binding decisions → tasks):**

| Binding requirement | Task(s) |
|---|---|
| Stored payload: full result set, canon + voice drift as ONE JSON document | 2 (composite JSONB column), 3 (schema reusing the run-result models), 4 (per-section merge), 5 (model_dump/model_validate round-trip test) |
| History model: latest-wins, one record per novel, new run overwrites, `generated_at` | 2 (novel_id PK, generated_at), 4 (§12 latest-wins integration test), 5 (record-level timestamp semantics documented) |
| Stale flag via input fingerprint; hash stored on save, recomputed on GET | 1 (`fingerprint_chapter_texts` on `_hash_payload`), 5 (`_compute_fingerprint` single path + §12 stale-flip unit test) |
| Retrieval `GET …/consistency/{novel_id}` in the SERIES-004 router namespace | 6 (`router_consistency.py`, the plan-line-29 shape) |
| Alembic migration 0040, RULE-14 atomic | 2 (+ round-trip test per §12) |
| Results repository + service extension (store on run, fetch with stale) | 3 (contracts), 4 (repository), 5 (service) |
| Frontend loads persisted snapshot instead of empty state | 7 (types/api), 8 (i18n), 9 (hook + panel) |
| ADR-079 post-implementation amendment, no new ADR | 10 |
| §12 gates: round-trip / latest-wins / stale flip | 2 / 4 / 5 (named tests) |

No gaps found.

**2. Placeholder scan:** all code steps carry verbatim code; the two Step-7d drafting artifacts (a superseded intermediate assignment and its cleanup note) were removed at plan time — every test snippet is final. Commit messages are complete and typo-free.

**3. Type consistency (cross-task names):** `fingerprint_chapter_texts` (T1 → T5 import); `SeriesDriftResult` / `series_drift_results` (T2 → T3/T4/T5); `DriftSection`, `store_section(novel_id, *, section, document, fingerprint)`, `get`, `check_and_store_consistency`, `check_and_store_voice_drift`, `get_snapshot` (T3 contracts = T4 repository = T5 service = T6 routers/tests); `SeriesDriftSnapshotResponse` fields (T3 = T6 GET response = T7 TS mirror field-for-field, snake_case); `seriesKeys.driftSnapshot` = `getDriftSnapshot` = `useSeriesDriftSnapshot` (T7/T9); i18n keys `series.drift.snapshot.restored|stale` (T8 = T9 panel). Verified consistent.

**4. Design-doc discrepancies found during investigation (reported to the coordinator, resolved by the locked rulings in Global Constraints):** (a) design §5's "new run overwrites" + "ONE JSON document" is underspecified for the fact that the two checks are separate parallel POSTs — resolved by the per-section JSONB-merge ruling; (b) the design does not state GET behavior when nothing is persisted — resolved by the 200-all-null ruling; (c) design §5 names no degradation policy for store failures — resolved by the RULE-11 ruling. The GET path itself matches the SERIES-004 plan's line-29 sketch exactly (`GET /api/v1/series/{id}/consistency/{novel_id}`) — no discrepancy.
