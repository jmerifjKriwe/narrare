# Series Foundation — Slice 3: Series CRUD + Join Flow

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or superpowers:executing-plans. Steps use `- [ ]` for tracking.
>
> **Part of:** Series Foundation plan set — see `2026-07-29-series-foundation-index.md` for execution order.
> **Predecessor:** Slice 1+2 (`2026-07-29-series-foundation.md`) — must be merged first.
> **Successor:** Slice 4 (Frontend) — can start once this slice's endpoints are live.
> **Spec source:** `docs/superpowers/specs/2026-07-29-series-foundation-design.md`

**Goal:** Implement Series CRUD (create/read/update/delete) + Join Flow (Policy α: adaptive scope assignment with preview-then-apply) + KB Scope-Toggle (promote/demote) + Canon KB CRUD endpoints. After this slice: full backend API complete; frontend can consume.

**Architecture:** Standard Narrare domain module pattern (`series/` mirrors `novels/`). Contracts first (RULE-03). Service delegates DB to repository. Router delegates immediately to service. Join flow implements Policy α (heuristics if Canon empty, all-Overlay if Canon populated) with two-step preview/apply per user decision.

**Global constraints:** See `2026-07-29-series-foundation.md` §Global Constraints (RULE-03/04/05/06/07/11/14/22, TDD, no `--no-verify`, etc.).

---

## Task 3.1: series/contracts.py (Protocols)

**Files:**
- Create: `apps/api/narrare/series/contracts.py`
- Test: `tests/unit/api/series/test_contracts.py`

**Interfaces:**
- Consumes: `Series`, `SeriesSettings` from Core (Task 1.1), `Series` SQLAlchemy (Task 1.2), `Novel` (existing), KBRepository scope methods (Task 2.2)
- Produces: `SeriesRepositoryProtocol`, `SeriesServiceProtocol`, `SeriesJoinServiceProtocol` — implemented by Tasks 3.3, 3.4, 3.5

- [ ] **Step 1: Write failing test**

```python
# tests/unit/api/series/test_contracts.py
"""Smoke test: Protocols are importable and have expected method signatures."""
import inspect
from narrare.series.contracts import (
    SeriesRepositoryProtocol, SeriesServiceProtocol, SeriesJoinServiceProtocol,
)


def test_series_repository_protocol_methods():
    methods = {
        "create", "get", "list_for_user", "update", "delete",
        "list_novels", "reorder_novels", "get_settings", "update_settings",
    }
    actual = set(dir(SeriesRepositoryProtocol))
    assert methods.issubset(actual)


def test_series_service_protocol_methods():
    methods = {
        "create_series", "get_series", "list_series",
        "update_series", "delete_series",
    }
    actual = set(dir(SeriesServiceProtocol))
    assert methods.issubset(actual)


def test_series_join_service_protocol_methods():
    methods = {"preview_join", "apply_join"}
    actual = set(dir(SeriesJoinServiceProtocol))
    assert methods.issubset(actual)
```

- [ ] **Step 2: Run, verify fail**

```bash
pytest tests/unit/api/series/test_contracts.py -v
```
Expected: FAIL `ModuleNotFoundError: No module named 'narrare.series.contracts'`

- [ ] **Step 3: Implement contracts**

```python
# apps/api/narrare/series/contracts.py
"""Protocols for Series domain (RULE-03: contracts before implementation)."""
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from narrare_core.series.schemas import Series, SeriesSettings


class SeriesRepositoryProtocol(Protocol):
    async def create(self, user_id: UUID, title: str, subtitle: str | None,
                     description: str | None, genre: str | None,
                     writing_language: str | None,
                     planned_novel_count: int | None) -> Series: ...

    async def get(self, series_id: UUID) -> Series | None: ...

    async def list_for_user(self, user_id: UUID) -> list[Series]: ...

    async def update(self, series_id: UUID, **patch: object) -> Series | None: ...

    async def delete(self, series_id: UUID) -> bool: ...

    async def list_novels(self, series_id: UUID) -> list: ...  # list[NovelRow]

    async def reorder_novels(self, series_id: UUID, novel_ids: list[UUID]) -> None: ...

    async def get_settings(self, series_id: UUID) -> SeriesSettings | None: ...

    async def update_settings(self, series_id: UUID,
                              patch: dict[str, object]) -> SeriesSettings: ...


class SeriesServiceProtocol(Protocol):
    async def create_series(self, user_id: UUID, request: "SeriesCreateRequest") -> "SeriesResponse": ...
    async def get_series(self, series_id: UUID) -> "SeriesResponse": ...
    async def list_series(self, user_id: UUID) -> list["SeriesSummary"]: ...
    async def update_series(self, series_id: UUID, request: "SeriesUpdateRequest") -> "SeriesResponse": ...
    async def delete_series(self, series_id: UUID) -> None: ...


class SeriesJoinServiceProtocol(Protocol):
    """Policy α: adaptive scope assignment on join."""

    async def preview_join(self, series_id: UUID, novel_id: UUID) -> "JoinPreview": ...
    async def apply_join(self, series_id: UUID, novel_id: UUID,
                         position: int) -> "JoinResult": ...
```

- [ ] **Step 4: Run, verify pass**

```bash
pytest tests/unit/api/series/test_contracts.py -v
```
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/api/narrare/series/contracts.py tests/unit/api/series/test_contracts.py
git commit -m "feat(api/series): add contracts (Protocols) for SeriesRepository, Service, JoinService

Spec 1 Slice 3 Task 3.1 — Protocol definitions per RULE-03 (contracts-first).
Three protocols cover CRUD, settings, and join flow. Implemented by
Tasks 3.3 (repository), 3.4 (service), 3.5 (join_service)."
```

---

## Task 3.2: series/schemas.py (Pydantic Request/Response)

**Files:**
- Create: `apps/api/narrare/series/schemas.py`
- Test: `tests/unit/api/series/test_schemas.py`

**Interfaces:**
- Consumes: `Series`, `SeriesSettings` from Core (Task 1.1)
- Produces: `SeriesCreateRequest`, `SeriesUpdateRequest`, `SeriesResponse`, `SeriesSummary`, `JoinPreview`, `JoinResult`, `SeriesSettingsResponse`, `SeriesSettingsUpdateRequest` — used by Router (Task 3.6), Frontend (Slice 4)

- [ ] **Step 1: Write failing test**

```python
# tests/unit/api/series/test_schemas.py
import pytest
from uuid import uuid4
from narrare.series.schemas import (
    SeriesCreateRequest, SeriesUpdateRequest, SeriesResponse,
    SeriesSummary, JoinPreview, JoinResult,
    JoinEntryTreatment, SeriesSettingsUpdateRequest,
)


class TestSeriesCreateRequest:
    def test_minimal_valid(self):
        r = SeriesCreateRequest(title="The Expanse")
        assert r.title == "The Expanse"
        assert r.subtitle is None
        assert r.status is None  # defaults to draft in service

    def test_status_invalid_rejected(self):
        with pytest.raises(ValueError):
            SeriesCreateRequest(title="X", status="invalid")


class TestSeriesUpdateRequest:
    def test_all_fields_optional(self):
        r = SeriesUpdateRequest()
        assert r.title is None
        assert r.status is None


class TestJoinPreview:
    def test_structure(self):
        p = JoinPreview(
            series_id=uuid4(), novel_id=uuid4(),
            canon_empty=True,
            treatments=[
                JoinEntryTreatment(entry_id=uuid4(), slug="magic",
                                   entity_type="system",
                                   current_scope="novel",
                                   target_scope="series",
                                   reason="Entity type 'system' defaults to Canon"),
            ],
        )
        assert p.canon_empty is True
        assert len(p.treatments) == 1


class TestJoinResult:
    def test_structure(self):
        r = JoinResult(
            series_id=uuid4(), novel_id=uuid4(), position=2,
            promoted_to_canon=5, kept_as_overlay=12,
        )
        assert r.promoted_to_canon == 5
```

- [ ] **Step 2: Run, verify fail**

```bash
pytest tests/unit/api/series/test_schemas.py -v
```
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Implement schemas**

```python
# apps/api/narrare/series/schemas.py
"""Pydantic request/response schemas for Series API."""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from narrare_core.series.schemas import SeriesStatus


class SeriesCreateRequest(BaseModel):
    """POST /api/v1/series body."""
    title: str
    subtitle: str | None = None
    description: str | None = None
    genre: str | None = None
    writing_language: str | None = None
    status: SeriesStatus | None = None  # service defaults to "draft"
    planned_novel_count: int | None = None


class SeriesUpdateRequest(BaseModel):
    """PATCH /api/v1/series/{id} body. All fields optional."""
    title: str | None = None
    subtitle: str | None = None
    description: str | None = None
    genre: str | None = None
    writing_language: str | None = None
    status: SeriesStatus | None = None
    planned_novel_count: int | None = None


class SeriesResponse(BaseModel):
    """Response for single Series GET/POST/PATCH."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    title: str
    subtitle: str | None
    description: str | None
    genre: str | None
    writing_language: str | None
    status: SeriesStatus
    planned_novel_count: int | None
    novel_count: int = 0  # computed; not stored on Series


class SeriesSummary(BaseModel):
    """List item: lighter than SeriesResponse."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    subtitle: str | None
    status: SeriesStatus
    novel_count: int = 0


class SeriesSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    series_id: UUID
    author_voice: dict[str, object] | None


class SeriesSettingsUpdateRequest(BaseModel):
    """PATCH /api/v1/series/{id}/settings body."""
    author_voice: dict[str, object] | None = None  # Spec 1: usually null


# --- Join Flow types ---

class JoinEntryTreatment(BaseModel):
    """Per-entry decision in a JoinPreview: what would happen to this entry."""
    entry_id: UUID
    slug: str
    entity_type: str
    current_scope: Literal["novel"]  # before join, all entries are novel-scoped
    target_scope: Literal["series", "novel"]  # after join + apply
    reason: str  # human-readable explanation


class JoinPreview(BaseModel):
    """Result of POST /api/v1/series/{id}/novels (preview step).

    Lists every KB entry of the joining novel + how it would be treated
    on apply (promoted to Canon or kept as Overlay) based on Policy α.
    """
    series_id: UUID
    novel_id: UUID
    canon_empty: bool  # if True → heuristics apply; if False → all stay Overlay
    treatments: list[JoinEntryTreatment]


class JoinResult(BaseModel):
    """Result of POST /api/v1/series/{id}/novels/{novel_id}/apply."""
    series_id: UUID
    novel_id: UUID
    position: int
    promoted_to_canon: int  # 0 if canon was non-empty
    kept_as_overlay: int
```

- [ ] **Step 4: Run, verify pass**

```bash
pytest tests/unit/api/series/test_schemas.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/narrare/series/schemas.py tests/unit/api/series/test_schemas.py
git commit -m "feat(api/series): add Pydantic request/response schemas

Spec 1 Slice 3 Task 3.2 — SeriesCreateRequest, SeriesUpdateRequest,
SeriesResponse, SeriesSummary, settings schemas, plus Join Flow types
(JoinPreview, JoinEntryTreatment, JoinResult). JoinPreview exposes
per-entry treatment so UI can show 'what would happen' before apply."
```

---

## Task 3.3: series/repository.py (CRUD)

**Files:**
- Create: `apps/api/narrare/series/repository.py`
- Test: `tests/unit/api/series/test_repository.py`

**Interfaces:**
- Consumes: `SeriesRepositoryProtocol` (Task 3.1), `Series`/`SeriesSettings` SQLAlchemy (Task 1.2)
- Produces: `SeriesRepository` — used by Service (Task 3.4), JoinService (Task 3.5)

- [ ] **Step 1: Write failing test**

```python
# tests/unit/api/series/test_repository.py
import pytest
from uuid import uuid4

from narrare.series.repository import SeriesRepository


@pytest.mark.asyncio
async def test_create_series_returns_with_id(fake_session):
    repo = SeriesRepository(fake_session)
    s = await repo.create(
        user_id=uuid4(), title="The Expanse", subtitle=None,
        description=None, genre=None, writing_language=None,
        planned_novel_count=9,
    )
    assert s.id is not None
    assert s.title == "The Expanse"
    assert s.status == "draft"


@pytest.mark.asyncio
async def test_get_returns_none_for_unknown_id(fake_session):
    repo = SeriesRepository(fake_session)
    s = await repo.get(uuid4())
    assert s is None


@pytest.mark.asyncio
async def test_list_for_user_returns_only_users_series(fake_session_with_data):
    user_id = uuid4()
    repo = SeriesRepository(fake_session_with_data)
    series_list = await repo.list_for_user(user_id)
    assert all(s.user_id == user_id for s in series_list)


@pytest.mark.asyncio
async def test_update_changes_provided_fields_only(fake_session_with_series):
    repo = SeriesRepository(fake_session_with_series)
    series_id = ...  # fixture provides
    updated = await repo.update(series_id, title="New Title")
    assert updated.title == "New Title"


@pytest.mark.asyncio
async def test_delete_returns_true_on_success_false_if_missing(fake_session):
    repo = SeriesRepository(fake_session)
    assert await repo.delete(uuid4()) is False  # nothing to delete


@pytest.mark.asyncio
async def test_get_settings_returns_none_if_no_settings_row(fake_session):
    repo = SeriesRepository(fake_session)
    settings = await repo.get_settings(uuid4())
    assert settings is None


@pytest.mark.asyncio
async def test_list_novels_returns_empty_for_empty_series(fake_session):
    repo = SeriesRepository(fake_session)
    novels = await repo.list_novels(uuid4())
    assert novels == []


@pytest.mark.asyncio
async def test_reorder_novels_assigns_sequential_positions(fake_session_with_novels):
    repo = SeriesRepository(fake_session_with_novels)
    series_id = ...  # fixture
    novel_ids = [...]  # fixture
    await repo.reorder_novels(series_id, novel_ids)
    # Verify positions are 1..N
```

(Fill in fixture-provided IDs from existing test fakes pattern.)

- [ ] **Step 2: Run, verify fail**

```bash
pytest tests/unit/api/series/test_repository.py -v
```
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Implement repository**

```python
# apps/api/narrare/series/repository.py
"""SeriesRepository — DB queries for Series + SeriesSettings."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.novels.models import Novel
from narrare.series.contracts import SeriesRepositoryProtocol
from narrare.series.models import Series as SeriesModel, SeriesSettings as SeriesSettingsModel
from narrare_core.series.schemas import Series, SeriesSettings


class SeriesRepository(SeriesRepositoryProtocol):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self, user_id: UUID, title: str, subtitle: str | None,
        description: str | None, genre: str | None,
        writing_language: str | None, planned_novel_count: int | None,
    ) -> Series:
        model = SeriesModel(
            user_id=user_id, title=title, subtitle=subtitle,
            description=description, genre=genre,
            writing_language=writing_language,
            planned_novel_count=planned_novel_count,
            status="draft",  # always start as draft
        )
        self._session.add(model)
        # Also create empty SeriesSettings (1:1)
        await self._session.flush()
        settings = SeriesSettingsModel(series_id=model.id, author_voice=None)
        self._session.add(settings)
        await self._session.flush()
        return self._to_schema(model)

    async def get(self, series_id: UUID) -> Series | None:
        result = await self._session.execute(
            select(SeriesModel).where(SeriesModel.id == series_id)
        )
        model = result.scalar_one_or_none()
        return self._to_schema(model) if model else None

    async def list_for_user(self, user_id: UUID) -> list[Series]:
        result = await self._session.execute(
            select(SeriesModel).where(SeriesModel.user_id == user_id)
        )
        return [self._to_schema(m) for m in result.scalars().all()]

    async def update(self, series_id: UUID, **patch: object) -> Series | None:
        if not patch:
            return await self.get(series_id)
        await self._session.execute(
            update(SeriesModel).where(SeriesModel.id == series_id).values(**patch)
        )
        return await self.get(series_id)

    async def delete(self, series_id: UUID) -> bool:
        result = await self._session.execute(
            select(SeriesModel).where(SeriesModel.id == series_id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return False
        await self._session.delete(model)
        return True

    async def list_novels(self, series_id: UUID) -> list[Novel]:
        result = await self._session.execute(
            select(Novel)
            .where(Novel.series_id == series_id)
            .order_by(Novel.series_position.asc())
        )
        return list(result.scalars().all())

    async def reorder_novels(self, series_id: UUID, novel_ids: list[UUID]) -> None:
        for position, novel_id in enumerate(novel_ids, start=1):
            await self._session.execute(
                update(Novel)
                .where(Novel.id == novel_id, Novel.series_id == series_id)
                .values(series_position=position)
            )

    async def get_settings(self, series_id: UUID) -> SeriesSettings | None:
        result = await self._session.execute(
            select(SeriesSettingsModel).where(SeriesSettingsModel.series_id == series_id)
        )
        model = result.scalar_one_or_none()
        return self._settings_to_schema(model) if model else None

    async def update_settings(self, series_id: UUID, patch: dict[str, object]) -> SeriesSettings:
        result = await self._session.execute(
            select(SeriesSettingsModel).where(SeriesSettingsModel.series_id == series_id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            # create on demand
            model = SeriesSettingsModel(series_id=series_id)
            self._session.add(model)
        for k, v in patch.items():
            setattr(model, k, v)
        await self._session.flush()
        return self._settings_to_schema(model)

    @staticmethod
    def _to_schema(model: SeriesModel) -> Series:
        return Series(
            id=model.id, user_id=model.user_id, title=model.title,
            subtitle=model.subtitle, description=model.description,
            genre=model.genre, writing_language=model.writing_language,
            status=model.status, planned_novel_count=model.planned_novel_count,
            created_at=model.created_at, updated_at=model.updated_at,
        )

    @staticmethod
    def _settings_to_schema(model: SeriesSettingsModel) -> SeriesSettings:
        return SeriesSettings(
            series_id=model.series_id, author_voice=model.author_voice,
            created_at=model.created_at, updated_at=model.updated_at,
        )
```

- [ ] **Step 4: Run, verify pass**

```bash
pytest tests/unit/api/series/test_repository.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/narrare/series/repository.py tests/unit/api/series/test_repository.py
git commit -m "feat(api/series): implement SeriesRepository (CRUD + settings + novels)

Spec 1 Slice 3 Task 3.3 — full CRUD for Series, get/update for
SeriesSettings, list_novels and reorder_novels. Creates SeriesSettings
row alongside Series on create (1:1 invariant). Returns Core Pydantic
types (Series, SeriesSettings)."
```

---

## Task 3.4: series/service.py (CRUD business logic)

**Files:**
- Create: `apps/api/narrare/series/service.py`
- Test: `tests/unit/api/series/test_service.py`

**Interfaces:**
- Consumes: `SeriesRepositoryProtocol` (Task 3.1), schemas (Task 3.2), Core types
- Produces: `SeriesService` — used by Router (Task 3.6)

- [ ] **Step 1: Write failing test**

```python
# tests/unit/api/series/test_service.py
import pytest
from uuid import uuid4

from narrare.series.service import SeriesService
from narrare.series.schemas import SeriesCreateRequest, SeriesUpdateRequest


@pytest.mark.asyncio
async def test_create_series_returns_response_with_id(fake_repo):
    service = SeriesService(fake_repo)
    resp = await service.create_series(
        user_id=uuid4(),
        request=SeriesCreateRequest(title="Millennium"),
    )
    assert resp.id is not None
    assert resp.title == "Millennium"
    assert resp.status == "draft"


@pytest.mark.asyncio
async def test_get_series_404_if_missing(fake_repo):
    service = SeriesService(fake_repo)
    with pytest.raises(SeriesNotFoundError):
        await service.get_series(uuid4())


@pytest.mark.asyncio
async def test_status_transition_draft_to_active_allowed(fake_repo_with_series):
    service = SeriesService(fake_repo_with_series)
    series_id = ...
    resp = await service.update_series(series_id, SeriesUpdateRequest(status="active"))
    assert resp.status == "active"


@pytest.mark.asyncio
async def test_status_transition_draft_to_completed_rejected(fake_repo_with_series):
    """No skipping states: draft → active → completed."""
    service = SeriesService(fake_repo_with_series)
    series_id = ...
    with pytest.raises(InvalidStatusTransitionError):
        await service.update_series(series_id, SeriesUpdateRequest(status="completed"))


@pytest.mark.asyncio
async def test_delete_series_cascades_via_repo(fake_repo):
    service = SeriesService(fake_repo)
    # delete returns None on success; 404 if missing
    with pytest.raises(SeriesNotFoundError):
        await service.delete_series(uuid4())
```

(Fill in fixtures per ADR-030 Fake pattern.)

- [ ] **Step 2: Run, verify fail**

- [ ] **Step 3: Implement service**

```python
# apps/api/narrare/series/service.py
"""SeriesService — CRUD business logic for Series."""
from __future__ import annotations

from uuid import UUID

from narrare.series.contracts import SeriesRepositoryProtocol
from narrare.series.schemas import (
    SeriesCreateRequest, SeriesUpdateRequest, SeriesResponse, SeriesSummary,
)

# Status transition matrix: only adjacent transitions allowed
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"active"},
    "active": {"completed", "draft"},  # can abandon back to draft
    "completed": {"draft"},  # can reopen
}


class SeriesNotFoundError(Exception):
    """Raised when a Series is not found."""


class InvalidStatusTransitionError(Exception):
    """Raised when a status transition is not allowed."""


class SeriesService:
    def __init__(self, repo: SeriesRepositoryProtocol) -> None:
        self._repo = repo

    async def create_series(
        self, user_id: UUID, request: SeriesCreateRequest,
    ) -> SeriesResponse:
        series = await self._repo.create(
            user_id=user_id, title=request.title, subtitle=request.subtitle,
            description=request.description, genre=request.genre,
            writing_language=request.writing_language,
            planned_novel_count=request.planned_novel_count,
        )
        return SeriesResponse(
            id=series.id, user_id=series.user_id, title=series.title,
            subtitle=series.subtitle, description=series.description,
            genre=series.genre, writing_language=series.writing_language,
            status=series.status, planned_novel_count=series.planned_novel_count,
            novel_count=0,
        )

    async def get_series(self, series_id: UUID) -> SeriesResponse:
        series = await self._repo.get(series_id)
        if series is None:
            raise SeriesNotFoundError(f"Series {series_id} not found")
        novels = await self._repo.list_novels(series_id)
        return SeriesResponse(
            id=series.id, user_id=series.user_id, title=series.title,
            subtitle=series.subtitle, description=series.description,
            genre=series.genre, writing_language=series.writing_language,
            status=series.status, planned_novel_count=series.planned_novel_count,
            novel_count=len(novels),
        )

    async def list_series(self, user_id: UUID) -> list[SeriesSummary]:
        series_list = await self._repo.list_for_user(user_id)
        summaries = []
        for s in series_list:
            novels = await self._repo.list_novels(s.id)
            summaries.append(SeriesSummary(
                id=s.id, title=s.title, subtitle=s.subtitle,
                status=s.status, novel_count=len(novels),
            ))
        return summaries

    async def update_series(
        self, series_id: UUID, request: SeriesUpdateRequest,
    ) -> SeriesResponse:
        existing = await self._repo.get(series_id)
        if existing is None:
            raise SeriesNotFoundError(f"Series {series_id} not found")

        patch = request.model_dump(exclude_none=True)

        # Validate status transition
        if "status" in patch and patch["status"] != existing.status:
            allowed = _ALLOWED_TRANSITIONS.get(existing.status, set())
            if patch["status"] not in allowed:
                raise InvalidStatusTransitionError(
                    f"Cannot transition from '{existing.status}' to '{patch['status']}'"
                )

        updated = await self._repo.update(series_id, **patch)
        # Re-fetch via get_series for response with novel_count
        return await self.get_series(series_id)

    async def delete_series(self, series_id: UUID) -> None:
        deleted = await self._repo.delete(series_id)
        if not deleted:
            raise SeriesNotFoundError(f"Series {series_id} not found")
```

- [ ] **Step 4: Run, verify pass**

- [ ] **Step 5: Commit**

```bash
git add apps/api/narrare/series/service.py tests/unit/api/series/test_service.py
git commit -m "feat(api/series): implement SeriesService (CRUD + status transitions)

Spec 1 Slice 3 Task 3.4 — business logic with status-transition matrix
(draft→active→completed; can revert). 404 on missing. Returns response
DTOs with computed novel_count."
```

---

## Task 3.5: series/join_service.py (Policy α — Preview + Apply)

**Files:**
- Create: `apps/api/narrare/series/join_service.py`
- Test: `tests/unit/api/series/test_join_service.py`

**Interfaces:**
- Consumes: `SeriesJoinServiceProtocol` (Task 3.1), `SeriesRepositoryProtocol`, `KBRepositoryProtocol` (existing + Task 2.2 scope methods), `NovelRepositoryProtocol` (existing)
- Produces: `SeriesJoinService` — used by Router (Task 3.6)

> **Policy α core logic:**
> - `preview_join`: determine if Series-Canon is empty. For each KB entry in the joining novel, decide treatment.
>   - If Canon empty → apply Policy iii heuristics: `system/concept/setting/location/object/timeline → promote to Canon`; `character/faction → keep as Overlay`
>   - If Canon non-empty → all entries stay Overlay
> - `apply_join`: execute the previewed treatments atomically.

- [ ] **Step 1: Write failing test**

```python
# tests/unit/api/series/test_join_service.py
import pytest
from uuid import uuid4

from narrare.series.join_service import SeriesJoinService, NovelAlreadyInSeriesError
from narrare.series.schemas import JoinPreview


# Entity types that Policy iii promotes to Canon by default
CANON_TYPES = {"system", "concept", "setting", "location", "object", "timeline"}
OVERLAY_TYPES = {"character", "faction"}


@pytest.mark.asyncio
async def test_preview_join_canon_empty_applies_heuristics(
    fake_repos_with_empty_canon_series,
):
    """Policy α: empty Canon → Policy iii heuristics apply."""
    service = SeriesJoinService(*fake_repos_with_empty_canon_series)
    preview = await service.preview_join(series_id=uuid4(), novel_id=uuid4())
    assert preview.canon_empty is True
    # All canon-type entries should be marked target_scope="series"
    for t in preview.treatments:
        if t.entity_type in CANON_TYPES:
            assert t.target_scope == "series"
        elif t.entity_type in OVERLAY_TYPES:
            assert t.target_scope == "novel"


@pytest.mark.asyncio
async def test_preview_join_canon_nonempty_keeps_all_overlay(
    fake_repos_with_populated_canon_series,
):
    """Policy α: non-empty Canon → all entries stay Novel-Overlay."""
    service = SeriesJoinService(*fake_repos_with_populated_canon_series)
    preview = await service.preview_join(series_id=uuid4(), novel_id=uuid4())
    assert preview.canon_empty is False
    for t in preview.treatments:
        assert t.target_scope == "novel"


@pytest.mark.asyncio
async def test_preview_join_rejects_novel_already_in_series(
    fake_repos_with_novel_in_other_series,
):
    service = SeriesJoinService(*fake_repos_with_novel_in_other_series)
    with pytest.raises(NovelAlreadyInSeriesError):
        await service.preview_join(series_id=uuid4(), novel_id=uuid4())


@pytest.mark.asyncio
async def test_apply_join_executes_preview_treatments(
    fake_repos_with_empty_canon_series,
):
    """Apply promotes canon-type entries to Canon, assigns novel.series_id."""
    service = SeriesJoinService(*fake_repos_with_empty_canon_series)
    series_id, novel_id = uuid4(), uuid4()
    preview = await service.preview_join(series_id, novel_id)
    result = await service.apply_join(series_id, novel_id, position=1)
    assert result.series_id == series_id
    assert result.position == 1
    assert result.promoted_to_canon > 0
    assert result.kept_as_overlay >= 0


@pytest.mark.asyncio
async def test_apply_join_atomic_on_failure(
    fake_repos_with_failing_promote,
):
    """If any promote fails, the entire join must roll back (RULE-11)."""
    service = SeriesJoinService(*fake_repos_with_failing_promote)
    with pytest.raises(Exception):  # whatever the underlying error is
        await service.apply_join(series_id=uuid4(), novel_id=uuid4(), position=1)
    # Verify novel.series_id was NOT set (rollback)
```

- [ ] **Step 2: Run, verify fail**

- [ ] **Step 3: Implement join service**

```python
# apps/api/narrare/series/join_service.py
"""SeriesJoinService — Policy α implementation (preview + apply).

Policy α: adaptive scope assignment based on Canon state.
- Canon empty → apply Policy iii heuristics (system/concept/etc → Canon)
- Canon non-empty → all joining entries stay Novel-Overlay
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from narrare.kb.contracts import KBRepositoryProtocol
from narrare.novels.contracts import NovelRepositoryProtocol
from narrare.series.contracts import SeriesJoinServiceProtocol, SeriesRepositoryProtocol
from narrare.series.schemas import JoinEntryTreatment, JoinPreview, JoinResult


# Policy iii entity-type defaults
_CANON_TYPES: set[str] = {"system", "concept", "setting", "location", "object", "timeline"}
_OVERLAY_TYPES: set[str] = {"character", "faction"}


class NovelAlreadyInSeriesError(Exception):
    """Raised when a novel is already in another series (409 Conflict)."""


class SeriesJoinService(SeriesJoinServiceProtocol):
    def __init__(
        self,
        session: AsyncSession,
        series_repo: SeriesRepositoryProtocol,
        novel_repo: NovelRepositoryProtocol,
        kb_repo: KBRepositoryProtocol,
    ) -> None:
        self._session = session
        self._series_repo = series_repo
        self._novel_repo = novel_repo
        self._kb_repo = kb_repo

    async def preview_join(self, series_id: UUID, novel_id: UUID) -> JoinPreview:
        novel = await self._novel_repo.get(novel_id)
        if novel is None:
            raise ValueError(f"Novel {novel_id} not found")
        if novel.series_id is not None and novel.series_id != series_id:
            raise NovelAlreadyInSeriesError(
                f"Novel {novel_id} already in series {novel.series_id}"
            )

        # Determine Canon state of target series
        canon_entries = await self._kb_repo.find_canon_for_series(series_id)
        canon_empty = len(canon_entries) == 0

        # All current entries of the novel (Novel-Overlay scope, since standalone)
        novel_entries = await self._kb_repo.find_overlay_for_novel(novel_id)

        treatments: list[JoinEntryTreatment] = []
        for entry in novel_entries:
            if canon_empty and entry.entity_type in _CANON_TYPES:
                target_scope = "series"
                reason = f"Entity type '{entry.entity_type}' defaults to Canon (Policy iii)"
            else:
                target_scope = "novel"
                if canon_empty and entry.entity_type in _OVERLAY_TYPES:
                    reason = f"Entity type '{entry.entity_type}' defaults to Novel-Overlay (Policy iii)"
                else:
                    reason = "Series-Canon is non-empty; new entries stay as Novel-Overlay (Policy α)"

            treatments.append(JoinEntryTreatment(
                entry_id=entry.id, slug=entry.slug, entity_type=entry.entity_type,
                current_scope="novel", target_scope=target_scope, reason=reason,
            ))

        return JoinPreview(
            series_id=series_id, novel_id=novel_id,
            canon_empty=canon_empty, treatments=treatments,
        )

    async def apply_join(
        self, series_id: UUID, novel_id: UUID, position: int,
    ) -> JoinResult:
        # Re-preview to get authoritative treatments
        preview = await self.preview_join(series_id, novel_id)

        promoted = 0
        kept = 0
        try:
            # 1. Set novel.series_id + series_position
            await self._novel_repo.update_series_membership(
                novel_id, series_id=series_id, series_position=position,
            )

            # 2. Apply per-entry treatments
            for t in preview.treatments:
                if t.target_scope == "series":
                    await self._kb_repo.promote_to_canon(novel_id, t.entry_id)
                    promoted += 1
                else:
                    kept += 1  # stays as Novel-Overlay; only series_id propagation happens

            # If canon_empty and entry kept as overlay, still set series_id on those
            # entries so they know they belong to the series now.
            # (Done implicitly via novel.series_id; entries reference novel_id,
            # which is in the series. No additional kb_entries.series_id needed for
            # Novel-Overlay entries — series_id is optional for them.)

            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

        return JoinResult(
            series_id=series_id, novel_id=novel_id, position=position,
            promoted_to_canon=promoted, kept_as_overlay=kept,
        )
```

> **Note for implementer:** `NovelRepository.update_series_membership()` is a new method needed on the existing `NovelRepositoryProtocol`. Add it to the existing contract + implementation. The method sets `series_id` and `series_position` on a novel row.

- [ ] **Step 4: Run, verify pass**

- [ ] **Step 5: Commit**

```bash
git add apps/api/narrare/series/join_service.py tests/unit/api/series/test_join_service.py apps/api/narrare/novels/contracts.py apps/api/narrare/novels/repository.py
git commit -m "feat(api/series): implement SeriesJoinService (Policy α preview/apply)

Spec 1 Slice 3 Task 3.5 — Policy α adaptive scope assignment:
- canon_empty → apply Policy iii heuristics (system/concept/setting/
  location/object/timeline → promote; character/faction → keep overlay)
- canon non-empty → all entries stay Novel-Overlay
Preview-then-Apply two-step per user decision. Atomic (commit/rollback).
NovelAlreadyInSeriesError for 409 Conflict. Adds NovelRepository.
update_series_membership() helper."
```

---

## Task 3.6: series/router.py + dependencies.py (HTTP endpoints)

**Files:**
- Create: `apps/api/narrare/series/router.py`
- Create: `apps/api/narrare/series/dependencies.py`
- Test: `tests/unit/api/series/test_router.py`

**Interfaces:**
- Consumes: `SeriesService` (Task 3.4), `SeriesJoinService` (Task 3.5)
- Produces: HTTP endpoints under `/api/v1/series/*`

- [ ] **Step 1: Write failing test (skeleton — full router tests require FastAPI TestClient integration)**

```python
# tests/unit/api/series/test_router.py
"""Smoke tests for series router — endpoint shape + auth.

Full integration coverage in tests/integration/test_series_api.py.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_post_series_creates_and_returns_201(authenticated_client: AsyncClient):
    response = await authenticated_client.post("/api/v1/series", json={"title": "Test"})
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test"
    assert data["status"] == "draft"


@pytest.mark.asyncio
async def test_get_series_404_for_unknown(authenticated_client: AsyncClient):
    response = await authenticated_client.get("/api/v1/series/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_series_list(authenticated_client: AsyncClient):
    response = await authenticated_client.get("/api/v1/series")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_delete_series_204(authenticated_client_with_series: AsyncClient):
    series_id = ...
    response = await authenticated_client_with_series.delete(f"/api/v1/series/{series_id}")
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_preview_join_endpoint(authenticated_client_with_series_and_novel: AsyncClient):
    """POST /series/{id}/novels returns JoinPreview (does NOT apply)."""
    series_id, novel_id = ...
    response = await authenticated_client_with_series_and_novel.post(
        f"/api/v1/series/{series_id}/novels",
        json={"novel_id": str(novel_id)},
    )
    assert response.status_code == 200
    data = response.json()
    assert "treatments" in data
    assert "canon_empty" in data


@pytest.mark.asyncio
async def test_apply_join_endpoint(authenticated_client_with_preview: AsyncClient):
    """POST /series/{id}/novels/{novel_id}/apply executes the join."""
    series_id, novel_id = ...
    response = await authenticated_client_with_preview.post(
        f"/api/v1/series/{series_id}/novels/{novel_id}/apply",
        json={"position": 1},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_apply_join_409_if_already_in_series(authenticated_client: AsyncClient):
    response = await authenticated_client.post(
        f"/api/v1/series/{uuid4()}/novels/{uuid4()}/apply",
        json={"position": 1},
    )
    # Depends on fixture state
    assert response.status_code in (409, 404)
```

- [ ] **Step 2: Implement router + dependencies**

```python
# apps/api/narrare/series/dependencies.py
"""DI factories for Series module."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from narrare._app.database import get_session
from narrare.kb.repository import KBRepository
from narrare.novels.repository import NovelRepository
from narrare.series.join_service import SeriesJoinService
from narrare.series.repository import SeriesRepository
from narrare.series.service import SeriesService


async def get_series_repository(session: AsyncSession = Depends(get_session)) -> SeriesRepository:
    return SeriesRepository(session)


async def get_series_service(
    repo: SeriesRepository = Depends(get_series_repository),
) -> SeriesService:
    return SeriesService(repo)


async def get_series_join_service(
    session: AsyncSession = Depends(get_session),
    series_repo: SeriesRepository = Depends(get_series_repository),
    novel_repo: NovelRepository = Depends(/* existing getter */),
    kb_repo: KBRepository = Depends(/* existing getter */),
) -> SeriesJoinService:
    return SeriesJoinService(session, series_repo, novel_repo, kb_repo)
```

```python
# apps/api/narrare/series/router.py
"""FastAPI routes for Series (RULE-06: thin router, delegates to service)."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from narrare._app.auth import current_user, User
from narrare.series.dependencies import get_series_service, get_series_join_service
from narrare.series.join_service import NovelAlreadyInSeriesError
from narrare.series.schemas import (
    SeriesCreateRequest, SeriesUpdateRequest, SeriesResponse, SeriesSummary,
    JoinPreview, JoinResult,
    SeriesSettingsResponse, SeriesSettingsUpdateRequest,
)
from narrare.series.service import InvalidStatusTransitionError, SeriesNotFoundError, SeriesService

router = APIRouter(prefix="/api/v1/series", tags=["series"])


@router.post("", response_model=SeriesResponse, status_code=201)
async def create_series(
    request: SeriesCreateRequest,
    user: User = Depends(current_user),
    service: SeriesService = Depends(get_series_service),
) -> SeriesResponse:
    return await service.create_series(user.id, request)


@router.get("", response_model=list[SeriesSummary])
async def list_series(
    user: User = Depends(current_user),
    service: SeriesService = Depends(get_series_service),
) -> list[SeriesSummary]:
    return await service.list_series(user.id)


@router.get("/{series_id}", response_model=SeriesResponse)
async def get_series(
    series_id: UUID,
    user: User = Depends(current_user),
    service: SeriesService = Depends(get_series_service),
) -> SeriesResponse:
    try:
        return await service.get_series(series_id)
    except SeriesNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/{series_id}", response_model=SeriesResponse)
async def update_series(
    series_id: UUID,
    request: SeriesUpdateRequest,
    user: User = Depends(current_user),
    service: SeriesService = Depends(get_series_service),
) -> SeriesResponse:
    try:
        return await service.update_series(series_id, request)
    except SeriesNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidStatusTransitionError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/{series_id}", status_code=204)
async def delete_series(
    series_id: UUID,
    user: User = Depends(current_user),
    service: SeriesService = Depends(get_series_service),
) -> None:
    try:
        await service.delete_series(series_id)
    except SeriesNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# --- Novels within Series ---

@router.get("/{series_id}/novels")
async def list_novels_in_series(
    series_id: UUID,
    user: User = Depends(current_user),
    service: SeriesService = Depends(get_series_service),
) -> list:
    """Returns novels in series, ordered by series_position."""
    # Implementor: delegate to service.list_novels(series_id) — add method
    ...


@router.post("/{series_id}/novels", response_model=JoinPreview)
async def preview_join(
    series_id: UUID,
    body: dict,  # {"novel_id": str}
    user: User = Depends(current_user),
    join_service: SeriesJoinService = Depends(get_series_join_service),
) -> JoinPreview:
    novel_id = UUID(body["novel_id"])
    try:
        return await join_service.preview_join(series_id, novel_id)
    except NovelAlreadyInSeriesError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/{series_id}/novels/{novel_id}/apply", response_model=JoinResult)
async def apply_join(
    series_id: UUID,
    novel_id: UUID,
    body: dict,  # {"position": int}
    user: User = Depends(current_user),
    join_service: SeriesJoinService = Depends(get_series_join_service),
) -> JoinResult:
    position = int(body.get("position", 1))
    try:
        return await join_service.apply_join(series_id, novel_id, position)
    except NovelAlreadyInSeriesError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/{series_id}/novels/{novel_id}", status_code=204)
async def remove_novel_from_series(
    series_id: UUID, novel_id: UUID,
    user: User = Depends(current_user),
) -> None:
    """Sets novel.series_id = NULL (back to standalone)."""
    # Implementor: delegate to novel service
    ...


@router.patch("/{series_id}/novels/reorder", status_code=204)
async def reorder_novels(
    series_id: UUID,
    body: dict,  # {"novel_ids": [str]}
    user: User = Depends(current_user),
    service: SeriesService = Depends(get_series_service),
) -> None:
    novel_ids = [UUID(n) for n in body["novel_ids"]]
    # Implementor: delegate to service.reorder_novels(series_id, novel_ids)
    ...


# --- Settings ---

@router.get("/{series_id}/settings", response_model=SeriesSettingsResponse)
async def get_settings(
    series_id: UUID,
    user: User = Depends(current_user),
    service: SeriesService = Depends(get_series_service),
) -> SeriesSettingsResponse:
    # Implementor: delegate to service.get_settings(series_id)
    ...


@router.patch("/{series_id}/settings", response_model=SeriesSettingsResponse)
async def update_settings(
    series_id: UUID,
    request: SeriesSettingsUpdateRequest,
    user: User = Depends(current_user),
    service: SeriesService = Depends(get_series_service),
) -> SeriesSettingsResponse:
    # Implementor: delegate to service.update_settings(series_id, request)
    ...
```

> **Note for implementer:** Wire `router` into the FastAPI app's router list (typically in `apps/api/narrare/_app/__init__.py` or wherever routers are registered). Follow existing pattern (e.g., how `volumes.router` is wired).

- [ ] **Step 3: Run tests, verify pass**

- [ ] **Step 4: Commit**

```bash
git add apps/api/narrare/series/router.py apps/api/narrare/series/dependencies.py tests/unit/api/series/test_router.py
git commit -m "feat(api/series): add router + DI for all Series endpoints

Spec 1 Slice 3 Task 3.6 — FastAPI routes for Series CRUD, novels-in-series
list, join preview/apply two-step, remove-from-series, reorder, settings
get/update. Thin router per RULE-06; delegates to SeriesService and
SeriesJoinService. Auth via current_user dependency."
```

---

## Task 3.7: kb/scope_service.py + scope-toggle endpoints

**Files:**
- Create: `apps/api/narrare/kb/scope_service.py`
- Modify: `apps/api/narrare/kb/router.py` (+promote/demote endpoints)
- Test: `tests/unit/api/kb/test_scope_service.py`, `tests/unit/api/kb/test_scope_endpoints.py`

**Interfaces:**
- Consumes: `KBRepository` scope methods (Task 2.2)
- Produces: `KBScopeService` with `promote_to_canon` / `demote_to_overlay`; HTTP endpoints

- [ ] **Step 1: Write failing test**

```python
# tests/unit/api/kb/test_scope_service.py
import pytest
from uuid import uuid4

from narrare.kb.scope_service import KBScopeService


@pytest.mark.asyncio
async def test_promote_to_canon_calls_repo(fake_kb_repo):
    service = KBScopeService(fake_kb_repo)
    await service.promote_to_canon(novel_id=uuid4(), entry_id=uuid4())
    fake_kb_repo.promote_to_canon.assert_called_once()


@pytest.mark.asyncio
async def test_demote_to_overlay_calls_repo(fake_kb_repo):
    service = KBScopeService(fake_kb_repo)
    await service.demote_to_overlay(
        series_id=uuid4(), entry_id=uuid4(), target_novel_id=uuid4(),
    )
    fake_kb_repo.demote_to_overlay.assert_called_once()
```

- [ ] **Step 2: Implement service**

```python
# apps/api/narrare/kb/scope_service.py
"""KBScopeService — business logic for promote/demote scope toggle."""
from __future__ import annotations

from uuid import UUID

from narrare.kb.contracts import KBRepositoryProtocol
from narrare_core.kb.schemas.entry import SeriesKBEntry, NovelKBEntry


class KBScopeService:
    def __init__(self, kb_repo: KBRepositoryProtocol) -> None:
        self._kb_repo = kb_repo

    async def promote_to_canon(self, novel_id: UUID, entry_id: UUID) -> SeriesKBEntry:
        """Overlay → Canon. Raises ValueError if entry isn't a Novel-Overlay of novel."""
        return await self._kb_repo.promote_to_canon(novel_id, entry_id)

    async def demote_to_overlay(
        self, series_id: UUID, entry_id: UUID, target_novel_id: UUID,
    ) -> NovelKBEntry:
        """Canon → Overlay for target_novel_id. Raises if entry isn't Canon of series."""
        return await self._kb_repo.demote_to_overlay(series_id, entry_id, target_novel_id)
```

- [ ] **Step 3: Add endpoints to existing `apps/api/narrare/kb/router.py`**

```python
# Append to existing kb/router.py:

from narrare.kb.scope_service import KBScopeService


@router.post("/novels/{novel_id}/kb/{entry_id}/promote")
async def promote_entry_to_canon(
    novel_id: UUID, entry_id: UUID,
    user: User = Depends(current_user),
    kb_repo: KBRepository = Depends(get_kb_repository),
) -> dict:
    """Overlay → Canon. Response: the promoted SeriesKBEntry."""
    service = KBScopeService(kb_repo)
    try:
        promoted = await service.promote_to_canon(novel_id, entry_id)
        return promoted.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/novels/{novel_id}/kb/{entry_id}/demote")
async def demote_entry_to_overlay(
    novel_id: UUID, entry_id: UUID,
    body: dict,  # {"target_novel_id": str, "series_id": str}
    user: User = Depends(current_user),
    kb_repo: KBRepository = Depends(get_kb_repository),
) -> dict:
    """Canon → Overlay for target_novel_id."""
    service = KBScopeService(kb_repo)
    try:
        demoted = await service.demote_to_overlay(
            series_id=UUID(body["series_id"]),
            entry_id=entry_id,
            target_novel_id=UUID(body["target_novel_id"]),
        )
        return demoted.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
```

- [ ] **Step 4: Run, verify pass**

- [ ] **Step 5: Commit**

```bash
git add apps/api/narrare/kb/scope_service.py apps/api/narrare/kb/router.py tests/unit/api/kb/test_scope_service.py tests/unit/api/kb/test_scope_endpoints.py
git commit -m "feat(api/kb): add scope-toggle endpoints (promote/demote)

Spec 1 Slice 3 Task 3.7 — KBScopeService thin wrapper over KBRepository
scope methods. Two new endpoints on existing kb/router.py:
- POST /novels/{id}/kb/{entry_id}/promote (Overlay → Canon)
- POST /novels/{id}/kb/{entry_id}/demote (Canon → Overlay; body has
  target_novel_id + series_id). 409 on invariant violation."
```

---

## Task 3.8: kb/router_series.py (Canon KB CRUD endpoints)

**Files:**
- Create: `apps/api/narrare/kb/router_series.py`
- Test: `tests/unit/api/kb/test_router_series.py`

**Interfaces:**
- Consumes: `KBRepository` scope methods (Task 2.2)
- Produces: HTTP endpoints under `/api/v1/series/{id}/kb/*` for Series-Canon KB CRUD

> **Note:** This is parallel to existing `kb/router.py` (which serves Novel-Overlay KB). Both routers use the same `KBRepository`; they differ in scope filtering.

- [ ] **Step 1: Write failing test (skeleton)**

```python
# tests/unit/api/kb/test_router_series.py
import pytest


@pytest.mark.asyncio
async def test_get_canon_kb_returns_list(authenticated_client_with_series):
    series_id = ...
    response = await authenticated_client_with_series.get(f"/api/v1/series/{series_id}/kb")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_create_canon_entry(authenticated_client_with_series):
    series_id = ...
    response = await authenticated_client_with_series.post(
        f"/api/v1/series/{series_id}/kb",
        json={"entity_type": "system", "name": "Magic", "slug": "magic", "body": "..."},
    )
    assert response.status_code == 201
```

- [ ] **Step 2: Implement router**

```python
# apps/api/narrare/kb/router_series.py
"""FastAPI routes for Series-Canon KB CRUD.

Parallel to kb/router.py (which serves Novel-Overlay KB). Both use
KBRepository; this one filters by series_id and novel_id IS NULL.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from narrare._app.auth import current_user, User
from narrare._app.database import get_session
from narrare.kb.repository import KBRepository

router = APIRouter(prefix="/api/v1/series/{series_id}/kb", tags=["kb", "series"])


@router.get("")
async def list_canon_entries(
    series_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list:
    repo = KBRepository(session)
    return [e.model_dump() for e in await repo.find_canon_for_series(series_id)]


@router.post("", status_code=201)
async def create_canon_entry(
    series_id: UUID,
    body: dict,  # {entity_type, name, slug, body, ...}
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    # Implementor: validate body, create KBEntry with series_id=series_id, novel_id=NULL
    # Reuse KBRepository.create() but pass series_id explicitly
    ...


@router.get("/{entry_id}")
async def get_canon_entry(series_id: UUID, entry_id: UUID, ...) -> dict:
    # Filter by both series_id and entry_id; verify novel_id IS NULL
    ...


@router.patch("/{entry_id}")
async def update_canon_entry(series_id: UUID, entry_id: UUID, body: dict, ...) -> dict:
    ...


@router.delete("/{entry_id}", status_code=204)
async def delete_canon_entry(series_id: UUID, entry_id: UUID, ...) -> None:
    ...
```

- [ ] **Step 3: Wire into app router list (alongside Task 3.6)**

- [ ] **Step 4: Run, verify pass**

- [ ] **Step 5: Commit**

```bash
git add apps/api/narrare/kb/router_series.py tests/unit/api/kb/test_router_series.py
git commit -m "feat(api/kb): add Canon KB CRUD router (/api/v1/series/{id}/kb/*)

Spec 1 Slice 3 Task 3.8 — parallel router to kb/router.py, scoped to
Series-Canon (novel_id IS NULL). Standard CRUD: list, create, get,
update, delete. Same KBRepository, different scope filter."
```

---

## Slice 3 Self-Review Checklist

After all tasks land, verify:

- [ ] `pytest tests/unit/api/series/ -v` — all green
- [ ] `pytest tests/unit/api/kb/test_scope*.py -v` — all green
- [ ] `pytest tests/integration/test_series_api.py -v` — endpoints work end-to-end (if integration test Postgres available)
- [ ] `just check` — architecture + adoption + AI-UX + size + streaming + prompt-structure green
- [ ] Regression: `pytest tests/unit/api/analysis/ tests/unit/api/writing/ -v` — ANAL-008/WRITE-010/ANAL-009 still green
- [ ] i18n: no new keys needed yet (frontend comes in Slice 4)
- [ ] No new architecture exceptions introduced

## Slice 3 → Slice 4 Handoff

After Slice 3 merges, Slice 4 (Frontend) can start. Frontend will consume these endpoints:

- Series CRUD: `/api/v1/series[/{id}]` (POST/GET/PATCH/DELETE)
- Series list: `/api/v1/series` (GET)
- Novels in series: `/api/v1/series/{id}/novels` (GET)
- Join preview: `/api/v1/series/{id}/novels` (POST body: `{novel_id}`)
- Join apply: `/api/v1/series/{id}/novels/{novel_id}/apply` (POST body: `{position}`)
- Remove from series: `/api/v1/series/{id}/novels/{novel_id}` (DELETE)
- Reorder novels: `/api/v1/series/{id}/novels/reorder` (PATCH body: `{novel_ids}`)
- Series settings: `/api/v1/series/{id}/settings` (GET/PATCH)
- Canon KB CRUD: `/api/v1/series/{id}/kb[/{entry_id}]` (POST/GET/PATCH/DELETE)
- KB scope toggle: `/api/v1/novels/{id}/kb/{entry_id}/promote|demote` (POST)
