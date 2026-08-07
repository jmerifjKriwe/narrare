"""Unit tests for ``KBCanonService`` — Series-Canon KB CRUD business logic.

Series Foundation Spec 1, Slice 3 Task 3.8.

Exercises the canon service against ``AsyncMock`` repos (no DB / no HTTP): the
canonical pattern from ``tests/unit/api/test_kb_service.py``. Covers ownership
verification, the canon scope invariant (``novel_id IS NULL``), slug uniqueness
within the canon scope, and the ORM→``SeriesKBEntry`` mapping. The HTTP status
codes are covered by the sibling ``test_router_series.py`` (RULE-04 split).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare.kb.canon_service import KBCanonService
from narrare.kb.contracts import KBRepositoryProtocol
from narrare.kb.models import KBEntry
from narrare.kb.schemas import KBEntryCreate, KBEntryUpdate
from narrare.series.contracts import SeriesRepositoryProtocol
from narrare_core.kb.schemas.entry import SeriesKBEntry
from narrare_core.series.schemas import Series
from narrare_core.shared.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)

OWNER_ID = uuid.uuid4()


def _make_series() -> MagicMock:
    """A Core ``Series`` mock owned by ``OWNER_ID``."""
    series = MagicMock(spec=Series)
    series.user_id = OWNER_ID
    return series


def _make_canon_entry(**overrides: object) -> MagicMock:
    """A canon KBEntry mock (``novel_id IS NULL``, ``series_id`` set)."""
    entry = MagicMock(spec=KBEntry)
    entry.id = overrides.get("id", uuid.uuid4())
    entry.novel_id = None
    entry.series_id = overrides.get("series_id", uuid.uuid4())
    entry.name = overrides.get("name", "Magic System")
    entry.slug = overrides.get("slug", "magic-system")
    entry.entity_type = overrides.get("entity_type", "system")
    entry.body = overrides.get("body", "")
    entry.status = overrides.get("status", "canon")
    entry.tags = overrides.get("tags", [])
    entry.review_status = overrides.get("review_status", "approved")
    entry.metadata_ = overrides.get("metadata_")
    entry.template_version = overrides.get("template_version")
    entry.source = overrides.get("source", "manual")
    entry.embeddings_dirty = overrides.get("embeddings_dirty", False)
    entry.last_referenced_at = None
    entry.usage_count = overrides.get("usage_count", 0)
    entry.created_at = overrides.get("created_at")
    entry.updated_at = overrides.get("updated_at")
    entry.base_entry_id = None
    return entry


def _make_service(*, series_owned: bool = True) -> tuple[KBCanonService, AsyncMock, AsyncMock]:
    """Build a KBCanonService with mock repos.

    ``series_owned=False`` makes the series lookup return ``None`` (missing).
    """
    kb_repo = AsyncMock(spec=KBRepositoryProtocol)
    series_repo = AsyncMock(spec=SeriesRepositoryProtocol)
    series_repo.get = AsyncMock(return_value=_make_series() if series_owned else None)
    return KBCanonService(kb_repo, series_repo), kb_repo, series_repo


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


class TestCreateCanon:
    async def test_create_returns_series_entry_with_novel_id_null(self) -> None:
        service, repo, _ = _make_service()
        series_id = uuid.uuid4()
        repo.find_canon_by_slug = AsyncMock(return_value=None)
        repo.create = AsyncMock(return_value=_make_canon_entry(series_id=series_id))

        data = KBEntryCreate(entity_type="system", name="Magic System")
        result = await service.create_canon(series_id, OWNER_ID, data)

        assert isinstance(result, SeriesKBEntry)
        assert result.novel_id is None
        assert result.series_id == series_id
        repo.create.assert_awaited_once()

    async def test_create_passes_canon_scope_to_repo(self) -> None:
        service, repo, _ = _make_service()
        series_id = uuid.uuid4()
        repo.find_canon_by_slug = AsyncMock(return_value=None)
        repo.create = AsyncMock(return_value=_make_canon_entry(series_id=series_id))

        await service.create_canon(
            series_id, OWNER_ID, KBEntryCreate(entity_type="system", name="X")
        )

        created = repo.create.call_args[0][0]
        assert created.novel_id is None
        assert created.series_id == series_id

    async def test_create_auto_generates_slug(self) -> None:
        service, repo, _ = _make_service()
        repo.find_canon_by_slug = AsyncMock(return_value=None)
        repo.create = AsyncMock(return_value=_make_canon_entry())

        await service.create_canon(
            uuid.uuid4(), OWNER_ID, KBEntryCreate(entity_type="system", name="Magic System")
        )

        assert repo.create.call_args[0][0].slug == "magic-system"

    async def test_create_duplicate_slug_raises_conflict(self) -> None:
        service, repo, _ = _make_service()
        repo.find_canon_by_slug = AsyncMock(return_value=_make_canon_entry())

        data = KBEntryCreate(entity_type="system", name="Magic System")
        with pytest.raises(ConflictError, match="already exists"):
            await service.create_canon(uuid.uuid4(), OWNER_ID, data)

    async def test_create_missing_series_raises_forbidden(self) -> None:
        service, _, _ = _make_service(series_owned=False)

        with pytest.raises(ForbiddenError, match="access to this series"):
            await service.create_canon(
                uuid.uuid4(), OWNER_ID, KBEntryCreate(entity_type="system", name="X")
            )

    async def test_create_not_owned_series_raises_forbidden(self) -> None:
        service, _, _ = _make_service()  # owned by OWNER_ID

        with pytest.raises(ForbiddenError, match="access to this series"):
            await service.create_canon(
                uuid.uuid4(), uuid.uuid4(), KBEntryCreate(entity_type="system", name="X")
            )

    async def test_create_invalid_metadata_raises_validation(self) -> None:
        service, repo, _ = _make_service()
        repo.find_canon_by_slug = AsyncMock(return_value=None)

        data = KBEntryCreate(entity_type="character", name="Bad", metadata={"age": "not_a_number"})
        with pytest.raises(ValidationError, match="Invalid metadata"):
            await service.create_canon(uuid.uuid4(), OWNER_ID, data)


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------


class TestGetCanon:
    async def test_get_existing_canon(self) -> None:
        service, repo, _ = _make_service()
        series_id = uuid.uuid4()
        entry = _make_canon_entry(series_id=series_id)
        repo.get_by_id = AsyncMock(return_value=entry)

        result = await service.get_canon(series_id, entry.id, OWNER_ID)

        assert isinstance(result, SeriesKBEntry)
        assert result.id == entry.id

    async def test_get_nonexistent_raises_not_found(self) -> None:
        service, repo, _ = _make_service()
        repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(NotFoundError, match="KBEntry"):
            await service.get_canon(uuid.uuid4(), uuid.uuid4(), OWNER_ID)

    async def test_get_overlay_entry_raises_not_found(self) -> None:
        """A non-canon entry (novel_id set) must not be reachable via canon CRUD."""
        service, repo, _ = _make_service()
        entry = _make_canon_entry()
        entry.novel_id = uuid.uuid4()  # overlay, not canon
        repo.get_by_id = AsyncMock(return_value=entry)

        with pytest.raises(NotFoundError, match="KBEntry"):
            await service.get_canon(uuid.uuid4(), entry.id, OWNER_ID)

    async def test_get_wrong_series_raises_not_found(self) -> None:
        service, repo, _ = _make_service()
        entry = _make_canon_entry(series_id=uuid.uuid4())
        repo.get_by_id = AsyncMock(return_value=entry)

        with pytest.raises(NotFoundError, match="KBEntry"):
            await service.get_canon(uuid.uuid4(), entry.id, OWNER_ID)

    async def test_get_missing_series_raises_forbidden(self) -> None:
        service, _, _ = _make_service(series_owned=False)

        with pytest.raises(ForbiddenError):
            await service.get_canon(uuid.uuid4(), uuid.uuid4(), OWNER_ID)


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


class TestUpdateCanon:
    async def test_update_name_regenerates_slug(self) -> None:
        service, repo, _ = _make_service()
        series_id = uuid.uuid4()
        entry = _make_canon_entry(series_id=series_id, slug="old-name")
        repo.get_by_id = AsyncMock(return_value=entry)
        repo.find_canon_by_slug = AsyncMock(return_value=None)
        repo.update = AsyncMock(return_value=entry)

        await service.update_canon(series_id, entry.id, OWNER_ID, KBEntryUpdate(name="New Name"))

        updates = repo.update.call_args[0][1]
        assert updates["name"] == "New Name"
        assert updates["slug"] == "new-name"

    async def test_update_duplicate_slug_raises_conflict(self) -> None:
        service, repo, _ = _make_service()
        entry = _make_canon_entry(slug="old-slug")
        repo.get_by_id = AsyncMock(return_value=entry)
        repo.find_canon_by_slug = AsyncMock(return_value=_make_canon_entry())

        with pytest.raises(ConflictError, match="already exists"):
            await service.update_canon(
                entry.series_id, entry.id, OWNER_ID, KBEntryUpdate(slug="taken-slug")
            )

    async def test_update_overlay_entry_raises_not_found(self) -> None:
        service, repo, _ = _make_service()
        entry = _make_canon_entry()
        entry.novel_id = uuid.uuid4()  # overlay
        repo.get_by_id = AsyncMock(return_value=entry)

        with pytest.raises(NotFoundError, match="KBEntry"):
            await service.update_canon(uuid.uuid4(), entry.id, OWNER_ID, KBEntryUpdate(name="X"))


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


class TestDeleteCanon:
    async def test_delete_existing_canon(self) -> None:
        service, repo, _ = _make_service()
        series_id = uuid.uuid4()
        entry = _make_canon_entry(series_id=series_id)
        repo.get_by_id = AsyncMock(return_value=entry)
        repo.delete = AsyncMock()

        await service.delete_canon(series_id, entry.id, OWNER_ID)

        repo.delete.assert_awaited_once_with(entry)

    async def test_delete_overlay_entry_raises_not_found(self) -> None:
        service, repo, _ = _make_service()
        entry = _make_canon_entry()
        entry.novel_id = uuid.uuid4()  # overlay
        repo.get_by_id = AsyncMock(return_value=entry)

        with pytest.raises(NotFoundError, match="KBEntry"):
            await service.delete_canon(uuid.uuid4(), entry.id, OWNER_ID)


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


class TestListCanon:
    async def test_list_returns_canon_entries(self) -> None:
        service, repo, _ = _make_service()
        series_id = uuid.uuid4()
        entries = [_make_canon_entry(series_id=series_id), _make_canon_entry(series_id=series_id)]
        repo.find_canon_for_series = AsyncMock(return_value=entries)

        result = await service.list_canon(series_id, OWNER_ID)

        assert result is entries
        repo.find_canon_for_series.assert_awaited_once_with(series_id)

    async def test_list_missing_series_raises_forbidden(self) -> None:
        service, _, _ = _make_service(series_owned=False)

        with pytest.raises(ForbiddenError):
            await service.list_canon(uuid.uuid4(), OWNER_ID)


# Shared update-builder tests live in test_entry_updates.py (RULE-04 split —
# build_entry_updates is tested with its own module, not KBCanonService).
