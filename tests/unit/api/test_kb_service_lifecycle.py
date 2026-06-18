"""Unit tests for the KBService lifecycle hook (ADR-050 P1-B).

Verifies that ``KBService.update``/``delete`` route rename / deprecate /
delete events through the injected ``KBLifecycleDispatcher``, and that
omitting the dispatcher (backward-compat) is safe.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

from narrare.kb.contracts import KBRepositoryProtocol
from narrare.kb.lifecycle_dispatcher import KBLifecycleDispatcher
from narrare.kb.models import KBEntry
from narrare.kb.schemas import KBEntryUpdate
from narrare.kb.service import KBService
from narrare.novels.contracts import NovelRepositoryProtocol
from narrare.novels.models import Novel


def _make_entry(name: str = "John", status: str = "canon") -> MagicMock:
    entry = MagicMock(spec=KBEntry)
    entry.id = uuid.uuid4()
    entry.novel_id = uuid.uuid4()
    entry.name = name
    entry.status = status
    entry.slug = "john"
    entry.entity_type = "character"
    return entry


def _make_service(
    entry: MagicMock,
    *,
    lifecycle: KBLifecycleDispatcher | None,
) -> tuple[KBService, AsyncMock]:
    repo = AsyncMock(spec=KBRepositoryProtocol)
    repo.get_by_id = AsyncMock(return_value=entry)
    repo.get_by_slug = AsyncMock(return_value=None)
    repo.update = AsyncMock(return_value=entry)
    repo.delete = AsyncMock()

    novel_repo = AsyncMock(spec=NovelRepositoryProtocol)
    novel_repo.get_by_id = AsyncMock(return_value=MagicMock(spec=Novel))

    service = KBService(repo=repo, novel_repo=novel_repo, lifecycle=lifecycle)
    return service, repo


def _spy_dispatcher() -> tuple[KBLifecycleDispatcher, AsyncMock]:
    """A real dispatcher wrapping a single AsyncMock observer.

    Using the real dispatcher (not a mock of the dispatcher) proves the
    service wires into the actual fan-out + RULE-11 isolation.
    """
    observer = AsyncMock()
    observer.consumer_feature = "spy"
    return KBLifecycleDispatcher(observers=[observer]), observer


class TestUpdateRename:
    async def test_name_change_notifies_renamed_with_old_and_new(self) -> None:
        entry = _make_entry(name="John")
        dispatcher, observer = _spy_dispatcher()
        service, repo = _make_service(entry, lifecycle=dispatcher)

        await service.update(entry.novel_id, entry.id, uuid.uuid4(), KBEntryUpdate(name="Jonathan"))

        observer.on_kb_entity_renamed.assert_awaited_once_with(
            novel_id=entry.novel_id,
            entity_id=entry.id,
            old_name="John",
            new_name="Jonathan",
        )
        repo.update.assert_awaited_once()

    async def test_name_unchanged_does_not_notify(self) -> None:
        entry = _make_entry(name="John")
        dispatcher, observer = _spy_dispatcher()
        service, _ = _make_service(entry, lifecycle=dispatcher)

        await service.update(entry.novel_id, entry.id, uuid.uuid4(), KBEntryUpdate(name="John"))

        observer.on_kb_entity_renamed.assert_not_awaited()


class TestUpdateDeprecate:
    async def test_status_to_deprecated_notifies(self) -> None:
        entry = _make_entry(status="canon")
        dispatcher, observer = _spy_dispatcher()
        service, _ = _make_service(entry, lifecycle=dispatcher)

        await service.update(
            entry.novel_id,
            entry.id,
            uuid.uuid4(),
            KBEntryUpdate(status="deprecated"),
        )

        observer.on_kb_entity_deprecated.assert_awaited_once_with(
            novel_id=entry.novel_id,
            entity_id=entry.id,
        )

    async def test_already_deprecated_no_transition_no_notify(self) -> None:
        entry = _make_entry(status="deprecated")
        dispatcher, observer = _spy_dispatcher()
        service, _ = _make_service(entry, lifecycle=dispatcher)

        await service.update(
            entry.novel_id,
            entry.id,
            uuid.uuid4(),
            KBEntryUpdate(status="deprecated"),
        )

        observer.on_kb_entity_deprecated.assert_not_awaited()

    async def test_status_to_non_deprecated_no_notify(self) -> None:
        entry = _make_entry(status="draft")
        dispatcher, observer = _spy_dispatcher()
        service, _ = _make_service(entry, lifecycle=dispatcher)

        await service.update(
            entry.novel_id,
            entry.id,
            uuid.uuid4(),
            KBEntryUpdate(status="reviewed"),
        )

        observer.on_kb_entity_deprecated.assert_not_awaited()


class TestUpdateNoLifecycle:
    async def test_without_dispatcher_does_not_error(self) -> None:
        entry = _make_entry(name="John")
        service, _ = _make_service(entry, lifecycle=None)

        # Backward-compat: no dispatcher → no notification, no error.
        result = await service.update(
            entry.novel_id,
            entry.id,
            uuid.uuid4(),
            KBEntryUpdate(name="Jonathan", status="deprecated"),
        )
        assert result is entry


class TestDelete:
    async def test_delete_notifies_deleted(self) -> None:
        entry = _make_entry()
        dispatcher, observer = _spy_dispatcher()
        service, _ = _make_service(entry, lifecycle=dispatcher)

        await service.delete(entry.novel_id, entry.id, uuid.uuid4())

        observer.on_kb_entity_deleted.assert_awaited_once_with(
            novel_id=entry.novel_id,
            entity_id=entry.id,
        )

    async def test_delete_without_dispatcher_does_not_error(self) -> None:
        entry = _make_entry()
        service, _ = _make_service(entry, lifecycle=None)
        await service.delete(entry.novel_id, entry.id, uuid.uuid4())
