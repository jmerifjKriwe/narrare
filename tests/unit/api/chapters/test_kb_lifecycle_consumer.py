"""Regression tests for chapter-frontmatter KB lifecycle handling.

ADR-050 P1-B requires chapter frontmatter to surface stale/dangling KB
references without rewriting user-authored chapter content.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from collections.abc import Sequence

from narrare.chapters.kb_lifecycle_consumer import ChapterFrontmatterRefConsumerImpl
from narrare.chapters.models import Chapter
from narrare.consistency.ref_integrity_sink import InMemoryRefIntegrityIssueSink
from narrare_core.context.integration_contracts import (
    ChapterFrontmatterRefConsumer,
    KBEntityLifecycleObserver,
)


class _FakeChapterRepo:
    def __init__(self) -> None:
        self.chapters: list[Chapter] = []

    def seed(self, chapter: Chapter) -> None:
        self.chapters.append(chapter)

    async def list_by_novel(
        self,
        novel_id: UUID,
        volume_id: UUID | None = None,
    ) -> Sequence[Chapter]:
        del novel_id, volume_id
        return list(self.chapters)


def _chapter(*, content: str, pov_character_id: str = "") -> Chapter:
    return Chapter(
        id=uuid4(),
        novel_id=uuid4(),
        content=content,
        pov_character_id=pov_character_id,
    )


class TestChapterFrontmatterProtocol:
    def test_satisfies_core_protocols(self) -> None:
        consumer = ChapterFrontmatterRefConsumerImpl(
            chapter_repo=_FakeChapterRepo(),
            issue_sink=InMemoryRefIntegrityIssueSink(),
        )

        assert isinstance(consumer, KBEntityLifecycleObserver)
        assert isinstance(consumer, ChapterFrontmatterRefConsumer)
        assert consumer.consumer_feature == "chapter_frontmatter"


class TestChapterFrontmatterRename:
    async def test_rename_emits_issue_without_rewriting_frontmatter(self) -> None:
        sink = InMemoryRefIntegrityIssueSink()
        repo = _FakeChapterRepo()
        original = "---\npov_character: John\nlocation: Castle\n---\nBody mentions John."
        chapter = _chapter(content=original)
        repo.seed(chapter)
        consumer = ChapterFrontmatterRefConsumerImpl(repo, sink)

        await consumer.on_kb_entity_renamed(
            novel_id=chapter.novel_id,
            entity_id=uuid4(),
            old_name="John",
            new_name="Jonathan",
        )

        assert chapter.content == original
        assert len(sink.issues) == 1
        issue = sink.issues[0]
        assert issue.consumer_feature == "chapter_frontmatter"
        assert issue.reason == "stale_name_ref"
        assert issue.ref_kind == "name"
        assert issue.ref_value == "John"


class TestChapterFrontmatterDelete:
    async def test_delete_emits_issue_for_id_ref_without_tombstone_column(self) -> None:
        entity_id = uuid4()
        sink = InMemoryRefIntegrityIssueSink()
        repo = _FakeChapterRepo()
        original = f"---\ncharacters:\n  - {entity_id}\n---\nBody."
        chapter = _chapter(content=original, pov_character_id=str(entity_id))
        repo.seed(chapter)
        consumer = ChapterFrontmatterRefConsumerImpl(repo, sink)

        await consumer.on_kb_entity_deleted(novel_id=chapter.novel_id, entity_id=entity_id)

        assert chapter.content == original
        assert len(sink.issues) == 2
        assert all(issue.reason == "deleted_ref_without_tombstone" for issue in sink.issues)
        assert all(issue.resolved_status == "deleted" for issue in sink.issues)


class TestChapterFrontmatterDeprecate:
    async def test_deprecate_emits_warning_for_id_ref_without_rewriting(self) -> None:
        entity_id = uuid4()
        sink = InMemoryRefIntegrityIssueSink()
        repo = _FakeChapterRepo()
        original = f"---\nlocation: {entity_id}\n---\nBody."
        chapter = _chapter(content=original)
        repo.seed(chapter)
        consumer = ChapterFrontmatterRefConsumerImpl(repo, sink)

        await consumer.on_kb_entity_deprecated(novel_id=chapter.novel_id, entity_id=entity_id)

        assert chapter.content == original
        assert len(sink.issues) == 1
        assert sink.issues[0].reason == "deprecated_ref_in_active_context"
