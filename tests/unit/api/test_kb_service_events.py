"""KBService event-publishing tests (Q-016 — wiki staleness gap).

Extracted from ``test_kb_service.py`` per RULE-04 (file-size limit). Proves
``KBService.update`` publishes ``kb.entry.updated`` to its injected in-process
``EventPublisher`` so the ``WikiEventListener`` regenerates the entity's wiki
summary — closing the silent staleness gap (ADR-080 / WIKI-001).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

from narrare.kb.contracts import KBRepositoryProtocol
from narrare.kb.models import KBEntry
from narrare.kb.schemas import KBEntryUpdate
from narrare.kb.service import KBService
from narrare.novels.contracts import NovelRepositoryProtocol
from narrare.novels.models import Novel
from narrare_core.events.types import DomainEvent, EventType

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


def _make_service_with_publisher(
    publisher: object,
) -> tuple[KBService, AsyncMock, AsyncMock]:
    """Create a KBService wired to ``publisher`` with mock repos."""
    repo = AsyncMock(spec=KBRepositoryProtocol)
    novel_repo = AsyncMock(spec=NovelRepositoryProtocol)
    novel = MagicMock(spec=Novel)
    novel_repo.get_by_id = AsyncMock(return_value=novel)
    service = KBService(
        repo=repo,
        novel_repo=novel_repo,
        event_publisher=publisher,  # type: ignore[arg-type]
    )
    return service, repo, novel_repo


def _seed_entry(novel_id: uuid.UUID) -> MagicMock:
    entry = MagicMock(spec=KBEntry)
    entry.id = uuid.uuid4()
    entry.novel_id = novel_id
    entry.name = "Old"
    entry.status = "active"
    entry.slug = "old"
    return entry


def _recorder() -> tuple[list[DomainEvent], Callable[[DomainEvent], Awaitable[None]]]:
    """Return ``(received_list, handler)`` — an async handler recording events."""
    received: list[DomainEvent] = []

    async def _record(event: DomainEvent) -> None:
        received.append(event)

    return received, _record


class TestKBServiceEventPublishing:
    """KBService.update publishes ``kb.entry.updated`` to its injected publisher."""

    async def test_update_publishes_kb_entry_updated(self) -> None:
        from narrare.events.publisher import EventPublisher

        publisher = EventPublisher()
        received, handler = _recorder()
        publisher.subscribe("kb.entry.updated", handler)

        service, repo, _ = _make_service_with_publisher(publisher)

        novel_id = uuid.uuid4()
        entry = _seed_entry(novel_id)
        repo.get_by_id = AsyncMock(return_value=entry)
        repo.get_by_slug = AsyncMock(return_value=None)
        repo.update = AsyncMock(return_value=entry)

        await service.update(novel_id, entry.id, uuid.uuid4(), KBEntryUpdate(name="New"))

        assert len(received) == 1
        event = received[0]
        assert event.event_type == EventType.KB_ENTRY_UPDATED
        assert event.payload["entity_id"] == str(entry.id)
        assert event.payload["novel_id"] == str(novel_id)

    async def test_update_without_publisher_does_not_raise(self) -> None:
        """Graceful degradation: no publisher wired → update still succeeds."""
        repo = AsyncMock(spec=KBRepositoryProtocol)
        novel_repo = AsyncMock(spec=NovelRepositoryProtocol)
        novel_repo.get_by_id = AsyncMock(return_value=MagicMock(spec=Novel))
        service = KBService(repo=repo, novel_repo=novel_repo)  # no publisher

        entry = _seed_entry(uuid.uuid4())
        repo.get_by_id = AsyncMock(return_value=entry)
        repo.get_by_slug = AsyncMock(return_value=None)
        repo.update = AsyncMock(return_value=entry)

        # Must not raise even though no publisher is present.
        await service.update(entry.novel_id, entry.id, uuid.uuid4(), KBEntryUpdate(name="New"))

    async def test_publish_failure_does_not_abort_save(self) -> None:
        """RULE-11: a publish error is logged, never blocks the user's save."""
        from narrare.events.publisher import EventPublisher

        publisher = EventPublisher()

        async def _failing(event: DomainEvent) -> None:
            raise RuntimeError("dispatch blew up")

        publisher.subscribe("kb.entry.updated", _failing)
        service, repo, _ = _make_service_with_publisher(publisher)

        entry = _seed_entry(uuid.uuid4())
        repo.get_by_id = AsyncMock(return_value=entry)
        repo.get_by_slug = AsyncMock(return_value=None)
        repo.update = AsyncMock(return_value=entry)

        # The dispatch error is swallowed inside _dispatch; save must succeed.
        result = await service.update(
            entry.novel_id, entry.id, uuid.uuid4(), KBEntryUpdate(name="New")
        )
        assert result is entry
