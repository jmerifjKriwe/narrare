"""Unit tests for KB service — business logic."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare.kb._utils import slugify
from narrare.kb.contracts import KBRepositoryProtocol
from narrare.kb.models import KBEntry
from narrare.kb.schemas import KBEntryCreate, KBEntryUpdate
from narrare.kb.service import KBService
from narrare.novels.contracts import NovelRepositoryProtocol
from narrare.novels.models import Novel
from narrare_core.shared.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)

# ---------------------------------------------------------------------------
# Slugify tests
# ---------------------------------------------------------------------------


class TestSlugify:
    def test_simple_name(self) -> None:
        assert slugify("John Smith") == "john-smith"

    def test_special_chars_removed(self) -> None:
        assert slugify("O'Brien & Co.") == "obrien-co"

    def test_multiple_spaces(self) -> None:
        assert slugify("  Hello   World  ") == "hello-world"

    def test_unicode_preserved_digits(self) -> None:
        assert slugify("Character #1") == "character-1"

    def test_german_chars_removed(self) -> None:
        assert slugify("Müller Haus") == "mller-haus"

    def test_empty_string(self) -> None:
        assert slugify("") == ""

    def test_only_special_chars(self) -> None:
        assert slugify("@#$%") == ""


# ---------------------------------------------------------------------------
# Service tests
# ---------------------------------------------------------------------------


def _make_service(
    novel_owned: bool = True,
) -> tuple[KBService, AsyncMock, AsyncMock]:
    """Create a KBService with mock repos."""
    repo = AsyncMock(spec=KBRepositoryProtocol)
    novel_repo = AsyncMock(spec=NovelRepositoryProtocol)

    if novel_owned:
        novel = MagicMock(spec=Novel)
        novel_repo.get_by_id = AsyncMock(return_value=novel)
    else:
        novel_repo.get_by_id = AsyncMock(return_value=None)

    service = KBService(repo=repo, novel_repo=novel_repo)
    return service, repo, novel_repo


class TestKBServiceCreate:
    async def test_create_with_valid_data(self) -> None:
        service, repo, _ = _make_service()
        repo.get_by_slug = AsyncMock(return_value=None)

        entry = MagicMock(spec=KBEntry)
        entry.id = uuid.uuid4()
        repo.create = AsyncMock(return_value=entry)

        data = KBEntryCreate(
            entity_type="character",
            name="John Smith",
        )
        result = await service.create(uuid.uuid4(), uuid.uuid4(), data)
        assert result is entry
        repo.create.assert_called_once()

    async def test_create_auto_generates_slug(self) -> None:
        service, repo, _ = _make_service()
        repo.get_by_slug = AsyncMock(return_value=None)
        repo.create = AsyncMock(return_value=MagicMock(spec=KBEntry))

        data = KBEntryCreate(entity_type="character", name="John Smith")
        await service.create(uuid.uuid4(), uuid.uuid4(), data)

        call_args = repo.create.call_args[0][0]
        assert call_args.slug == "john-smith"

    async def test_create_with_custom_slug(self) -> None:
        service, repo, _ = _make_service()
        repo.get_by_slug = AsyncMock(return_value=None)
        repo.create = AsyncMock(return_value=MagicMock(spec=KBEntry))

        data = KBEntryCreate(entity_type="character", name="John", slug="custom-slug")
        await service.create(uuid.uuid4(), uuid.uuid4(), data)

        call_args = repo.create.call_args[0][0]
        assert call_args.slug == "custom-slug"

    async def test_create_duplicate_slug_raises_conflict(self) -> None:
        service, repo, _ = _make_service()
        repo.get_by_slug = AsyncMock(return_value=MagicMock(spec=KBEntry))

        data = KBEntryCreate(entity_type="character", name="John")
        with pytest.raises(ConflictError, match="already exists"):
            await service.create(uuid.uuid4(), uuid.uuid4(), data)

    async def test_create_forbidden_novel(self) -> None:
        service, _, _ = _make_service(novel_owned=False)

        data = KBEntryCreate(entity_type="character", name="John")
        with pytest.raises(ForbiddenError, match="access to this novel"):
            await service.create(uuid.uuid4(), uuid.uuid4(), data)

    async def test_create_with_invalid_metadata_raises_validation(self) -> None:
        service, repo, _ = _make_service()
        repo.get_by_slug = AsyncMock(return_value=None)

        data = KBEntryCreate(
            entity_type="character",
            name="Bad",
            metadata={"age": "not_a_number"},
        )
        # This should raise ValidationError from schema validation
        with pytest.raises(ValidationError, match="Invalid metadata"):
            await service.create(uuid.uuid4(), uuid.uuid4(), data)

    async def test_create_with_omitted_metadata_persists_empty_dict(self) -> None:
        """Omitted/None metadata persists as {}, never jsonb null.

        The UI create form omits the field. The column is nullable with a
        Python-side ``default=dict`` — an explicitly-set None bypasses
        that default and persists jsonb null, which flowed to the FE as
        `"metadata": null` and crashed the detail view (Task 7
        KB-management E2E, 2026-10-16; schema default + service coercion).
        """
        service, repo, _ = _make_service()
        repo.get_by_slug = AsyncMock(return_value=None)
        repo.create = AsyncMock(return_value=MagicMock(spec=KBEntry))

        data = KBEntryCreate(entity_type="character", name="John")
        await service.create(uuid.uuid4(), uuid.uuid4(), data)

        call_args = repo.create.call_args[0][0]
        assert call_args.metadata_ == {}

    async def test_create_with_explicit_metadata_passes_through(self) -> None:
        """Explicit metadata is stored verbatim — the coercion never over-applies."""
        service, repo, _ = _make_service()
        repo.get_by_slug = AsyncMock(return_value=None)
        repo.create = AsyncMock(return_value=MagicMock(spec=KBEntry))

        data = KBEntryCreate(
            entity_type="character",
            name="John",
            metadata={"age": 30, "role": "protagonist"},
        )
        await service.create(uuid.uuid4(), uuid.uuid4(), data)

        call_args = repo.create.call_args[0][0]
        assert call_args.metadata_ == {"age": 30, "role": "protagonist"}


class TestKBServiceGet:
    async def test_get_existing_entry(self) -> None:
        service, repo, _ = _make_service()

        entry = MagicMock(spec=KBEntry)
        entry.novel_id = uuid.uuid4()
        repo.get_by_id = AsyncMock(return_value=entry)

        result = await service.get(entry.novel_id, uuid.uuid4(), uuid.uuid4())
        assert result is entry

    async def test_get_nonexistent_raises_not_found(self) -> None:
        service, repo, _ = _make_service()
        repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(NotFoundError, match="KBEntry"):
            await service.get(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())

    async def test_get_wrong_novel_raises_not_found(self) -> None:
        service, repo, _ = _make_service()

        entry = MagicMock(spec=KBEntry)
        entry.novel_id = uuid.uuid4()
        repo.get_by_id = AsyncMock(return_value=entry)

        different_novel = uuid.uuid4()
        with pytest.raises(NotFoundError, match="KBEntry"):
            await service.get(different_novel, uuid.uuid4(), uuid.uuid4())


class TestKBServiceUpdate:
    async def test_update_name_regenerates_slug(self) -> None:
        service, repo, _ = _make_service()

        entry = MagicMock(spec=KBEntry)
        entry.novel_id = uuid.uuid4()
        entry.slug = "old-name"
        repo.get_by_id = AsyncMock(return_value=entry)
        repo.get_by_slug = AsyncMock(return_value=None)
        repo.update = AsyncMock(return_value=entry)

        data = KBEntryUpdate(name="New Name")
        await service.update(entry.novel_id, uuid.uuid4(), uuid.uuid4(), data)

        update_call = repo.update.call_args[0][1]
        assert update_call["name"] == "New Name"
        assert update_call["slug"] == "new-name"

    async def test_update_duplicate_slug_raises_conflict(self) -> None:
        service, repo, _ = _make_service()

        entry = MagicMock(spec=KBEntry)
        entry.novel_id = uuid.uuid4()
        entry.slug = "old-slug"
        repo.get_by_id = AsyncMock(return_value=entry)
        repo.get_by_slug = AsyncMock(return_value=MagicMock(spec=KBEntry))

        data = KBEntryUpdate(slug="taken-slug")
        with pytest.raises(ConflictError, match="already exists"):
            await service.update(entry.novel_id, uuid.uuid4(), uuid.uuid4(), data)


class TestKBServiceDelete:
    async def test_delete_existing_entry(self) -> None:
        service, repo, _ = _make_service()

        entry = MagicMock(spec=KBEntry)
        entry.novel_id = uuid.uuid4()
        repo.get_by_id = AsyncMock(return_value=entry)
        repo.delete = AsyncMock()

        await service.delete(entry.novel_id, uuid.uuid4(), uuid.uuid4())
        repo.delete.assert_called_once_with(entry)


# Q-016 event-publishing tests live in ``test_kb_service_events.py`` (RULE-04
# file-size split). They verify KBService.update publishes kb.entry.updated to
# the in-process EventPublisher that regenerates wiki summaries.
