"""Unit tests for ChapterService — create, update_meta, reorder, delete."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import pytest
from structlog.testing import capture_logs

from narrare.chapters.schemas import (
    CreateChapterRequest,
    UpdateChapterMetaRequest,
)
from narrare.chapters.service import ChapterService
from narrare.events.publisher import EventPublisher
from narrare_core.shared.errors import NotFoundError
from tests.factories import make_chapter, make_novel
from tests.fakes import FakeChapterRepository, FakeNovelService

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.events.types import DomainEvent, EventType


@pytest.fixture
def fake_repo() -> FakeChapterRepository:
    return FakeChapterRepository()


@pytest.fixture
def fake_novel_service() -> FakeNovelService:
    return FakeNovelService()


@pytest.fixture
def service(
    fake_repo: FakeChapterRepository, fake_novel_service: FakeNovelService
) -> ChapterService:
    return ChapterService(repo=fake_repo, novel_service=fake_novel_service)


def _seed_ownership(
    fake_novel_service: FakeNovelService,
    novel_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Seed a novel into the fake novel service for ownership checks."""
    novel_id = novel_id or uuid.uuid4()
    user_id = user_id or uuid.uuid4()
    novel = make_novel(id=novel_id, user_id=user_id)
    fake_novel_service.seed(novel)
    return novel_id, user_id


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


class TestChapterServiceCreate:
    async def test_create_with_explicit_position(
        self,
        service: ChapterService,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = _seed_ownership(fake_novel_service)

        request = CreateChapterRequest(title="New Chapter", content="hello", position=5)
        result = await service.create(novel_id, user_id, request)

        assert result.title == "New Chapter"
        assert result.position == 5
        fake_repo.assert_called_once("create")

    async def test_create_appends_at_end_when_no_position(
        self,
        service: ChapterService,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = _seed_ownership(fake_novel_service)
        existing = make_chapter(novel_id=novel_id, position=2)
        fake_repo.seed(existing)

        request = CreateChapterRequest(title="Appended", content="text")
        result = await service.create(novel_id, user_id, request)

        assert result.position == 3  # max_position(2) + 1


# ---------------------------------------------------------------------------
# update_meta
# ---------------------------------------------------------------------------


class TestChapterServiceUpdateMeta:
    async def test_update_meta_modifies_chapter(
        self,
        service: ChapterService,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = _seed_ownership(fake_novel_service)
        chapter = make_chapter(novel_id=novel_id, title="Old Title")
        fake_repo.seed(chapter)

        import uuid as _uuid

        UpdateChapterMetaRequest.model_rebuild(_types_namespace={"uuid": _uuid})

        result = await service.update_meta(
            chapter.id,
            novel_id,
            user_id,
            UpdateChapterMetaRequest(title="New Title"),
        )
        assert result.title == "New Title"


# ---------------------------------------------------------------------------
# update_meta → chapter.finalized event (Q-016 — wiki staleness gap)
# ---------------------------------------------------------------------------


class _PublishFailingPublisher(EventPublisher):
    """Real EventPublisher whose publish() raises.

    The service's failure branch (RULE-11: non-blocking + logged) wraps
    the publish() call itself. EventPublisher._dispatch already swallows
    handler exceptions, so a failing subscriber can never reach that
    branch — only a publish() that raises exercises it.
    """

    async def publish(
        self,
        event_type: EventType,
        *,
        aggregate_id: UUID,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Raise instead of dispatching."""
        msg = "simulated publisher failure"
        raise RuntimeError(msg)


class TestChapterServiceEventPublishing:
    """``chapter.finalized`` fires only on the status → ``final`` transition."""

    @staticmethod
    def _service_with_publisher(
        fake_repo: FakeChapterRepository, fake_novel_service: FakeNovelService
    ) -> tuple[ChapterService, list[object]]:
        from narrare.events.publisher import EventPublisher

        publisher = EventPublisher()
        received: list[object] = []

        async def _record(event: DomainEvent) -> None:
            received.append(event)

        publisher.subscribe("chapter.finalized", _record)
        service = ChapterService(
            repo=fake_repo, novel_service=fake_novel_service, event_publisher=publisher
        )
        return service, received

    async def test_transition_to_final_publishes_chapter_finalized(
        self,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        service, received = self._service_with_publisher(fake_repo, fake_novel_service)
        novel_id, user_id = _seed_ownership(fake_novel_service)
        chapter = make_chapter(novel_id=novel_id, status="draft")
        fake_repo.seed(chapter)

        await service.update_meta(
            chapter.id, novel_id, user_id, UpdateChapterMetaRequest(status="final")
        )

        from narrare_core.events.types import EventType

        assert len(received) == 1
        event = received[0]
        assert event.event_type == EventType.CHAPTER_FINALIZED  # type: ignore[attr-defined]
        assert event.payload["chapter_id"] == str(chapter.id)  # type: ignore[attr-defined]
        assert event.payload["novel_id"] == str(novel_id)  # type: ignore[attr-defined]

    async def test_title_only_does_not_publish(
        self,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        service, received = self._service_with_publisher(fake_repo, fake_novel_service)
        novel_id, user_id = _seed_ownership(fake_novel_service)
        chapter = make_chapter(novel_id=novel_id, status="draft")
        fake_repo.seed(chapter)

        await service.update_meta(
            chapter.id, novel_id, user_id, UpdateChapterMetaRequest(title="Renamed")
        )
        assert received == []

    async def test_non_final_status_does_not_publish(
        self,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        service, received = self._service_with_publisher(fake_repo, fake_novel_service)
        novel_id, user_id = _seed_ownership(fake_novel_service)
        chapter = make_chapter(novel_id=novel_id, status="draft")
        fake_repo.seed(chapter)

        await service.update_meta(
            chapter.id, novel_id, user_id, UpdateChapterMetaRequest(status="reviewed")
        )
        assert received == []

    async def test_already_final_re_finalized_does_not_double_publish(
        self,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        """Re-saving status=final on an already-final chapter is not a transition."""
        service, received = self._service_with_publisher(fake_repo, fake_novel_service)
        novel_id, user_id = _seed_ownership(fake_novel_service)
        chapter = make_chapter(novel_id=novel_id, status="final")
        fake_repo.seed(chapter)

        await service.update_meta(
            chapter.id, novel_id, user_id, UpdateChapterMetaRequest(status="final")
        )
        assert received == []

    async def test_no_publisher_does_not_raise(
        self,
        service: ChapterService,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        """Graceful degradation: no publisher wired → update still succeeds."""
        novel_id, user_id = _seed_ownership(fake_novel_service)
        chapter = make_chapter(novel_id=novel_id, status="draft")
        fake_repo.seed(chapter)

        await service.update_meta(
            chapter.id, novel_id, user_id, UpdateChapterMetaRequest(status="final")
        )

    async def test_publish_failure_is_logged_and_does_not_block_update(
        self,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        """A raising publisher is logged (RULE-11) and never aborts update_meta."""
        service = ChapterService(
            repo=fake_repo,
            novel_service=fake_novel_service,
            event_publisher=_PublishFailingPublisher(),
        )
        novel_id, user_id = _seed_ownership(fake_novel_service)
        chapter = make_chapter(novel_id=novel_id, status="draft")
        fake_repo.seed(chapter)

        with capture_logs() as logs:
            result = await service.update_meta(
                chapter.id, novel_id, user_id, UpdateChapterMetaRequest(status="final")
            )

        assert result.status == "final"
        matching = [log for log in logs if log.get("event") == "chapter_finalized_publish_failed"]
        assert len(matching) == 1
        assert matching[0]["chapter_id"] == str(chapter.id)
        assert matching[0]["novel_id"] == str(novel_id)


# ---------------------------------------------------------------------------
# reorder
# ---------------------------------------------------------------------------


class TestChapterServiceReorder:
    async def test_reorder_calls_repo(
        self,
        service: ChapterService,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = _seed_ownership(fake_novel_service)
        ch1 = make_chapter(novel_id=novel_id)
        ch2 = make_chapter(novel_id=novel_id)
        fake_repo.seed(ch1, ch2)

        result = await service.reorder(novel_id, user_id, [ch1.id, ch2.id])
        assert len(result) == 2


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


class TestChapterServiceDelete:
    async def test_delete_removes_chapter(
        self,
        service: ChapterService,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = _seed_ownership(fake_novel_service)
        chapter = make_chapter(novel_id=novel_id)
        fake_repo.seed(chapter)

        await service.delete(chapter.id, novel_id, user_id)
        fake_repo.assert_called_once("delete")

    async def test_delete_raises_404_when_not_found(
        self, service: ChapterService, fake_novel_service: FakeNovelService
    ) -> None:
        novel_id, user_id = _seed_ownership(fake_novel_service)

        with pytest.raises(NotFoundError):
            await service.delete(uuid.uuid4(), novel_id, user_id)


# ---------------------------------------------------------------------------
# Model __repr__ coverage
# ---------------------------------------------------------------------------


class TestChapterModelRepr:
    def test_chapter_repr_includes_title_and_position(self) -> None:
        from tests.factories import make_chapter as _make_chapter

        chapter = _make_chapter(title="My Chapter", position=3)
        result = repr(chapter)
        assert "Chapter" in result
        assert "My Chapter" in result
        assert "position=3" in result

    def test_chapter_version_repr_includes_version_and_source(self) -> None:
        import uuid as _uuid

        from sqlalchemy.orm.attributes import set_attribute

        from narrare.chapters.models import ChapterVersion

        version = ChapterVersion()
        for k, v in {
            "id": _uuid.uuid4(),
            "chapter_id": _uuid.uuid4(),
            "content": "test",
            "word_count": 1,
            "version_number": 5,
            "source": "manual",
        }.items():
            set_attribute(version, k, v)

        result = repr(version)
        assert "ChapterVersion" in result
        assert "version=5" in result
        assert "manual" in result
