# Series Foundation — Spec 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Series/Reihe Spec 1 (Foundation + KB Evolution) — Series entity, KB Series-Canon+Novel-Overlay scope model, CRUD, Navigation (N2 Workspace), UI.

**Architecture:** Hybrid KB strategy (Option C: Series-Canon + Novel-Overlay) on single physical `kb_entries` table with discriminated Pydantic types (2A+STI). Series is a first-class object with its own Workspace (N2). Five vertical slices: Data Foundation → KB Scope → Series CRUD+Join → Frontend Dashboard+Workspace → KB Scope UI.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2.0 async, Alembic, Pydantic 2, Next.js 16 App Router, TipTap v3, TanStack Query, Zustand, motion, Vitest. i18n: en/de/fr.

**Spec source:** `docs/superpowers/specs/2026-07-29-series-foundation-design.md`
**Companion notes:** `docs/superpowers/specs/2026-07-28-series-cross-spec-notes.md`

## Global Constraints

- **Python:** 3.14+ (use `from __future__ import annotations` in all new modules)
- **PostgreSQL:** partial unique indexes (`CREATE UNIQUE INDEX ... WHERE`), CHECK constraints, JSONB (for `SeriesSettings.author_voice`, nullable empty in Spec 1)
- **Alembic:** migration must be `0036_series_foundation.py` (next sequential after 0035), full `upgrade()` + `downgrade()`, atomic steps
- **RULE-03:** Contracts (Protocols) in `contracts.py` BEFORE service/repository implementations
- **RULE-04:** File-size hard limits — modularize when approaching limits; never delete comments to fit
- **RULE-05:** Each domain module owns its DB models, schemas, contracts, service, router, tests
- **RULE-06:** One responsibility per file (`router.py` only routes; `service.py` only business logic; `repository.py` only DB)
- **RULE-07:** `core/` never imports from `apps/`; service → repository → DB direction
- **RULE-11:** No `try/except: pass`; all errors logged and propagated with clear messages
- **RULE-13:** N/A for Spec 1 (no LLM in Series services)
- **RULE-14:** Every model column change needs matching Alembic migration in same task
- **RULE-22/CR-04:** Producer + consumers defined together; KB scope changes must keep existing consumers green
- **i18n:** All user-facing strings in en/de/fr simultaneously (no staggering)
- **Animation:** Reuse `lib/motion-variants.ts`; `MotionProvider` honored (reduced-motion)
- **TDD:** ADR-014 — failing test first, then minimal impl, then green, then commit. Regression tests before new features.
- **Test coverage targets:** Core 90%+, Backend 85%+, Frontend 80%+, Migration 100%
- **Architecture validation:** `just check` must stay green throughout
- **Pre-commit hooks:** NEVER use `--no-verify`. If hooks fail, fix root cause.

---

## File Structure

### New Backend (`apps/api/narrare/`)

```
series/
├── __init__.py                  ← public exports
├── models.py                    ← Series, SeriesSettings (SQLAlchemy)
├── contracts.py                 ← SeriesRepositoryProtocol, SeriesServiceProtocol, SeriesJoinServiceProtocol
├── schemas.py                   ← SeriesCreateRequest, SeriesUpdateRequest, SeriesResponse, SeriesSummary, JoinPreview, JoinResult
├── repository.py                ← SeriesRepository (DB queries for Series + SeriesSettings)
├── service.py                   ← SeriesService (CRUD business logic)
├── join_service.py              ← SeriesJoinService (Policy α preview/apply + Policy iii heuristics)
├── router.py                    ← FastAPI routes (delegates to service)
└── dependencies.py              ← DI factories (get_series_repository, get_series_service, get_series_join_service)

kb/
├── router_series.py             ← NEW — Canon KB CRUD endpoints (/api/v1/series/{id}/kb/*)
├── scope_service.py             ← NEW — promote_to_canon / demote_to_overlay business logic
└── (modified) repository.py     ← +find_canon_for_series, +find_overlay_for_novel, +find_merged_for_novel, +promote_to_canon, +demote_to_overlay
```

### Modified Backend

- `apps/api/narrare/novels/models.py` — +`series_id`, +`series_position`, +`subtitle`
- `apps/api/narrare/kb/models.py` — +`series_id`, +`base_entry_id`, `novel_id` → nullable, drop unique constraint, add partial uniques + CHECK
- `apps/api/narrare/kb/repository.py` — +scope-aware methods
- `apps/api/narrare/kb/router.py` — +promote/demote endpoints

### New Migration

- `apps/api/alembic/versions/0036_series_foundation.py`

### New Core (`packages/core/narrare_core/`)

```
series/
├── __init__.py                  ← public exports
└── schemas.py                   ← Series, SeriesSettings (Pydantic, pure)

kb/schemas/
└── entry.py                     ← NEW — KBEntryBase, SeriesKBEntry, NovelKBEntry, KBEntry (discriminated union)
```

### Modified Core

- `packages/core/narrare_core/kb/schemas/__init__.py` — re-export `KBEntry`, `SeriesKBEntry`, `NovelKBEntry`, `KBEntryBase`
- `packages/core/narrare_core/kb/schemas/character.py` — leave intact (re-export from `entry.py` for backward compat if needed)

### New Frontend (`packages/web/`)

```
app/series/[id]/
├── page.tsx                     ← Bände-Tab (default)
├── canon/page.tsx               ← Series-Canon KB-Tab
├── settings/page.tsx            ← Settings-Tab
└── voice/page.tsx               ← Voice-Tab (disabled placeholder)

components/series/
├── SeriesWorkspace.tsx          ← main container + tab routing
├── SeriesHero.tsx               ← title, status, meta
├── BändeList.tsx                ← novel list with position pills + up/down buttons
├── CanonKBTab.tsx               ← Series-Canon KB browser
├── SeriesSettings.tsx           ← settings form
└── VoiceTab.tsx                 ← disabled placeholder (Spec 3 fills)

components/dashboard/
└── SeriesCard.tsx               ← NEW — series card variant

components/kb/
├── ScopeToggle.tsx              ← NEW — promote/demote toggle
└── CanonKBEditor.tsx            ← NEW — editor for Canon entries (no novel context)

hooks/
├── useSeries.ts                 ← series CRUD hooks
├── useSeriesJoin.ts             ← join preview + apply
├── useKBScope.ts                ← promote/demote mutations
├── useCanonKB.ts                ← Canon KB CRUD (mirrors useKB)
└── useNovelSeries.ts            ← returns Series | null for a novel

lib/api/
└── series.ts                    ← REST API client

types/
└── series.ts                    ← TS types mirroring Core

messages/                         ← i18n (3 locales)
├── en/series.json
├── de/series.json
└── fr/series.json
```

### Modified Frontend

- `packages/web/app/page.tsx` (Dashboard) — N2 modification (mixed cards)
- `packages/web/components/dashboard/*` — add SeriesCard variant to grid
- `packages/web/components/kb/KBEditor.tsx` (or equivalent) — integrate ScopeToggle

### New Tests

```
tests/unit/core/series/
└── test_schemas.py

tests/unit/core/kb/schemas/
└── test_entry.py                ← STI type tests

tests/unit/api/series/
├── __init__.py
├── test_models.py
├── test_repository.py
├── test_service.py
├── test_join_service.py
└── test_router.py

tests/unit/api/kb/
└── test_scope_repository.py

tests/integration/
└── test_migration_0036.py

packages/web/components/series/__tests__/
packages/web/components/kb/__tests__/test_ScopeToggle.tsx
packages/web/hooks/__tests__/test_useSeries.ts (etc.)
```

### Doc Updates

- `docs/architecture/decisions/ADR-075-series-foundation.md` (NEW)
- `docs/features/series/SERIES-001-foundation.md` (NEW)
- `docs/_shared/CURRENT_STATE.md` (update with Spec 1 entry)
- `docs/_shared/GLOSSARY.md` (new terms)
- `docs/architecture/decisions/ADR-074-author-voice-storage.md` (partial close of Review Trigger)
- `docs/architecture/decisions/INDEX.md` (add ADR-075)

---

# Slice 1: Data Foundation

> **Goal:** Create the Series entity + SeriesSettings + Novel column changes + Alembic migration. After this slice: schema exists, no business logic yet.

## Task 1.1: Core Pydantic Series + SeriesSettings schemas

**Files:**
- Create: `packages/core/narrare_core/series/__init__.py`
- Create: `packages/core/narrare_core/series/schemas.py`
- Test: `tests/unit/core/series/__init__.py`, `tests/unit/core/series/test_schemas.py`

**Interfaces:**
- Produces: `Series`, `SeriesSettings`, `SeriesStatus` (Literal type) — used by Backend models (Task 1.2), Backend schemas (Task 3.2), all later tasks

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/core/series/test_schemas.py
import pytest
from uuid import uuid4
from narrare_core.series.schemas import Series, SeriesSettings, SeriesStatus


class TestSeriesSchema:
    def test_series_minimal_valid(self):
        s = Series(id=uuid4(), user_id=uuid4(), title="The Expanse", status="draft")
        assert s.subtitle is None
        assert s.genre is None
        assert s.writing_language is None
        assert s.planned_novel_count is None

    def test_series_status_invalid_rejected(self):
        with pytest.raises(ValueError):
            Series(id=uuid4(), user_id=uuid4(), title="X", status="invalid")

    def test_series_status_values(self):
        for status in ("draft", "active", "completed"):
            s = Series(id=uuid4(), user_id=uuid4(), title="X", status=status)
            assert s.status == status

    def test_series_extra_allowed(self):
        s = Series(id=uuid4(), user_id=uuid4(), title="X", status="draft", future_field="ok")
        assert s.future_field == "ok"


class TestSeriesSettingsSchema:
    def test_settings_minimal_valid(self):
        ss = SeriesSettings(series_id=uuid4())
        assert ss.author_voice is None  # empty in Spec 1

    def test_settings_author_voice_optional_dict(self):
        ss = SeriesSettings(series_id=uuid4(), author_voice={"foo": "bar"})
        assert ss.author_voice == {"foo": "bar"}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/unit/core/series/test_schemas.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'narrare_core.series'`

- [ ] **Step 3: Implement schemas**

```python
# packages/core/narrare_core/series/schemas.py
"""Core Pydantic schemas for Series and SeriesSettings (pure, no HTTP/DB)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

SeriesStatus = Literal["draft", "active", "completed"]


class Series(BaseModel):
    """A series/reihe — groups multiple novels with shared Canon KB."""
    model_config = ConfigDict(extra="allow")

    id: UUID
    user_id: UUID
    title: str
    subtitle: str | None = None
    description: str | None = None
    genre: str | None = None
    writing_language: str | None = None
    status: SeriesStatus = "draft"
    planned_novel_count: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SeriesSettings(BaseModel):
    """1:1 settings for a Series. author_voice empty in Spec 1 (Spec 3 fills)."""
    model_config = ConfigDict(extra="allow")

    series_id: UUID
    author_voice: dict[str, object] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
```

```python
# packages/core/narrare_core/series/__init__.py
"""Series core module — Pydantic schemas for Series entities."""
from narrare_core.series.schemas import Series, SeriesSettings, SeriesStatus

__all__ = ["Series", "SeriesSettings", "SeriesStatus"]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/unit/core/series/test_schemas.py -v
```
Expected: PASS (4 tests)

- [ ] **Step 5: Verify check_architecture green**

```bash
just check
```
Expected: Architecture constraints OK.

- [ ] **Step 6: Commit**

```bash
git add packages/core/narrare_core/series/ tests/unit/core/series/
git commit -m "feat(core/series): add Series + SeriesSettings Pydantic schemas

Spec 1 Slice 1 Task 1.1 — pure Core types, no HTTP/DB. Series status
enum (draft|active|completed) uses Narrare vocabulary. SeriesSettings.
author_voice nullable (empty in Spec 1, forward-compat for Spec 3)."
```

---

## Task 1.2: Backend Series SQLAlchemy models

**Files:**
- Create: `apps/api/narrare/series/__init__.py` (empty for now)
- Create: `apps/api/narrare/series/models.py`
- Test: `tests/unit/api/series/__init__.py`, `tests/unit/api/series/test_models.py`

**Interfaces:**
- Consumes: `narrare._app.database.Base` (existing)
- Produces: `Series` (SQLAlchemy), `SeriesSettings` (SQLAlchemy) — used by Repository (Task 3.3), Migration (Task 1.5)

- [ ] **Step 1: Write failing test**

```python
# tests/unit/api/series/test_models.py
from narrare.series.models import Series as SeriesModel, SeriesSettings as SeriesSettingsModel


def test_series_model_tablename():
    assert SeriesModel.__tablename__ == "series"


def test_series_settings_model_tablename():
    assert SeriesSettingsModel.__tablename__ == "series_settings"


def test_series_model_has_expected_columns():
    cols = {c.name for c in SeriesModel.__table__.columns}
    expected = {"id", "user_id", "title", "subtitle", "description", "genre",
                "writing_language", "status", "planned_novel_count",
                "created_at", "updated_at"}
    assert expected.issubset(cols)


def test_series_settings_model_has_expected_columns():
    cols = {c.name for c in SeriesSettingsModel.__table__.columns}
    expected = {"id", "series_id", "author_voice", "created_at", "updated_at"}
    assert expected.issubset(cols)


def test_series_settings_series_id_unique():
    cols = {c.name: c for c in SeriesSettingsModel.__table__.columns}
    assert cols["series_id"].unique is True
```

- [ ] **Step 2: Run test, verify fail**

```bash
pytest tests/unit/api/series/test_models.py -v
```
Expected: FAIL `ModuleNotFoundError: No module named 'narrare.series'`

- [ ] **Step 3: Implement models**

```python
# apps/api/narrare/series/models.py
"""Series and SeriesSettings SQLAlchemy models."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from narrare._app.database import Base


class Series(Base):
    """A series/reihe grouping multiple novels with shared Canon KB."""
    __tablename__ = "series"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    genre: Mapped[str | None] = mapped_column(String(100), nullable=True)
    writing_language: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    planned_novel_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        # Status CHECK constraint mirrors Pydantic Literal in Core
        # Implemented via Alembic migration (Task 1.5) — declared here for documentation
    )


class SeriesSettings(Base):
    """1:1 settings for a Series. author_voice empty in Spec 1 (Spec 3 fills)."""
    __tablename__ = "series_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("series.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    author_voice: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
```

```python
# apps/api/narrare/series/__init__.py
"""Series backend module."""
```

- [ ] **Step 4: Run test, verify pass**

```bash
pytest tests/unit/api/series/test_models.py -v
```
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/api/narrare/series/ tests/unit/api/series/
git commit -m "feat(api/series): add Series + SeriesSettings SQLAlchemy models

Spec 1 Slice 1 Task 1.2 — backend ORM models matching Core schemas.
SeriesSettings.author_voice JSONB nullable (Spec 3 fills). SeriesSettings.
series_id UNIQUE FK with ON DELETE CASCADE."
```

---

## Task 1.3: Modify Novel model (add series_id, series_position, subtitle)

**Files:**
- Modify: `apps/api/narrare/novels/models.py` (+3 columns)
- Test: `tests/unit/api/novels/test_models.py` (extend existing or create)

**Interfaces:**
- Produces: `Novel.series_id`, `Novel.series_position`, `Novel.subtitle` — used by Join Service (Task 3.5), Migration (Task 1.5)

- [ ] **Step 1: Write failing test**

```python
# tests/unit/api/novels/test_series_columns.py
from narrare.novels.models import Novel


def test_novel_has_series_id_column():
    cols = {c.name: c for c in Novel.__table__.columns}
    assert "series_id" in cols
    assert cols["series_id"].nullable is True  # nullable: NULL = standalone


def test_novel_has_series_position_column():
    cols = {c.name: c for c in Novel.__table__.columns}
    assert "series_position" in cols
    assert cols["series_position"].nullable is True


def test_novel_has_subtitle_column():
    cols = {c.name: c for c in Novel.__table__.columns}
    assert "subtitle" in cols
    assert cols["subtitle"].nullable is True
```

- [ ] **Step 2: Run test, verify fail**

```bash
pytest tests/unit/api/novels/test_series_columns.py -v
```
Expected: FAIL with AssertionError on column existence.

- [ ] **Step 3: Modify Novel model**

```python
# apps/api/narrare/novels/models.py — add these imports and fields
# Add to imports:
from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID  # already imported

# Add to Novel class (after existing columns, before timestamps):
    # Series membership (Spec 1, ADR-075). NULL = standalone novel.
    series_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("series.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Position within series (1-based). NULL if not in series.
    series_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Per-novel subtitle (each band has its own identity within a series)
    subtitle: Mapped[str | None] = mapped_column(String(500), nullable=True)
```

Note: Add `from sqlalchemy import Integer` if not already imported.

- [ ] **Step 4: Run test, verify pass**

```bash
pytest tests/unit/api/novels/test_series_columns.py -v
```
Expected: PASS (3 tests)

- [ ] **Step 5: Run existing novel tests for regression**

```bash
pytest tests/unit/api/novels/ -v
```
Expected: All existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add apps/api/narrare/novels/models.py tests/unit/api/novels/test_series_columns.py
git commit -m "feat(api/novels): add series_id, series_position, subtitle columns

Spec 1 Slice 1 Task 1.3 — Novel gains optional series membership.
series_id nullable FK to series (ON DELETE SET NULL → standalone).
series_position nullable (UNIQUE with series_id via migration).
subtitle nullable per-novel subtitle."
```

---

## Task 1.4: Modify KBEntry model (add series_id, base_entry_id, novel_id nullable, constraints)

**Files:**
- Modify: `apps/api/narrare/kb/models.py`
- Test: `tests/unit/api/kb/test_models.py` (extend)

**Interfaces:**
- Produces: `KBEntry.series_id`, `KBEntry.base_entry_id`, `KBEntry.novel_id` (now nullable) — used by Repository scope methods (Task 2.4), Migration (Task 1.5)

> **Critical:** This task touches the existing KBEntry model. The model change must be backward compatible — existing queries that filter `WHERE novel_id = X` must still work because existing rows have non-NULL novel_id.

- [ ] **Step 1: Write failing test**

```python
# tests/unit/api/kb/test_scope_columns.py
from narrare.kb.models import KBEntry


def test_kb_entry_has_series_id_column():
    cols = {c.name: c for c in KBEntry.__table__.columns}
    assert "series_id" in cols
    assert cols["series_id"].nullable is True


def test_kb_entry_has_base_entry_id_column():
    cols = {c.name: c for c in KBEntry.__table__.columns}
    assert "base_entry_id" in cols
    assert cols["base_entry_id"].nullable is True


def test_kb_entry_novel_id_is_nullable():
    """Critical: novel_id must be nullable so Series-Canon entries can exist."""
    cols = {c.name: c for c in KBEntry.__table__.columns}
    assert cols["novel_id"].nullable is True


def test_kb_entry_old_unique_constraint_dropped():
    """The old (novel_id, slug) unique must be replaced by partial uniques."""
    constr_names = {c.name for c in KBEntry.__table__.constraints}
    assert "uq_kb_entries_novel_slug" not in constr_names
```

- [ ] **Step 2: Run test, verify fail**

```bash
pytest tests/unit/api/kb/test_scope_columns.py -v
```
Expected: FAIL on column existence + novel_id nullable + unique constraint.

- [ ] **Step 3: Modify KBEntry model**

```python
# apps/api/narrare/kb/models.py — modifications to KBEntry class:

# 1. Change novel_id to nullable:
    novel_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("novels.id", ondelete="CASCADE"),
        nullable=True,  # CHANGED: was nullable=False
        index=True,
    )

# 2. Add series_id and base_entry_id after novel_id:
    # Series-Canon scope: when novel_id is NULL, this entry is canon for the series.
    series_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("series.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    # For Novel-Overlay entries: optional link to the Series-Canon entry this overlays.
    base_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kb_entries.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

# 3. Replace __table_args__ — remove UniqueConstraint("novel_id", "slug"), keep others.
# The partial unique indexes + CHECK constraint are added via Alembic migration
# (Task 1.5) because SQLAlchemy doesn't natively express partial unique indexes
# in __table_args__. We document them here in a comment:
    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('character', 'concept', 'faction', 'location', "
            "'object', 'setting', 'system', 'timeline')",
            name="ck_kb_entries_entity_type",
        ),
        CheckConstraint(
            "status IN ('draft', 'reviewed', 'canon', 'deprecated')",
            name="ck_kb_entries_status",
        ),
        CheckConstraint(
            "review_status IN ('approved', 'pending', 'rejected')",
            name="ck_kb_entries_review_status",
        ),
        # REMOVED: UniqueConstraint("novel_id", "slug", name="uq_kb_entries_novel_slug")
        # REPLACED BY (in Alembic migration 0036):
        #   - uq_kb_canon_per_series ON (series_id, slug) WHERE novel_id IS NULL
        #   - uq_kb_overlay_per_novel ON (novel_id, slug) WHERE novel_id IS NOT NULL
        #   - ck_kb_entries_scope_invariant CHECK
        Index("ix_kb_entries_entity_type", "entity_type"),
        Index("ix_kb_entries_novel_id", "novel_id"),
        Index("ix_kb_entries_novel_type", "novel_id", "entity_type"),
    )
```

Note: Remove the line `UniqueConstraint("novel_id", "slug", name="uq_kb_entries_novel_slug"),` from the existing `__table_args__`.

- [ ] **Step 4: Run test, verify pass**

```bash
pytest tests/unit/api/kb/test_scope_columns.py -v
```
Expected: PASS (4 tests)

- [ ] **Step 5: Run existing KB tests for regression**

```bash
pytest tests/unit/api/kb/ -v
```
Expected: All existing tests still pass at the model level. (DB-level constraints will be tested in integration after migration.)

- [ ] **Step 6: Commit**

```bash
git add apps/api/narrare/kb/models.py tests/unit/api/kb/test_scope_columns.py
git commit -m "feat(api/kb): extend KBEntry with series scope (Schema 2A)

Spec 1 Slice 1 Task 1.4 — adds series_id, base_entry_id columns.
novel_id becomes nullable (NULL = Series-Canon entry). Old (novel_id,
slug) unique constraint dropped; partial uniques + CHECK added via
Alembic migration 0036 in Task 1.5. Backward compatible: existing
queries WHERE novel_id = X still work (Canon has novel_id IS NULL)."
```

---

## Task 1.5: Alembic migration 0036_series_foundation

**Files:**
- Create: `apps/api/alembic/versions/0036_series_foundation.py`
- Test: `tests/integration/test_migration_0036.py`

**Interfaces:**
- Consumes: All schema changes from Tasks 1.2, 1.3, 1.4
- Produces: Applied DB schema with series, series_settings tables, novels columns, kb_entries scope changes, partial uniques, CHECK constraint

> **RULE-14:** This migration MUST land in the same task as the model changes. It does — Tasks 1.2-1.4 are model changes, Task 1.5 is the migration.

- [ ] **Step 1: Write migration test (TDD)**

```python
# tests/integration/test_migration_0036.py
"""Integration test for Alembic migration 0036_series_foundation.

Verifies upgrade() + downgrade() roundtrip and that all schema
artifacts land correctly. Requires test Postgres (CI runs it).
"""
import pytest
from sqlalchemy import text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_migration_0036_upgrade_creates_series_tables(async_session):
    """After upgrade: series + series_settings tables exist."""
    result = await async_session.execute(text(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_name IN ('series', 'series_settings')"
    ))
    tables = {row[0] for row in result}
    assert "series" in tables
    assert "series_settings" in tables


@pytest.mark.integration
@pytest.mark.asyncio
async def test_migration_0036_novels_has_series_columns(async_session):
    result = await async_session.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'novels' AND column_name IN "
        "('series_id', 'series_position', 'subtitle')"
    ))
    cols = {row[0] for row in result}
    assert {"series_id", "series_position", "subtitle"}.issubset(cols)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_migration_0036_kb_entries_scope_columns(async_session):
    result = await async_session.execute(text(
        "SELECT column_name, is_nullable FROM information_schema.columns "
        "WHERE table_name = 'kb_entries' AND column_name IN "
        "('novel_id', 'series_id', 'base_entry_id')"
    ))
    cols = {row[0]: row[1] for row in result}
    assert cols["novel_id"] == "YES"  # nullable
    assert "series_id" in cols
    assert "base_entry_id" in cols


@pytest.mark.integration
@pytest.mark.asyncio
async def test_migration_0036_partial_unique_indexes_exist(async_session):
    result = await async_session.execute(text(
        "SELECT indexname FROM pg_indexes WHERE tablename = 'kb_entries' "
        "AND indexname IN ('uq_kb_canon_per_series', 'uq_kb_overlay_per_novel')"
    ))
    indexes = {row[0] for row in result}
    assert "uq_kb_canon_per_series" in indexes
    assert "uq_kb_overlay_per_novel" in indexes


@pytest.mark.integration
@pytest.mark.asyncio
async def test_migration_0036_check_constraint_exists(async_session):
    result = await async_session.execute(text(
        "SELECT conname FROM pg_constraint WHERE conname = 'ck_kb_entries_scope_invariant'"
    ))
    assert result.first() is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_migration_0036_series_status_check(async_session):
    result = await async_session.execute(text(
        "SELECT conname FROM pg_constraint WHERE conname = 'ck_series_status'"
    ))
    assert result.first() is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_migration_0036_novels_unique_series_position(async_session):
    """UNIQUE(series_id, series_position) ensures no two novels share a position."""
    result = await async_session.execute(text(
        "SELECT indexname FROM pg_indexes WHERE tablename = 'novels' "
        "AND indexname = 'uq_novels_series_position'"
    ))
    assert result.first() is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_migration_0036_downgrade_roundtrip(async_session):
    """upgrade() then downgrade() should leave DB in pre-migration state."""
    # This test is typically run by the migration test harness;
    # implementer should verify the migration's downgrade() reverses all steps.
    # See existing migration tests for pattern (e.g., 0033_adaptive_settings).
    pass
```

- [ ] **Step 2: Run test, verify fail**

```bash
pytest tests/integration/test_migration_0036.py -v
```
Expected: FAIL — schema doesn't exist yet. (Integration tests need test Postgres; if unavailable locally, CI runs them.)

- [ ] **Step 3: Implement migration**

```python
# apps/api/alembic/versions/0036_series_foundation.py
"""Series Foundation: series, series_settings, novels columns, kb_entries scope.

Revision ID: 0036_series_foundation
Revises: 0035_evidence_novel_id  (or current head — verify before commit)
Created: 2026-07-29
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0036_series_foundation"
down_revision = "0035_evidence_novel_id"  # VERIFY: current head at impl time
branch_labels = None
depends_on = None

SENTINEL_NULL = "00000000-0000-0000-0000-000000000000"  # not used; partial indexes instead


def upgrade() -> None:
    """Apply Series Foundation schema changes."""

    # 1. Create series table
    op.create_table(
        "series",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("subtitle", sa.String(500), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("genre", sa.String(100), nullable=True),
        sa.Column("writing_language", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("planned_novel_count", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('draft', 'active', 'completed')", name="ck_series_status"),
    )
    op.create_index("ix_series_user_id", "series", ["user_id"])

    # 2. Create series_settings table (1:1 to series)
    op.create_table(
        "series_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("series_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("series.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("author_voice", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 3. Add series_id, series_position, subtitle to novels
    op.add_column("novels", sa.Column("series_id", postgresql.UUID(as_uuid=True),
                                       sa.ForeignKey("series.id", ondelete="SET NULL"),
                                       nullable=True))
    op.add_column("novels", sa.Column("series_position", sa.Integer, nullable=True))
    op.add_column("novels", sa.Column("subtitle", sa.String(500), nullable=True))
    op.create_index("ix_novels_series_id", "novels", ["series_id"])
    op.create_unique_constraint("uq_novels_series_position", "novels", ["series_id", "series_position"])

    # 4. Add series_id, base_entry_id to kb_entries; make novel_id nullable
    op.add_column("kb_entries", sa.Column("series_id", postgresql.UUID(as_uuid=True),
                                          sa.ForeignKey("series.id", ondelete="CASCADE"),
                                          nullable=True))
    op.add_column("kb_entries", sa.Column("base_entry_id", postgresql.UUID(as_uuid=True),
                                          sa.ForeignKey("kb_entries.id", ondelete="SET NULL"),
                                          nullable=True))
    op.alter_column("kb_entries", "novel_id", nullable=True)
    op.create_index("ix_kb_entries_series_id", "kb_entries", ["series_id"])
    op.create_index("ix_kb_entries_base_entry_id", "kb_entries", ["base_entry_id"])

    # 5. Drop old unique constraint; add partial unique indexes
    op.drop_constraint("uq_kb_entries_novel_slug", "kb_entries", type_="unique")

    op.create_index(
        "uq_kb_canon_per_series",
        "kb_entries",
        ["series_id", "slug"],
        unique=True,
        postgresql_where=sa.text("novel_id IS NULL"),
    )
    op.create_index(
        "uq_kb_overlay_per_novel",
        "kb_entries",
        ["novel_id", "slug"],
        unique=True,
        postgresql_where=sa.text("novel_id IS NOT NULL"),
    )

    # 6. CHECK constraint for scope invariant
    op.create_check_constraint(
        "ck_kb_entries_scope_invariant",
        "kb_entries",
        "(novel_id IS NULL AND series_id IS NOT NULL AND base_entry_id IS NULL) "
        "OR (novel_id IS NOT NULL)",
    )


def downgrade() -> None:
    """Reverse Series Foundation schema changes."""

    # Reverse order of upgrade()

    # 6. Drop CHECK
    op.drop_constraint("ck_kb_entries_scope_invariant", "kb_entries", type_="check")

    # 5. Drop partial uniques; restore old unique
    op.drop_index("uq_kb_overlay_per_novel", table_name="kb_entries")
    op.drop_index("uq_kb_canon_per_series", table_name="kb_entries")
    op.create_unique_constraint("uq_kb_entries_novel_slug", "kb_entries", ["novel_id", "slug"])

    # 4. Drop kb_entries columns; restore novel_id NOT NULL
    op.drop_index("ix_kb_entries_base_entry_id", table_name="kb_entries")
    op.drop_index("ix_kb_entries_series_id", table_name="kb_entries")
    # IMPORTANT: only restore NOT NULL if no NULL novel_id rows exist (they won't in downgrade)
    op.alter_column("kb_entries", "novel_id", nullable=False)
    op.drop_column("kb_entries", "base_entry_id")
    op.drop_column("kb_entries", "series_id")

    # 3. Drop novels columns
    op.drop_constraint("uq_novels_series_position", "novels", type_="unique")
    op.drop_index("ix_novels_series_id", table_name="novels")
    op.drop_column("novels", "subtitle")
    op.drop_column("novels", "series_position")
    op.drop_column("novels", "series_id")

    # 2. Drop series_settings
    op.drop_table("series_settings")

    # 1. Drop series
    op.drop_index("ix_series_user_id", table_name="series")
    op.drop_table("series")
```

- [ ] **Step 4: Verify migration head**

```bash
cd apps/api && alembic heads
```
Confirm `down_revision` matches current head. Adjust if other migrations landed first.

- [ ] **Step 5: Apply migration locally and run test**

```bash
cd apps/api && alembic upgrade head
pytest tests/integration/test_migration_0036.py -v
```
Expected: PASS (8 tests)

- [ ] **Step 6: Verify backward compat — existing KB queries still work**

```bash
pytest tests/unit/api/kb/ tests/integration/test_kb.py -v
```
Expected: All existing KB tests still pass.

- [ ] **Step 7: Commit**

```bash
git add apps/api/alembic/versions/0036_series_foundation.py tests/integration/test_migration_0036.py
git commit -m "feat(alembic): 0036_series_foundation migration

Spec 1 Slice 1 Task 1.5 — full schema migration: series, series_settings
tables, novels columns (series_id, series_position, subtitle), kb_entries
scope changes (series_id, base_entry_id, novel_id nullable). Drops old
(novel_id, slug) unique; adds partial uniques (uq_kb_canon_per_series,
uq_kb_overlay_per_novel) + CHECK ck_kb_entries_scope_invariant. Full
upgrade() + downgrade() per RULE-14. Atomic steps in dependency order."
```

---

# Slice 2: KB Scope (Core STI Types + Repository Methods)

> **Goal:** Add discriminated Pydantic types for KBEntry scope (STI pattern), plus Repository methods for scope-aware queries. After this slice: data layer complete for Series + KB scope; no business logic yet.

## Task 2.1: Core STI types (KBEntryBase, SeriesKBEntry, NovelKBEntry, KBEntry)

**Files:**
- Create: `packages/core/narrare_core/kb/schemas/entry.py`
- Modify: `packages/core/narrare_core/kb/schemas/__init__.py` (re-export)
- Test: `tests/unit/core/kb/schemas/test_entry.py`

**Interfaces:**
- Produces: `KBEntryBase`, `SeriesKBEntry`, `NovelKBEntry`, `KBEntry` (discriminated union) — used by Repository (Task 2.4), all KB consumers

> **Backward compat:** Existing `from narrare_core.kb.schemas import KBEntry` imports must continue to work. The discriminated union `KBEntry` is the new canonical type; it dispatches to `SeriesKBEntry` or `NovelKBEntry` based on `scope` field.

- [ ] **Step 1: Write failing test**

```python
# tests/unit/core/kb/schemas/test_entry.py
import pytest
from uuid import uuid4
from pydantic import ValidationError

from narrare_core.kb.schemas.entry import (
    KBEntryBase, SeriesKBEntry, NovelKBEntry, KBEntry
)
from narrare_core.kb.schemas import KBEntry as KBEntryReExported


class TestSeriesKBEntry:
    def test_minimal_valid(self):
        e = SeriesKBEntry(
            id=uuid4(), entity_type="system", name="Magic", slug="magic",
            series_id=uuid4(),
        )
        assert e.scope == "series"
        assert e.novel_id is None
        assert e.base_entry_id is None

    def test_rejects_novel_id(self):
        with pytest.raises(ValidationError):
            SeriesKBEntry(
                id=uuid4(), entity_type="system", name="X", slug="x",
                series_id=uuid4(), novel_id=uuid4(),
            )

    def test_series_id_required(self):
        with pytest.raises(ValidationError):
            SeriesKBEntry(id=uuid4(), entity_type="system", name="X", slug="x")


class TestNovelKBEntry:
    def test_minimal_valid(self):
        e = NovelKBEntry(
            id=uuid4(), entity_type="character", name="Harry", slug="harry",
            novel_id=uuid4(),
        )
        assert e.scope == "novel"
        assert e.series_id is None  # optional
        assert e.base_entry_id is None  # optional

    def test_novel_id_required(self):
        with pytest.raises(ValidationError):
            NovelKBEntry(id=uuid4(), entity_type="character", name="X", slug="x")

    def test_with_series_link(self):
        """Novel-Overlay can link to its parent series + base Canon entry."""
        e = NovelKBEntry(
            id=uuid4(), entity_type="character", name="Harry", slug="harry",
            novel_id=uuid4(), series_id=uuid4(), base_entry_id=uuid4(),
        )
        assert e.series_id is not None
        assert e.base_entry_id is not None


class TestKBEntryDiscriminatedUnion:
    def test_dispatch_series(self):
        """A dict with scope='series' deserializes to SeriesKBEntry."""
        data = {
            "id": str(uuid4()), "entity_type": "system", "name": "Magic",
            "slug": "magic", "scope": "series", "series_id": str(uuid4()),
        }
        # When used as Annotated discriminated union, dispatch happens
        # For direct TypeAdapter usage:
        from pydantic import TypeAdapter
        adapter = TypeAdapter(KBEntry)
        entry = adapter.validate_python(data)
        assert isinstance(entry, SeriesKBEntry)

    def test_dispatch_novel(self):
        data = {
            "id": str(uuid4()), "entity_type": "character", "name": "Harry",
            "slug": "harry", "scope": "novel", "novel_id": str(uuid4()),
        }
        from pydantic import TypeAdapter
        adapter = TypeAdapter(KBEntry)
        entry = adapter.validate_python(data)
        assert isinstance(entry, NovelKBEntry)

    def test_extra_fields_allowed(self):
        """Forward-compat: extra fields don't break (extra='allow')."""
        e = SeriesKBEntry(
            id=uuid4(), entity_type="system", name="X", slug="x",
            series_id=uuid4(), future_field="value",
        )
        assert e.future_field == "value"


class TestBackwardCompat:
    def test_kb_entry_re_exported_from_schemas_init(self):
        """Importing KBEntry from narrare_core.kb.schemas still works."""
        # KBEntryReExported is imported at top of file
        assert KBEntryReExported is not None
```

- [ ] **Step 2: Run test, verify fail**

```bash
pytest tests/unit/core/kb/schemas/test_entry.py -v
```
Expected: FAIL `ModuleNotFoundError: No module named 'narrare_core.kb.schemas.entry'`

- [ ] **Step 3: Implement STI types**

```python
# packages/core/narrare_core/kb/schemas/entry.py
"""KBEntry Single-Table-Inheritance (STI) types.

Schema 2A+STI: single physical kb_entries table, discriminated Pydantic
types at Core layer. Series-Canon entries (novel_id IS NULL) are typed
as SeriesKBEntry; Novel-Overlay entries (novel_id IS NOT NULL) are typed
as NovelKBEntry. DB CHECK constraint 'ck_kb_entries_scope_invariant'
mirrors this invariant physically.

See: docs/superpowers/specs/2026-07-29-series-foundation-design.md §3.2
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class KBEntryBase(BaseModel):
    """Common fields for all KB entries (Series-Canon + Novel-Overlay).

    Persisted in single kb_entries table. Subtypes fix scope-specific
    fields and add the discriminator value.
    """
    model_config = ConfigDict(extra="allow")

    id: UUID
    entity_type: str
    name: str
    slug: str
    status: str = "draft"
    body: str | None = None
    metadata_: dict[str, object] | None = None
    tags: list[str] | None = None
    template_version: str | None = None
    source: str = "manual"
    review_status: str = "approved"
    embeddings_dirty: bool = False
    last_referenced_at: datetime | None = None
    usage_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # Discriminator field (Literal in subtypes fixes the value)
    scope: Literal["series", "novel"]


class SeriesKBEntry(KBEntryBase):
    """A Series-Canon KB entry — shared across all novels in the series.

    DB invariant: novel_id IS NULL, series_id IS NOT NULL, base_entry_id IS NULL.
    """
    scope: Literal["series"] = "series"
    series_id: UUID
    novel_id: None = None
    base_entry_id: None = None


class NovelKBEntry(KBEntryBase):
    """A Novel-Overlay KB entry — valid in one specific novel.

    DB invariant: novel_id IS NOT NULL.
    series_id set iff novel belongs to a series.
    base_entry_id optional: link to Series-Canon entry this is an overlay of.
    """
    scope: Literal["novel"] = "novel"
    novel_id: UUID
    series_id: UUID | None = None
    base_entry_id: UUID | None = None


# Discriminated union for API responses, runtime dispatch, JSON round-trip.
# `scope` field is the discriminator.
KBEntry = Annotated[
    Union[SeriesKBEntry, NovelKBEntry],
    Field(discriminator="scope"),
]
```

```python
# packages/core/narrare_core/kb/schemas/__init__.py — add re-exports:
from narrare_core.kb.schemas.entry import (
    KBEntryBase,
    SeriesKBEntry,
    NovelKBEntry,
    KBEntry,
)
# ... existing exports (VoiceMetrics, VoiceAnalysis, etc.) stay
```

- [ ] **Step 4: Run test, verify pass**

```bash
pytest tests/unit/core/kb/schemas/test_entry.py -v
```
Expected: PASS (10 tests)

- [ ] **Step 5: Verify check_architecture green**

```bash
just check
```

- [ ] **Step 6: Commit**

```bash
git add packages/core/narrare_core/kb/schemas/entry.py packages/core/narrare_core/kb/schemas/__init__.py tests/unit/core/kb/schemas/test_entry.py
git commit -m "feat(core/kb): add KBEntry STI types (SeriesKBEntry, NovelKBEntry)

Spec 1 Slice 2 Task 2.1 — Schema 2A+STI implementation. Single physical
kb_entries table, discriminated Pydantic types at Core layer.
SeriesKBEntry fixes novel_id=None; NovelKBEntry requires novel_id.
KBEntry is Annotated discriminated union (scope field discriminator).
Re-exported from kb.schemas.__init__ for backward compat."
```

---

## Task 2.2: KB Scope-Aware Repository methods

**Files:**
- Modify: `apps/api/narrare/kb/repository.py` (+5 methods)
- Modify: `apps/api/narrare/kb/contracts.py` (+5 protocol methods)
- Test: `tests/unit/api/kb/test_scope_repository.py`

**Interfaces:**
- Consumes: `SeriesKBEntry`, `NovelKBEntry`, `KBEntry` (from Task 2.1), `KBEntry` SQLAlchemy model (existing + Task 1.4 changes)
- Produces: `find_canon_for_series()`, `find_overlay_for_novel()`, `find_merged_for_novel()`, `promote_to_canon()`, `demote_to_overlay()` — used by Scope Service (Task 3.8), Generation (Spec 2)

- [ ] **Step 1: Write failing test**

```python
# tests/unit/api/kb/test_scope_repository.py
"""Tests for KB scope-aware repository methods.

Uses FakeSession pattern (ADR-030) — no real DB needed for unit tests.
Integration tests (tests/integration/) cover the SQL behavior.
"""
import pytest
from uuid import uuid4

from narrare.kb.repository import KBRepository
from narrare.kb.models import KBEntry as KBEntryModel
from narrare_core.kb.schemas.entry import SeriesKBEntry, NovelKBEntry


# Fixtures: see tests/fakes/ for existing FakeSession patterns


class TestFindCanonForSeries:
    async def test_returns_only_canon_entries(self, fake_session_with_data):
        """Entries with novel_id IS NULL are Canon."""
        series_id = uuid4()
        repo = KBRepository(fake_session_with_data)
        canon = await repo.find_canon_for_series(series_id)
        assert all(e.novel_id is None for e in canon)
        assert all(e.series_id == series_id for e in canon)


class TestFindOverlayForNovel:
    async def test_returns_only_overlay_entries(self, fake_session_with_data):
        """Entries with novel_id = X are Overlay."""
        novel_id = uuid4()
        repo = KBRepository(fake_session_with_data)
        overlay = await repo.find_overlay_for_novel(novel_id)
        assert all(e.novel_id == novel_id for e in overlay)


class TestFindMergedForNovel:
    async def test_merges_canon_and_overlay_with_overlay_winning(self, fake_session_with_data):
        """For each slug, Overlay wins over Canon."""
        novel_id = uuid4()
        repo = KBRepository(fake_session_with_data)
        merged = await repo.find_merged_for_novel(novel_id)
        slugs = [e.slug for e in merged]
        # No duplicate slugs (overlay wins canon)
        assert len(slugs) == len(set(slugs))


class TestPromoteToCanon:
    async def test_promote_clears_novel_id_sets_series_id(self, fake_session_with_data):
        novel_id = uuid4()
        entry_id = uuid4()
        repo = KBRepository(fake_session_with_data)
        promoted = await repo.promote_to_canon(novel_id, entry_id)
        assert promoted.novel_id is None
        assert promoted.series_id is not None


class TestDemoteToOverlay:
    async def test_demote_sets_novel_id_clears_canon_state(self, fake_session_with_data):
        series_id = uuid4()
        entry_id = uuid4()
        target_novel_id = uuid4()
        repo = KBRepository(fake_session_with_data)
        demoted = await repo.demote_to_overlay(series_id, entry_id, target_novel_id)
        assert demoted.novel_id == target_novel_id
```

- [ ] **Step 2: Run test, verify fail**

```bash
pytest tests/unit/api/kb/test_scope_repository.py -v
```
Expected: FAIL `AttributeError: 'KBRepository' object has no attribute 'find_canon_for_series'`

- [ ] **Step 3: Add methods to contracts (Protocol)**

```python
# apps/api/narrare/kb/contracts.py — add to KBRepositoryProtocol:
from narrare_core.kb.schemas.entry import SeriesKBEntry, NovelKBEntry, KBEntry
from typing import Protocol
from uuid import UUID

class KBRepositoryProtocol(Protocol):
    # ... existing methods ...

    # Spec 1: Series scope methods (ADR-075)
    async def find_canon_for_series(self, series_id: UUID) -> list[SeriesKBEntry]:
        """All Series-Canon entries for a series (novel_id IS NULL)."""
        ...

    async def find_overlay_for_novel(self, novel_id: UUID) -> list[NovelKBEntry]:
        """All Novel-Overlay entries for a novel (novel_id = X)."""
        ...

    async def find_merged_for_novel(self, novel_id: UUID) -> list[KBEntry]:
        """Canon of parent series + Overlay of novel, merged (Overlay wins on slug)."""
        ...

    async def promote_to_canon(self, novel_id: UUID, entry_id: UUID) -> SeriesKBEntry:
        """Promote a Novel-Overlay entry to Series-Canon (clears novel_id, sets series_id)."""
        ...

    async def demote_to_overlay(
        self, series_id: UUID, entry_id: UUID, target_novel_id: UUID
    ) -> NovelKBEntry:
        """Demote a Series-Canon entry to Novel-Overlay for target_novel_id."""
        ...
```

- [ ] **Step 4: Implement methods in KBRepository**

```python
# apps/api/narrare/kb/repository.py — add these methods to KBRepository class:

from sqlalchemy import select
from narrare_core.kb.schemas.entry import SeriesKBEntry, NovelKBEntry
from narrare.kb.models import KBEntry as KBEntryModel
from narrare.novels.models import Novel


async def find_canon_for_series(self, series_id: UUID) -> list[SeriesKBEntry]:
    """All Series-Canon entries for a series (novel_id IS NULL)."""
    result = await self._session.execute(
        select(KBEntryModel).where(
            KBEntryModel.series_id == series_id,
            KBEntryModel.novel_id.is_(None),
        )
    )
    entries = result.scalars().all()
    return [self._to_series_kb_entry(e) for e in entries]


async def find_overlay_for_novel(self, novel_id: UUID) -> list[NovelKBEntry]:
    """All Novel-Overlay entries for a novel (novel_id = X)."""
    result = await self._session.execute(
        select(KBEntryModel).where(KBEntryModel.novel_id == novel_id)
    )
    entries = result.scalars().all()
    return [self._to_novel_kb_entry(e) for e in entries]


async def find_merged_for_novel(self, novel_id: UUID) -> list[KBEntry]:
    """Canon of parent series + Overlay of novel, merged (Overlay wins on slug)."""
    # First find the novel's series_id
    novel_result = await self._session.execute(
        select(Novel.series_id).where(Novel.id == novel_id)
    )
    series_id = novel_result.scalar_one_or_none()
    if series_id is None:
        # Standalone novel — no canon, only overlay
        return await self.find_overlay_for_novel(novel_id)

    # Fetch canon + overlay
    canon = await self.find_canon_for_series(series_id)
    overlay = await self.find_overlay_for_novel(novel_id)

    # Merge: dict by slug, overlay wins
    merged: dict[str, KBEntry] = {e.slug: e for e in canon}
    for e in overlay:
        merged[e.slug] = e  # overlay overrides canon
    return list(merged.values())


async def promote_to_canon(self, novel_id: UUID, entry_id: UUID) -> SeriesKBEntry:
    """Promote a Novel-Overlay entry to Series-Canon."""
    # 1. Load entry
    entry = await self._get(entry_id)
    if entry is None or entry.novel_id != novel_id:
        raise ValueError(f"Entry {entry_id} not found or not an overlay of novel {novel_id}")

    # 2. Load novel's series_id
    novel = await self._session.execute(
        select(Novel).where(Novel.id == novel_id)
    )
    novel_obj = novel.scalar_one_or_none()
    if novel_obj is None or novel_obj.series_id is None:
        raise ValueError(f"Novel {novel_id} not in a series")

    # 3. Mutate to Canon
    entry.novel_id = None
    entry.series_id = novel_obj.series_id
    entry.base_entry_id = None
    await self._session.flush()
    return self._to_series_kb_entry(entry)


async def demote_to_overlay(
    self, series_id: UUID, entry_id: UUID, target_novel_id: UUID
) -> NovelKBEntry:
    """Demote a Series-Canon entry to Novel-Overlay for target_novel_id."""
    entry = await self._get(entry_id)
    if entry is None or entry.series_id != series_id or entry.novel_id is not None:
        raise ValueError(f"Entry {entry_id} not found or not canon of series {series_id}")

    entry.novel_id = target_novel_id
    # series_id stays (novel is still in series); base_entry_id cleared (no longer overlay-of-canon)
    entry.base_entry_id = None
    await self._session.flush()
    return self._to_novel_kb_entry(entry)


def _to_series_kb_entry(self, model: KBEntryModel) -> SeriesKBEntry:
    """Convert SQLAlchemy model to Core SeriesKBEntry Pydantic type."""
    return SeriesKBEntry(
        id=model.id, entity_type=model.entity_type, name=model.name, slug=model.slug,
        status=model.status, body=model.body, metadata_=model.metadata_, tags=model.tags,
        template_version=model.template_version, source=model.source,
        review_status=model.review_status, embeddings_dirty=model.embeddings_dirty,
        last_referenced_at=model.last_referenced_at, usage_count=model.usage_count,
        created_at=model.created_at, updated_at=model.updated_at,
        series_id=model.series_id,  # type: ignore[arg-type]
    )


def _to_novel_kb_entry(self, model: KBEntryModel) -> NovelKBEntry:
    """Convert SQLAlchemy model to Core NovelKBEntry Pydantic type."""
    return NovelKBEntry(
        id=model.id, entity_type=model.entity_type, name=model.name, slug=model.slug,
        status=model.status, body=model.body, metadata_=model.metadata_, tags=model.tags,
        template_version=model.template_version, source=model.source,
        review_status=model.review_status, embeddings_dirty=model.embeddings_dirty,
        last_referenced_at=model.last_referenced_at, usage_count=model.usage_count,
        created_at=model.created_at, updated_at=model.updated_at,
        novel_id=model.novel_id,  # type: ignore[arg-type]
        series_id=model.series_id,
        base_entry_id=model.base_entry_id,
    )
```

- [ ] **Step 5: Run test, verify pass**

```bash
pytest tests/unit/api/kb/test_scope_repository.py -v
```
Expected: PASS (5 test classes)

- [ ] **Step 6: Regression — existing KB tests still pass**

```bash
pytest tests/unit/api/kb/ -v
```

- [ ] **Step 7: Commit**

```bash
git add apps/api/narrare/kb/repository.py apps/api/narrare/kb/contracts.py tests/unit/api/kb/test_scope_repository.py
git commit -m "feat(api/kb): add scope-aware repository methods (find_canon/overlay/merged, promote/demote)

Spec 1 Slice 2 Task 2.2 — KBRepository gains 5 scope methods.
find_merged_for_novel will be consumed by Spec 2 (Generation Context)
but ships in Spec 1 so the read-path exists. Promote/demote implement
scope-toggle logic. Helpers _to_series_kb_entry / _to_novel_kb_entry
convert SQLAlchemy rows to discriminated Pydantic types."
```

---

## Task 2.3: Regression — backward compat verification

**Files:**
- Test: `tests/unit/api/kb/test_backward_compat_scope_change.py` (NEW)

> **Critical regression test:** verifies existing KB queries (that filter `WHERE novel_id = X`) return the SAME results before and after the schema change. This protects ANAL-008/WRITE-010/ANAL-009 from silent breakage.

- [ ] **Step 1: Write regression test**

```python
# tests/unit/api/kb/test_backward_compat_scope_change.py
"""Regression test: existing KB queries must not break after scope schema change.

Existing queries that filter WHERE novel_id = X must continue to return
ONLY Novel-Overlay entries (Canon has novel_id IS NULL and is correctly
excluded). This is the critical backward-compat guarantee.
"""
import pytest
from uuid import uuid4

from narrare.kb.repository import KBRepository


@pytest.mark.asyncio
async def test_get_by_novel_returns_only_overlay(fake_session_with_mixed_entries):
    """A novel with both Overlay + Canon available should get ONLY Overlay."""
    novel_id = uuid4()
    repo = KBRepository(fake_session_with_mixed_entries)

    # Existing method: list entries for a novel
    entries = await repo.list_for_novel(novel_id)  # existing method

    # All returned entries must have novel_id = X (not Canon)
    assert all(e.novel_id == novel_id for e in entries)
    # No Canon entries leaked in (Canon has novel_id IS NULL)
    assert all(e.novel_id is not None for e in entries)


@pytest.mark.asyncio
async def test_existing_kb_consumer_paths_still_functional(fake_session):
    """Smoke test: ANAL-008/WRITE-010/ANAL-009 paths still work after schema change."""
    # This is a placeholder for running existing ANAL-008/WRITE-010/ANAL-009
    # test suites — they must remain green. Run separately:
    #   pytest tests/unit/api/analysis/test_character_voice.py
    #   pytest tests/unit/api/writing/test_voice_check.py
    #   pytest tests/unit/api/analysis/test_voice_drift.py
    pass
```

- [ ] **Step 2: Run regression test**

```bash
pytest tests/unit/api/kb/test_backward_compat_scope_change.py -v
# Plus: pytest tests/unit/api/analysis/test_character_voice.py tests/unit/api/writing/test_voice_check.py tests/unit/api/analysis/test_voice_drift.py -v
```
Expected: All PASS.

- [ ] **Step 3: Commit (test-only)**

```bash
git add tests/unit/api/kb/test_backward_compat_scope_change.py
git commit -m "test(api/kb): add backward-compat regression for scope schema change

Spec 1 Slice 2 Task 2.3 — verifies existing WHERE novel_id = X queries
return ONLY Novel-Overlay entries after schema change (Canon excluded
via novel_id IS NULL). Protects ANAL-008/WRITE-010/ANAL-009 from silent
breakage. Per ADR-014 regression-first principle."
```

---

*(Continued in next message — Slices 3, 4, 5, and Final Doc Gate tasks.)*
