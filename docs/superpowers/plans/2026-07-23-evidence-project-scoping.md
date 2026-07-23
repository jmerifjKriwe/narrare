# Evidence Project Scoping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `novel_id` scope column to `invocation_evidence` (plus a read-only `created_at` on the Core model) so the Adaptivity Dashboard can list per-novel adaptive snapshots via `GET /api/v1/adaptive/{project_id}/snapshots`.

**Architecture:** A single nullable, indexed `novel_id` column (Alembic `0035`) extends the table ADR-069 D11 introduced adaptive columns on. The write path threads `novel_id = context.project_id` at exactly one boundary (`build_invocation_evidence`). The read path adds one repository method, one service method, one REST endpoint. Backward compatible: legacy rows keep NULL `novel_id` and are simply absent from per-novel queries (correct — they are unattributable). The Core `created_at` field is read-only (DB-stamped on INSERT; `domain_to_orm` omits it, `orm_to_domain` populates it).

**Tech Stack:** Python 3.14, SQLAlchemy 2.0 async, Alembic, FastAPI, Pydantic v2, PostgreSQL (UUID + `gen_random_uuid`).

## Global Constraints

- **RULE-14:** Migration `0035` ships in the SAME task as the ORM + Core model field change (Task 1). No `Base.metadata.create_all()` — the integration conftest runs `alembic upgrade head`; the migrated schema IS the test schema.
- **RULE-03:** Core `FeatureInvocationEvidence` fields + ORM column + mapper land before the repository/service/router that consume them.
- **RULE-07:** The `context.project_id → evidence.novel_id` rename happens at ONE boundary (`build_invocation_evidence`). No `apps/`→`core` import.
- **Naming:** The DB column is `novel_id` (matches `Chapter.novel_id`, `ProjectSettings.novel_id`). The REST path param stays `project_id` (matches existing `/adaptive/{project_id}` routes). They are the same UUID — the rename is localised to the evidence-build boundary. See ADR-070.
- **Backward compatibility:** `novel_id` is nullable; pre-0035 rows stay NULL by design.
- **Asymmetric `created_at`:** `domain_to_orm` MUST NOT emit `created_at` (DB `server_default=func.now()`); `orm_to_domain` MUST populate it from the ORM row.
- **Tests:** Unit tests in `tests/unit/`, integration tests in `tests/integration/` (real Postgres via `alembic upgrade head`). Fakes over MagicMock for domain deps.

**Spec:** `docs/architecture/decisions/ADR-070-evidence-project-scoping.md`

---

## File Structure

| File | Responsibility | Task |
|------|----------------|------|
| `apps/api/alembic/versions/0035_evidence_project_scoping.py` | Add `novel_id` column + index; reversible. | 1 |
| `apps/api/narrare/evidence/models.py` | ORM `novel_id` column (nullable, indexed). | 1 |
| `packages/core/narrare_core/ai_invocation/evidence_models.py` | Core `novel_id` + read-only `created_at` fields. | 1 |
| `apps/api/narrare/evidence/_mappers.py` | Asymmetric mapping (novel_id both ways; created_at read-only). | 1 |
| `packages/core/narrare_core/ai_invocation/_evidence.py` | Thread `novel_id = context.project_id`. | 2 |
| `apps/api/narrare/evidence/repository.py` | `get_adaptive_snapshots(novel_id, limit)`. | 3 |
| `apps/api/narrare/adaptive/schemas.py` | `AdaptiveSnapshotItem` + `AdaptiveSnapshotsResponse`. | 4 |
| `apps/api/narrare/adaptive/service.py` | `get_adaptive_snapshots(project_id, user_id, limit)`. | 4 |
| `apps/api/narrare/adaptive/dependencies.py` | Wire `EvidenceRepositoryImpl` into the service. | 4 |
| `apps/api/narrare/adaptive/router.py` | `GET /{project_id}/snapshots`. | 5 |

---

### Task 1: Data layer — migration `0035` + ORM + Core model + asymmetric mappers

**Files:**
- Create: `apps/api/alembic/versions/0035_evidence_project_scoping.py`
- Modify: `apps/api/narrare/evidence/models.py` (add column after `invocation_id`, ~line 62)
- Modify: `packages/core/narrare_core/ai_invocation/evidence_models.py` (add two fields after `invocation_id`, ~line 43)
- Modify: `apps/api/narrare/evidence/_mappers.py` (`domain_to_orm` + `orm_to_domain`)
- Test: `tests/unit/api/test_evidence_project_scoping_mapping.py`

**Interfaces:**
- Consumes: nothing (foundation task).
- Produces: `FeatureInvocationEvidence.novel_id: UUID | None`, `FeatureInvocationEvidence.created_at: datetime | None`; ORM column `InvocationEvidenceModel.novel_id`; `domain_to_orm` emits `novel_id` (not `created_at`); `orm_to_domain` restores both.

- [ ] **Step 1: Write the failing mapping test**

Create `tests/unit/api/test_evidence_project_scoping_mapping.py`:

```python
"""Tests for FeatureInvocationEvidence novel_id + created_at mapping (ADR-070).

Verifies the asymmetric mapping contract:
- novel_id round-trips Core ↔ ORM both ways.
- created_at is READ-ONLY: populated by orm_to_domain, omitted by domain_to_orm
  (the DB column has server_default=func.now()).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from narrare.evidence._mappers import domain_to_orm, orm_to_domain
from narrare.evidence.models import InvocationEvidenceModel
from narrare_core.ai_invocation._enums import (
    AuditState,
    KBSuggestedStatus,
    PreferenceStatus,
)
from narrare_core.ai_invocation.evidence_models import FeatureInvocationEvidence


def _make_evidence(*, novel_id: object | None = "unset") -> FeatureInvocationEvidence:
    kwargs: dict[str, object] = dict(
        feature_id="dialogue_coach",
        intent="dialogue_coach",
        mode="dialogue_coach",
        prompt_route="ai_assist/dialogue_coach",
        preference_status=PreferenceStatus.PROVIDED,
        kb_suggested_status=KBSuggestedStatus.NOT_APPLICABLE,
        final_prompt_validated=True,
        audit_state=AuditState.ADOPTED,
        invocation_id=uuid4(),
        adaptive_source_summary={"summary": "preferences"},
        adaptive_weights={"preference": 0.7},
    )
    if novel_id != "unset":
        kwargs["novel_id"] = novel_id
    return FeatureInvocationEvidence(**kwargs)  # type: ignore[arg-type]


class TestNovelIdMapping:
    """novel_id round-trips Core ↔ ORM."""

    def test_domain_to_orm_includes_novel_id(self) -> None:
        novel = uuid4()
        evidence = _make_evidence(novel_id=novel)
        values = domain_to_orm(evidence)
        assert values["novel_id"] == novel

    def test_domain_to_orm_novel_id_none_when_unset(self) -> None:
        evidence = _make_evidence(novel_id=None)
        values = domain_to_orm(evidence)
        assert values["novel_id"] is None

    def test_orm_to_domain_restores_novel_id(self) -> None:
        novel = uuid4()
        evidence = _make_evidence(novel_id=novel)
        model = InvocationEvidenceModel(**domain_to_orm(evidence))  # type: ignore[arg-type]
        restored = orm_to_domain(model)
        assert restored.novel_id == novel


class TestCreatedAtAsymmetric:
    """created_at is read-only (DB-stamped); domain_to_orm omits it."""

    def test_domain_to_orm_omits_created_at(self) -> None:
        evidence = _make_evidence(novel_id=None)
        values = domain_to_orm(evidence)
        assert "created_at" not in values

    def test_orm_to_domain_restores_created_at(self) -> None:
        stamped = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)
        evidence = _make_evidence(novel_id=None)
        values = domain_to_orm(evidence)
        values["created_at"] = stamped
        model = InvocationEvidenceModel(**values)  # type: ignore[arg-type]
        restored = orm_to_domain(model)
        assert restored.created_at == stamped
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/api/test_evidence_project_scoping_mapping.py -v`
Expected: FAIL — `domain_to_orm` does not return `novel_id`; `FeatureInvocationEvidence` has no `novel_id`/`created_at` attributes.

- [ ] **Step 3: Add the Alembic migration**

Create `apps/api/alembic/versions/0035_evidence_project_scoping.py`:

```python
"""Add novel_id column to invocation_evidence (ADR-070).

Project-scopes each evidence row so the Adaptivity Dashboard can list
per-novel adaptive snapshots (GET /api/v1/adaptive/{project_id}/snapshots).
Nullable + indexed for backward compatibility: pre-0035 rows keep NULL
novel_id and are simply absent from per-novel queries (they are
unattributable — the write path never captured the novel before this
migration).

Mirrors the nullable-column pattern of 0030_evidence_correlation.

Revision ID: 0035_evidence_project_scoping
Revises: 0034_evidence_adaptive_columns
Create Date: 2026-07-23 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0035_evidence_project_scoping"
down_revision: str | None = "0034_evidence_adaptive_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ADR-070: project-scope column for per-novel snapshot queries.
    op.add_column(
        "invocation_evidence",
        sa.Column("novel_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_invocation_evidence_novel_id",
        "invocation_evidence",
        ["novel_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_invocation_evidence_novel_id",
        table_name="invocation_evidence",
    )
    op.drop_column("invocation_evidence", "novel_id")
```

- [ ] **Step 4: Add the ORM column**

In `apps/api/narrare/evidence/models.py`, add immediately after the `invocation_id` block (after line 62, before `prepared_context_fingerprint`):

```python
    # ADR-070: project-scope column for per-novel snapshot queries.
    # NULL on pre-0035 rows and when the invocation context had no project.
    novel_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
```

- [ ] **Step 5: Add the Core model fields**

In `packages/core/narrare_core/ai_invocation/evidence_models.py`, add after `invocation_id` (line 43) and BEFORE the `feature_id` line so optional fields stay grouped — but note `feature_id` is required, so insert immediately after `invocation_id: UUID | None = None`:

```python
    invocation_id: UUID | None = None
    # ADR-070: project scope (set on write from context.project_id) and
    # created_at (READ-ONLY — DB-stamped on INSERT; populated by orm_to_domain
    # on reads, omitted by domain_to_orm on writes).
    novel_id: UUID | None = None
    created_at: datetime | None = None
```

Also add `datetime` to the TYPE_CHECKING import block at the top of the file. Find:

```python
if TYPE_CHECKING:
    from uuid import UUID
```

Replace with:

```python
if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID
```

- [ ] **Step 6: Update the mappers (asymmetric)**

In `apps/api/narrare/evidence/_mappers.py`:

In `domain_to_orm`, add `novel_id` to the returned dict (after the `invocation_id` line, ~line 45). Do NOT add `created_at`:

```python
        # ADR-045 §2: correlation fields.
        "invocation_id": evidence.invocation_id,
        # ADR-070: project scope (write path). created_at is intentionally
        # omitted — the DB column has server_default=func.now().
        "novel_id": evidence.novel_id,
```

In `orm_to_domain`, add BOTH `novel_id` and `created_at` to the `FeatureInvocationEvidence(...)` constructor call (after the `invocation_id=` line, ~line 93):

```python
        # ADR-045 §2: correlation fields.
        invocation_id=model.invocation_id,
        # ADR-070: project scope + read-only DB-stamped timestamp.
        novel_id=model.novel_id,
        created_at=model.created_at,
```

- [ ] **Step 7: Run the mapping test to verify it passes**

Run: `pytest tests/unit/api/test_evidence_project_scoping_mapping.py -v`
Expected: PASS (all 5 tests).

- [ ] **Step 8: Verify the migration applies cleanly + no existing tests regress**

Run: `pytest tests/unit/api/test_evidence_repository_query.py tests/unit/api/test_evidence_adaptive_mapping.py tests/unit/core/ai_invocation/test_evidence_serialization.py -v`
Expected: PASS — existing constructors use keyword args, so the two new optional fields (default None) are backward compatible.

Run the migration check (integration conftest will run `alembic upgrade head`):
Run: `pytest tests/integration/evidence/test_evidence_repository_state.py -v`
Expected: PASS — confirms migration `0035` applies and the `novel_id` column exists in the live schema.

- [ ] **Step 9: Commit**

```bash
git add apps/api/alembic/versions/0035_evidence_project_scoping.py \
        apps/api/narrare/evidence/models.py \
        packages/core/narrare_core/ai_invocation/evidence_models.py \
        apps/api/narrare/evidence/_mappers.py \
        tests/unit/api/test_evidence_project_scoping_mapping.py
git commit -m "feat(evidence): add novel_id column + read-only created_at (ADR-070)"
```

---

### Task 2: Write-path threading — `build_invocation_evidence`

**Files:**
- Modify: `packages/core/narrare_core/ai_invocation/_evidence.py` (one line in the `FeatureInvocationEvidence(...)` constructor, ~line 122)
- Test: `tests/unit/core/ai_invocation/test_evidence_novel_id_threading.py`

**Interfaces:**
- Consumes: `PromptInvocationContext.project_id` (Task 1's Core field).
- Produces: every evidence record built by the pipeline carries `novel_id = context.project_id`.

- [ ] **Step 1: Write the failing threading test**

Create `tests/unit/core/ai_invocation/test_evidence_novel_id_threading.py`:

```python
"""Tests that build_invocation_evidence threads context.project_id → evidence.novel_id (ADR-070)."""

from __future__ import annotations

from uuid import uuid4

from narrare_core.ai_invocation._evidence import build_invocation_evidence
from narrare_core.ai_invocation._enums import ValidationStatus
from narrare_core.ai_invocation.models import PromptInvocationContext, ValidationResult
from narrare_core.llm.intents import LLMIntent


def _context(*, project_id: object | None) -> PromptInvocationContext:
    return PromptInvocationContext(
        feature_id="dialogue_coach",
        intent=LLMIntent.DIALOGUE_COACH,
        mode="dialogue_coach",
        project_id=project_id,
    )


class TestNovelIdThreading:
    def test_project_id_flows_to_novel_id(self) -> None:
        novel = uuid4()
        ctx = _context(project_id=novel)
        evidence = build_invocation_evidence(
            context=ctx,
            prepared=None,
            final_validation=ValidationResult(status=ValidationStatus.PASS),
            final_validator_ran=True,
        )
        assert evidence.novel_id == novel

    def test_none_project_id_yields_none_novel_id(self) -> None:
        ctx = _context(project_id=None)
        evidence = build_invocation_evidence(
            context=ctx,
            prepared=None,
            final_validation=ValidationResult(status=ValidationStatus.PASS),
            final_validator_ran=True,
        )
        assert evidence.novel_id is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/core/ai_invocation/test_evidence_novel_id_threading.py -v`
Expected: FAIL — `evidence.novel_id` is None (build_invocation_evidence does not set it yet).

- [ ] **Step 3: Thread novel_id in build_invocation_evidence**

In `packages/core/narrare_core/ai_invocation/_evidence.py`, in the `FeatureInvocationEvidence(...)` constructor call (~line 122), add the `novel_id` argument immediately after `invocation_id=invocation_id,`:

```python
    return FeatureInvocationEvidence(
        invocation_id=invocation_id,
        # ADR-070: project-scope the evidence row. context.project_id IS the
        # novel UUID (novel ≡ project in Narrare); the rename is localised here.
        novel_id=context.project_id,
        feature_id=context.feature_id,
        intent=context.intent.value,
        mode=context.mode,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/core/ai_invocation/test_evidence_novel_id_threading.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Run the evidence build regression suite**

Run: `pytest tests/unit/core/ai_invocation/ -k evidence -v`
Expected: PASS — no existing build_invocation_evidence test asserts absence of novel_id.

- [ ] **Step 6: Commit**

```bash
git add packages/core/narrare_core/ai_invocation/_evidence.py \
        tests/unit/core/ai_invocation/test_evidence_novel_id_threading.py
git commit -m "feat(evidence): thread context.project_id into evidence.novel_id (ADR-070)"
```

---

### Task 3: Repository read method — `get_adaptive_snapshots`

**Files:**
- Modify: `apps/api/narrare/evidence/repository.py` (new method after `update_adaptive_snapshot`, end of class ~line 198)
- Test: `tests/integration/evidence/test_evidence_adaptive_snapshots.py`

**Interfaces:**
- Consumes: ORM `novel_id` + `adaptive_source_summary` + `created_at` (Task 1).
- Produces: `EvidenceRepositoryImpl.get_adaptive_snapshots(novel_id: UUID, *, limit: int = 20) -> list[FeatureInvocationEvidence]` — newest first, only rows that used adaptive context, each carrying `created_at`.

- [ ] **Step 1: Write the failing integration test**

Create `tests/integration/evidence/test_evidence_adaptive_snapshots.py`:

```python
"""Integration tests for EvidenceRepositoryImpl.get_adaptive_snapshots (ADR-070)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

import pytest_asyncio

from narrare.evidence.models import InvocationEvidenceModel
from narrare.evidence.repository import EvidenceRepositoryImpl

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from uuid import UUID


def _row(
    *,
    novel_id: UUID | None,
    adaptive: dict[str, str] | None,
    created_at: datetime,
    invocation_id: UUID | None = None,
) -> InvocationEvidenceModel:
    return InvocationEvidenceModel(
        id=uuid.uuid4(),
        feature_id="dialogue_coach",
        intent="dialogue_coach",
        mode="dialogue_coach",
        prompt_route="ai_assist/dialogue_coach",
        preference_status="provided",
        kb_suggested_status="not_applicable",
        audit_state="adopted",
        final_prompt_validated=True,
        novel_id=novel_id,
        invocation_id=invocation_id or uuid.uuid4(),
        adaptive_source_summary=adaptive,
        adaptive_weights={"preference": 0.7} if adaptive else None,
        created_at=created_at,
    )


@pytest_asyncio.fixture(loop_scope="session")
async def evidence_repo(db_session: AsyncSession) -> EvidenceRepositoryImpl:
    return EvidenceRepositoryImpl(session=db_session)


class TestGetAdaptiveSnapshots:
    async def test_returns_only_rows_for_novel_with_adaptive(
        self,
        evidence_repo: EvidenceRepositoryImpl,
        db_session: AsyncSession,
    ) -> None:
        novel = uuid.uuid4()
        other = uuid.uuid4()
        db_session.add_all(
            [
                _row(novel_id=novel, adaptive={"summary": "preferences"},
                     created_at=datetime(2026, 7, 1, tzinfo=UTC)),
                _row(novel_id=novel, adaptive=None,
                     created_at=datetime(2026, 7, 2, tzinfo=UTC)),  # no adaptive → excluded
                _row(novel_id=other, adaptive={"summary": "voices"},
                     created_at=datetime(2026, 7, 3, tzinfo=UTC)),  # other novel → excluded
                _row(novel_id=None, adaptive={"summary": "legacy"},
                     created_at=datetime(2026, 7, 4, tzinfo=UTC)),  # unattributable → excluded
            ]
        )
        await db_session.flush()

        results = await evidence_repo.get_adaptive_snapshots(novel_id=novel)
        assert len(results) == 1
        assert results[0].novel_id == novel
        assert results[0].adaptive_source_summary == {"summary": "preferences"}

    async def test_orders_newest_first_and_carries_created_at(
        self,
        evidence_repo: EvidenceRepositoryImpl,
        db_session: AsyncSession,
    ) -> None:
        novel = uuid.uuid4()
        db_session.add_all(
            [
                _row(novel_id=novel, adaptive={"summary": "old"},
                     created_at=datetime(2026, 7, 1, tzinfo=UTC)),
                _row(novel_id=novel, adaptive={"summary": "new"},
                     created_at=datetime(2026, 7, 23, tzinfo=UTC)),
            ]
        )
        await db_session.flush()

        results = await evidence_repo.get_adaptive_snapshots(novel_id=novel)
        assert [r.adaptive_source_summary["summary"] for r in results] == ["new", "old"]
        assert all(r.created_at is not None for r in results)

    async def test_limit_is_respected(
        self,
        evidence_repo: EvidenceRepositoryImpl,
        db_session: AsyncSession,
    ) -> None:
        novel = uuid.uuid4()
        db_session.add_all(
            [
                _row(novel_id=novel, adaptive={"summary": str(i)},
                     created_at=datetime(2026, 7, i, tzinfo=UTC))
                for i in range(1, 6)
            ]
        )
        await db_session.flush()

        results = await evidence_repo.get_adaptive_snapshots(novel_id=novel, limit=2)
        assert len(results) == 2
        assert [r.adaptive_source_summary["summary"] for r in results] == ["5", "4"]

    async def test_no_matching_rows_returns_empty(
        self,
        evidence_repo: EvidenceRepositoryImpl,
    ) -> None:
        results = await evidence_repo.get_adaptive_snapshots(novel_id=uuid.uuid4())
        assert results == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/evidence/test_evidence_adaptive_snapshots.py -v`
Expected: FAIL — `AttributeError: 'EvidenceRepositoryImpl' object has no attribute 'get_adaptive_snapshots'`.

- [ ] **Step 3: Implement get_adaptive_snapshots**

In `apps/api/narrare/evidence/repository.py`, add this method to `EvidenceRepositoryImpl` (after `update_adaptive_snapshot`, before the end of the class). Add `FeatureInvocationEvidence` is already imported under TYPE_CHECKING.

```python
    async def get_adaptive_snapshots(
        self,
        novel_id: UUID,
        *,
        limit: int = 20,
    ) -> list[FeatureInvocationEvidence]:
        """List per-novel adaptive snapshots, newest first (ADR-070).

        Returns only rows that actually consumed adaptive context
        (``adaptive_source_summary IS NOT NULL``) and are scoped to
        ``novel_id``. Legacy rows with NULL ``novel_id`` are correctly
        absent — they are unattributable.

        Args:
            novel_id: The novel/project UUID to scope by.
            limit: Maximum records to return (default 20).

        Returns:
            Evidence records newest-first, each carrying ``created_at``.
        """
        stmt = (
            select(InvocationEvidenceModel)
            .where(InvocationEvidenceModel.novel_id == novel_id)
            .where(InvocationEvidenceModel.adaptive_source_summary.isnot(None))
            .order_by(InvocationEvidenceModel.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [orm_to_domain(row) for row in result.scalars()]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/integration/evidence/test_evidence_adaptive_snapshots.py -v`
Expected: PASS (all 4 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/api/narrare/evidence/repository.py \
        tests/integration/evidence/test_evidence_adaptive_snapshots.py
git commit -m "feat(evidence): add get_adaptive_snapshots repository read (ADR-070)"
```

---

### Task 4: Service method + response schemas + DI wiring

**Files:**
- Modify: `apps/api/narrare/adaptive/schemas.py` (add `AdaptiveSnapshotItem` + `AdaptiveSnapshotsResponse`)
- Modify: `apps/api/narrare/adaptive/service.py` (add `evidence_repo` dep + `get_adaptive_snapshots`)
- Modify: `apps/api/narrare/adaptive/dependencies.py` (wire `EvidenceRepositoryImpl`)
- Test: `tests/unit/api/adaptive/test_adaptive_snapshots_service.py`

**Interfaces:**
- Consumes: `EvidenceRepositoryImpl.get_adaptive_snapshots` (Task 3); `FeatureInvocationEvidence.adaptive_weights` dict.
- Produces: `AdaptiveContextService.get_adaptive_snapshots(project_id, user_id, limit=20) -> AdaptiveSnapshotsResponse`.

- [ ] **Step 1: Write the failing service test**

Create `tests/unit/api/adaptive/__init__.py` if it does not exist (empty file). Then create `tests/unit/api/adaptive/test_adaptive_snapshots_service.py`:

```python
"""Unit tests for AdaptiveContextService.get_adaptive_snapshots (ADR-070)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from narrare.adaptive.service import AdaptiveContextService
from narrare_core.ai_invocation._enums import (
    AuditState,
    KBSuggestedStatus,
    PreferenceStatus,
)
from narrare_core.ai_invocation.evidence_models import FeatureInvocationEvidence

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.adaptive.contracts import AdaptiveSettingsRepositoryProtocol
    from narrare_core.ai_invocation.adaptive_contracts import AdaptiveContextProvider


class _FakeEvidenceRepo:
    """Fake EvidenceRepositoryImpl — records calls, returns canned snapshots."""

    def __init__(self, snapshots: list[FeatureInvocationEvidence]) -> None:
        self._snapshots = snapshots
        self.last_novel_id: object | None = None
        self.last_limit: int | None = None

    async def get_adaptive_snapshots(
        self,
        novel_id: UUID,
        *,
        limit: int = 20,
    ) -> list[FeatureInvocationEvidence]:
        self.last_novel_id = novel_id
        self.last_limit = limit
        return self._snapshots


def _snapshot(*, weights: dict[str, float] | None) -> FeatureInvocationEvidence:
    return FeatureInvocationEvidence(
        feature_id="dialogue_coach",
        intent="dialogue_coach",
        mode="dialogue_coach",
        prompt_route="ai_assist/dialogue_coach",
        preference_status=PreferenceStatus.PROVIDED,
        kb_suggested_status=KBSuggestedStatus.NOT_APPLICABLE,
        final_prompt_validated=True,
        audit_state=AuditState.ADOPTED,
        invocation_id=uuid4(),
        novel_id=uuid4(),
        created_at=datetime(2026, 7, 23, tzinfo=UTC),
        adaptive_source_summary={"summary": "preferences"},
        adaptive_weights=weights,
    )


@pytest.fixture
def service(
    fake_provider: AdaptiveContextProvider,
    fake_settings_repo: AdaptiveSettingsRepositoryProtocol,
) -> tuple[AdaptiveContextService, _FakeEvidenceRepo]:
    repo = _FakeEvidenceRepo(snapshots=[_snapshot(weights={"preference": 0.7})])
    return (
        AdaptiveContextService(
            provider=fake_provider,
            settings_repo=fake_settings_repo,
            evidence_repo=repo,
        ),
        repo,
    )


class TestGetAdaptiveSnapshots:
    async def test_returns_items_and_passes_scope(
        self,
        service: tuple[AdaptiveContextService, _FakeEvidenceRepo],
    ) -> None:
        svc, repo = service
        novel = uuid4()
        response = await svc.get_adaptive_snapshots(
            project_id=novel, user_id=uuid4(), limit=20
        )
        assert repo.last_novel_id == novel
        assert repo.last_limit == 20
        assert len(response.items) == 1
        item = response.items[0]
        assert item.source_summary == {"summary": "preferences"}
        assert item.weights is not None
        assert item.weights.preference == 0.7
        assert item.created_at == datetime(2026, 7, 23, tzinfo=UTC)

    async def test_empty_repo_yields_empty_response(
        self,
        fake_provider: AdaptiveContextProvider,
        fake_settings_repo: AdaptiveSettingsRepositoryProtocol,
    ) -> None:
        repo = _FakeEvidenceRepo(snapshots=[])
        svc = AdaptiveContextService(
            provider=fake_provider,
            settings_repo=fake_settings_repo,
            evidence_repo=repo,
        )
        response = await svc.get_adaptive_snapshots(
            project_id=uuid4(), user_id=uuid4()
        )
        assert response.items == []
```

> Note: `fake_provider` / `fake_settings_repo` fixtures — if they do not already exist in `tests/unit/api/adaptive/`, create minimal fakes in a local `conftest.py` (instances whose `get_context`/`get_settings` return defaults). Reuse the project's existing fake pattern from `tests/fakes/` if an adaptive fake already exists; otherwise two-attribute stubs suffice here because `get_adaptive_snapshots` does not call the provider.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/api/adaptive/test_adaptive_snapshots_service.py -v`
Expected: FAIL — `AdaptiveContextService.__init__` does not accept `evidence_repo`; no `get_adaptive_snapshots` method.

- [ ] **Step 3: Add the response schemas**

In `apps/api/narrare/adaptive/schemas.py`, add at the end of the file:

```python
class AdaptiveSnapshotItem(BaseModel):
    """One row in the Recent Adaptive Activity timeline (ADR-070)."""

    model_config = ConfigDict(frozen=True)

    invocation_id: str | None = None
    novel_id: str | None = None
    intent: str
    mode: str | None = None
    created_at: datetime
    source_summary: dict[str, str] | None = None
    weights: AdaptiveWeightsResponse | None = None


class AdaptiveSnapshotsResponse(BaseModel):
    """Response for GET /adaptive/{project_id}/snapshots."""

    model_config = ConfigDict(frozen=True)

    project_id: str
    items: list[AdaptiveSnapshotItem] = Field(default_factory=list)
```

Add the `datetime` import at the top of `schemas.py`:

```python
from datetime import datetime
```

- [ ] **Step 4: Add the service method + evidence_repo dependency**

In `apps/api/narrare/adaptive/service.py`:

Add imports after the existing schema import block:

```python
from datetime import UTC

from narrare.adaptive.schemas import (
    AdaptiveContextResponse,
    AdaptiveSettingsResponse,
    AdaptiveSnapshotItem,
    AdaptiveSnapshotsResponse,
    AdaptiveSourceSummary,
    AdaptiveWeightsInput,
    AdaptiveWeightsResponse,
)
```

Update the constructor to accept `evidence_repo`:

```python
    def __init__(
        self,
        provider: AdaptiveContextProvider,
        settings_repo: AdaptiveSettingsRepositoryProtocol,
        evidence_repo: EvidenceSnapshotReader,
    ) -> None:
        self._provider = provider
        self._settings_repo = settings_repo
        self._evidence_repo = evidence_repo
```

Add a TYPE_CHECKING import for the evidence read Protocol and define the structural type the service depends on (avoid hard-coupling to the concrete `EvidenceRepositoryImpl` so the fake satisfies it):

```python
if TYPE_CHECKING:
    from uuid import UUID

    from narrare.adaptive.contracts import AdaptiveSettingsRepositoryProtocol
    from narrare_core.ai_invocation.adaptive_contracts import (
        AdaptiveContextProvider,
    )
    from narrare_core.ai_invocation.evidence_models import FeatureInvocationEvidence

    class EvidenceSnapshotReader(Protocol):
        async def get_adaptive_snapshots(
            self,
            novel_id: UUID,
            *,
            limit: int = 20,
        ) -> list[FeatureInvocationEvidence]: ...
```

Add `Protocol` to the `typing` import line (`from typing import TYPE_CHECKING, Protocol`).

Add the method at the end of the class:

```python
    async def get_adaptive_snapshots(
        self,
        project_id: UUID,
        user_id: UUID,
        limit: int = 20,
    ) -> AdaptiveSnapshotsResponse:
        """List recent adaptive snapshots for the dashboard (ADR-070).

        project_id is the novel UUID (novel ≡ project); it is passed to the
        evidence repository as novel_id. Ownership is gated at the REST
        boundary (auth + novel ownership), mirroring the other adaptive
        endpoints.
        """
        del user_id  # ownership handled at router; read scoped by novel_id.
        records = await self._evidence_repo.get_adaptive_snapshots(
            project_id, limit=limit
        )
        items = [_snapshot_item(r) for r in records]
        return AdaptiveSnapshotsResponse(
            project_id=str(project_id),
            items=items,
        )
```

Add the module-level mapping helper after the `_weights_to_response` helper:

```python
def _snapshot_item(record: FeatureInvocationEvidence) -> AdaptiveSnapshotItem:
    weights: AdaptiveWeightsResponse | None = None
    if record.adaptive_weights is not None:
        w = record.adaptive_weights
        weights = AdaptiveWeightsResponse(
            preference=max(0.0, min(1.0, w.get("preference", 0.0))),
            voice_fidelity=max(0.0, min(1.0, w.get("voice_fidelity", 0.0))),
            style_constraints=max(0.0, min(1.0, w.get("style_constraints", 0.0))),
            avoidance=max(0.0, min(1.0, w.get("avoidance", 0.0))),
        )
    return AdaptiveSnapshotItem(
        invocation_id=str(record.invocation_id) if record.invocation_id else None,
        novel_id=str(record.novel_id) if record.novel_id else None,
        intent=record.intent,
        mode=record.mode,
        created_at=record.created_at if record.created_at is not None
        else datetime.now(UTC),
        source_summary=record.adaptive_source_summary,
        weights=weights,
    )
```

Add `datetime` to the top-level (non-TYPE_CHECKING) imports in `service.py`:

```python
from datetime import UTC, datetime
```

(`FeatureInvocationEvidence` is referenced in `_snapshot_item`; it is imported under TYPE_CHECKING — since the helper only reads attributes at runtime, keep the annotation under TYPE_CHECKING and add a runtime import inside the function if a static checker complains, OR move `FeatureInvocationEvidence` to a runtime import. Prefer keeping it under TYPE_CHECKING and annotate with a string forward-ref `"FeatureInvocationEvidence"`.)

- [ ] **Step 5: Wire the evidence repo into DI**

In `apps/api/narrare/adaptive/dependencies.py`, update `get_adaptive_context_service`:

```python
def get_adaptive_context_service(
    session: SessionDep,
) -> AdaptiveContextService:
    """Create an AdaptiveContextService with production DI."""
    from narrare.adaptive.service import AdaptiveContextService
    from narrare.evidence.repository import EvidenceRepositoryImpl

    provider = get_adaptive_context_provider(session)
    settings_repo = get_adaptive_settings_repository(session)
    evidence_repo = EvidenceRepositoryImpl(session)
    return AdaptiveContextService(
        provider=provider,
        settings_repo=settings_repo,
        evidence_repo=evidence_repo,
    )
```

- [ ] **Step 6: Run the service test to verify it passes**

Run: `pytest tests/unit/api/adaptive/test_adaptive_snapshots_service.py -v`
Expected: PASS (both tests).

- [ ] **Step 7: Run existing adaptive service tests to verify no regression**

Run: `pytest tests/unit/api/adaptive/ tests/integration/ -k adaptive -v`
Expected: PASS — any existing test that constructs `AdaptiveContextService` must now pass `evidence_repo=`; update those call sites (add `evidence_repo=_FakeEvidenceRepo([])` or the production repo) if a test breaks.

- [ ] **Step 8: Commit**

```bash
git add apps/api/narrare/adaptive/schemas.py \
        apps/api/narrare/adaptive/service.py \
        apps/api/narrare/adaptive/dependencies.py \
        tests/unit/api/adaptive/
git commit -m "feat(adaptive): add get_adaptive_snapshots service + schemas + DI (ADR-070)"
```

---

### Task 5: REST endpoint — `GET /adaptive/{project_id}/snapshots`

**Files:**
- Modify: `apps/api/narrare/adaptive/router.py` (new route)
- Test: `tests/unit/api/adaptive/test_adaptive_snapshots_router.py`

**Interfaces:**
- Consumes: `AdaptiveContextService.get_adaptive_snapshots` (Task 4).
- Produces: `GET /api/v1/adaptive/{project_id}/snapshots?limit=20` → `AdaptiveSnapshotsResponse` (200), or 401 when auth missing.

- [ ] **Step 1: Write the failing router test**

Create `tests/unit/api/adaptive/test_adaptive_snapshots_router.py`:

```python
"""Router tests for GET /adaptive/{project_id}/snapshots (ADR-070)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from narrare.adaptive.router import router
from narrare.adaptive.schemas import (
    AdaptiveSnapshotItem,
    AdaptiveSnapshotsResponse,
)

if TYPE_CHECKING:
    from uuid import UUID


class _StubService:
    def __init__(self, response: AdaptiveSnapshotsResponse) -> None:
        self._response = response
        self.last_project_id: UUID | None = None
        self.last_limit: int | None = None

    async def get_adaptive_snapshots(
        self,
        project_id: UUID,
        user_id: UUID,
        limit: int = 20,
    ) -> AdaptiveSnapshotsResponse:
        self.last_project_id = project_id
        self.last_limit = limit
        return self._response


@pytest.fixture
def stub_service() -> _StubService:
    return _StubService(
        response=AdaptiveSnapshotsResponse(
            project_id=str(uuid4()),
            items=[
                AdaptiveSnapshotItem(
                    intent="dialogue_coach",
                    mode="dialogue_coach",
                    created_at=datetime(2026, 7, 23, tzinfo=UTC),
                    source_summary={"summary": "preferences"},
                )
            ],
        )
    )


@pytest.fixture
async def client(stub_service: _StubService) -> AsyncClient:
    from narrare._app.dependencies import CurrentUserIdDep

    app = FastAPI()
    app.include_router(router)

    async def _override_user() -> str:
        return str(uuid4())

    app.dependency_overrides[CurrentUserIdDep] = _override_user
    app.dependency_overrides[
        __import__(
            "narrare.adaptive.dependencies",
            fromlist=["get_adaptive_context_service"],
        ).get_adaptive_context_service
    ] = lambda: stub_service

    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


class TestGetSnapshotsEndpoint:
    async def test_returns_200_with_items(
        self,
        client: AsyncClient,
        stub_service: _StubService,
    ) -> None:
        novel = uuid4()
        resp = await client.get(f"/adaptive/{novel}/snapshots?limit=20")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["items"]) == 1
        assert body["items"][0]["source_summary"] == {"summary": "preferences"}
        assert stub_service.last_project_id == novel
        assert stub_service.last_limit == 20

    async def test_default_limit_is_20(
        self,
        client: AsyncClient,
        stub_service: _StubService,
    ) -> None:
        await client.get(f"/adaptive/{uuid4()}/snapshots")
        assert stub_service.last_limit == 20

    async def test_missing_auth_returns_401(self, stub_service: _StubService) -> None:
        app = FastAPI()
        app.include_router(router)  # no CurrentUserIdDep override → 401 path
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get(f"/adaptive/{uuid4()}/snapshots")
        assert resp.status_code in (401, 403)
```

> The exact auth-failure status depends on how `CurrentUserIdDep` is wired in the app shell (it may raise 401 or redirect). Assert `in (401, 403)` to stay robust to that wiring; tighten to 401 if the project's dependency explicitly raises `HTTPException(401)`.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/api/adaptive/test_adaptive_snapshots_router.py -v`
Expected: FAIL — route `/adaptive/{project_id}/snapshots` does not exist (404).

- [ ] **Step 3: Add the endpoint**

In `apps/api/narrare/adaptive/router.py`, add `AdaptiveSnapshotsResponse` to the schema import:

```python
from narrare.adaptive.schemas import (
    AdaptiveContextResponse,
    AdaptiveSettingsResponse,
    AdaptiveSnapshotsResponse,
    AdaptiveToggleInput,
    AdaptiveWeightsInput,
)
```

Add the route at the end of the file:

```python
@router.get(
    "/{project_id}/snapshots",
    response_model=AdaptiveSnapshotsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_adaptive_snapshots(
    project_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    limit: int = 20,
    service: AdaptiveContextService = Depends(get_adaptive_context_service),
) -> AdaptiveSnapshotsResponse:
    """Return recent adaptive snapshots for the dashboard timeline (ADR-070)."""
    return await service.get_adaptive_snapshots(
        project_id=project_id, user_id=uuid.UUID(user_id), limit=limit
    )
```

Update the module docstring endpoint list (top of `router.py`) to include the new route.

- [ ] **Step 4: Run the router test to verify it passes**

Run: `pytest tests/unit/api/adaptive/test_adaptive_snapshots_router.py -v`
Expected: PASS (all 3 tests).

- [ ] **Step 5: Full regression + type checks**

Run: `pytest tests/unit/api/adaptive/ tests/integration/evidence/ -v`
Expected: PASS.

Run: `just check-architecture` (or `python scripts/check_architecture.py`)
Expected: PASS — no RULE violations introduced (no `core/`→`apps/` import; contract before impl satisfied).

Run type checks (pyright/mypy per project config): `just typecheck` (or the project's equivalent)
Expected: PASS — all new methods fully annotated.

- [ ] **Step 6: Commit**

```bash
git add apps/api/narrare/adaptive/router.py \
        tests/unit/api/adaptive/test_adaptive_snapshots_router.py
git commit -m "feat(adaptive): add GET /adaptive/{project_id}/snapshots endpoint (ADR-070)"
```

---

## Self-Review

**1. Spec coverage:** ADR-070 requires (a) `novel_id` column → Task 1 ✅; (b) `novel_id` + `created_at` on Core → Task 1 ✅ (asymmetric per ADR); (c) Alembic migration after 0034 → Task 1 (0035) ✅; (d) write-path threading → Task 2 ✅; (e) `get_adaptive_snapshots(novel_id, limit)` → Task 3 ✅; (f) `GET /api/v1/adaptive/{project_id}/snapshots?limit=20` → Tasks 4–5 ✅; (g) tests at every layer → each task ✅.

**2. Placeholder scan:** No TBD/TODO/"add error handling" without code. The one advisory note (router auth-status robustness) includes the exact assertion to use. The `fake_provider`/`fake_settings_repo` fixture note gives a concrete fallback (local conftest stubs) rather than hand-waving.

**3. Type consistency:** `novel_id: UUID | None` is used identically in Core model, ORM, mapper, repository (`novel_id: UUID`), and service (`project_id: UUID` passed as `novel_id`). `get_adaptive_snapshots(novel_id, *, limit=20)` signature matches across repository, the `EvidenceSnapshotReader` Protocol, the `_FakeEvidenceRepo`, and the service call. `AdaptiveSnapshotsResponse`/`AdaptiveSnapshotItem` field names are consistent between schema, service mapping, router, and test assertions.
