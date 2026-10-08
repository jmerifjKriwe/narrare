"""Chapter service — business logic."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.chapters.repository import count_words
from narrare_core.events.types import EventType
from narrare_core.shared.errors import NotFoundError, ValidationError

if TYPE_CHECKING:
    import uuid

    from narrare.analytics.writing_stats_recorder import WritingStatsRecorder
    from narrare.chapters.contracts import ChapterRepositoryProtocol
    from narrare.chapters.models import Chapter, ChapterVersion
    from narrare.chapters.schemas import (
        CreateChapterRequest,
        UpdateChapterContentRequest,
        UpdateChapterMetaRequest,
    )
    from narrare.events.publisher import EventPublisher
    from narrare.novels.contracts import NovelServiceProtocol
    from narrare.volumes.contracts import VolumeRepositoryProtocol

logger = structlog.get_logger(__name__)


class ChapterService:
    def __init__(
        self,
        repo: ChapterRepositoryProtocol,
        novel_service: NovelServiceProtocol,
        volume_repo: VolumeRepositoryProtocol | None = None,
        event_publisher: EventPublisher | None = None,
        writing_stats_recorder: WritingStatsRecorder | None = None,
        *,
        max_content_length: int = 100_000,
    ) -> None:
        self._repo = repo
        self._novel_service = novel_service
        self._volume_repo = volume_repo
        self._event_publisher = event_publisher
        self._writing_stats_recorder = writing_stats_recorder
        self._max_content_length = max_content_length

    async def get(
        self,
        chapter_id: uuid.UUID,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Chapter:
        """Get a chapter, verifying novel ownership."""
        await self._novel_service.get(novel_id, user_id)  # ownership check
        chapter = await self._repo.get_by_id(chapter_id, novel_id)
        if not chapter:
            raise NotFoundError("Chapter", identifier=str(chapter_id))
        return chapter

    async def list_chapters(
        self, novel_id: uuid.UUID, user_id: uuid.UUID, volume_id: uuid.UUID | None = None
    ) -> list[Chapter]:
        await self._novel_service.get(novel_id, user_id)
        return await self._repo.list_by_novel(novel_id, volume_id=volume_id)

    async def create(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        request: CreateChapterRequest,
    ) -> Chapter:
        await self._novel_service.get(novel_id, user_id)
        position = request.position
        if position is None:
            position = (await self._repo.max_position(novel_id)) + 1

        # Resolve volume_id: use request or fall back to novel's default volume
        volume_id = request.volume_id
        if volume_id is None and self._volume_repo is not None:
            default_volume = await self._volume_repo.get_default_volume(novel_id)
            if default_volume is not None:
                volume_id = default_volume.id

        chapter = await self._repo.create(novel_id, request, position, volume_id=volume_id)

        # STATS-001 (ADR-095): create-with-content is a real write — the freshly
        # computed word_count IS the signed delta. Empty creates arrive as 0 and
        # are skipped inside the recorder (zero-skip), never here; same
        # never-raises posture as the other surfaces — no try/except at call sites.
        if self._writing_stats_recorder is not None:
            await self._writing_stats_recorder.record_delta(
                user_id=user_id,
                novel_id=novel_id,
                chapter_id=chapter.id,
                delta_words=chapter.word_count,
            )

        logger.info("chapter_created", chapter_id=str(chapter.id), novel_id=str(novel_id))
        return chapter

    async def update_content(
        self,
        chapter_id: uuid.UUID,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        request: UpdateChapterContentRequest,
    ) -> Chapter:
        if len(request.content) > self._max_content_length:
            raise ValidationError(
                f"Chapter content exceeds {self._max_content_length:,} character limit"
            )
        chapter = await self.get(chapter_id, novel_id, user_id)
        word_count = request.word_count or count_words(request.content)
        # Capture BEFORE the repo write — repositories update the chapter row
        # in place, so the old word count is unrecoverable afterwards.
        old_word_count = chapter.word_count

        # Save current content as version BEFORE updating
        latest = await self._repo.get_latest_version_number(chapter_id)
        await self._repo.save_version(chapter, latest + 1, source="autosave")

        updated = await self._repo.update_content(chapter, request.content, word_count)

        # Prune old versions (keep last 50)
        await self._repo.prune_versions(chapter_id, keep=50)

        # STATS-001 (ADR-095): signed word-count delta for this editor write.
        # The recorder is never-raises and skips zero deltas internally — no
        # try/except here by contract.
        if self._writing_stats_recorder is not None:
            await self._writing_stats_recorder.record_delta(
                user_id=user_id,
                novel_id=novel_id,
                chapter_id=chapter_id,
                delta_words=word_count - old_word_count,
            )

        logger.debug("chapter_content_updated", chapter_id=str(chapter_id), words=word_count)

        return updated

    async def update_meta(
        self,
        chapter_id: uuid.UUID,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        request: UpdateChapterMetaRequest,
    ) -> Chapter:
        chapter = await self.get(chapter_id, novel_id, user_id)
        # Snapshot status BEFORE the repo mutates the chapter (some repos
        # update in place) so the →final transition is detected correctly.
        previous_status = chapter.status
        updated = await self._repo.update_meta(chapter, request)

        # Q-016: publish chapter.finalized only on the transition INTO "final"
        # (not on every status write, not when already final). In-process
        # (ADR-080); non-blocking + logged (RULE-11).
        if (
            self._event_publisher is not None
            and request.status == "final"
            and previous_status != "final"
        ):
            try:
                await self._event_publisher.publish(
                    EventType.CHAPTER_FINALIZED,
                    aggregate_id=chapter_id,
                    payload={"chapter_id": str(chapter_id), "novel_id": str(novel_id)},
                )
            except Exception:
                logger.warning(
                    "chapter_finalized_publish_failed",
                    chapter_id=str(chapter_id),
                    novel_id=str(novel_id),
                    exc_info=True,
                )

        return updated

    async def reorder(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        chapter_ids: list[uuid.UUID],
    ) -> list[Chapter]:
        await self._novel_service.get(novel_id, user_id)
        chapters = await self._repo.reorder(novel_id, chapter_ids)
        logger.info("chapters_reordered", novel_id=str(novel_id), count=len(chapters))
        return chapters

    async def delete(
        self,
        chapter_id: uuid.UUID,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        chapter = await self.get(chapter_id, novel_id, user_id)
        # Capture BEFORE the delete — the row is gone afterwards.
        deleted_word_count = chapter.word_count
        await self._repo.delete(chapter)

        # STATS-001 (ADR-095): deletes are honest negative deltas (net-words).
        if self._writing_stats_recorder is not None:
            await self._writing_stats_recorder.record_delta(
                user_id=user_id,
                novel_id=novel_id,
                chapter_id=chapter_id,
                delta_words=-deleted_word_count,
            )

        logger.info("chapter_deleted", chapter_id=str(chapter_id))

    # -- Version methods --

    async def list_versions(
        self,
        chapter_id: uuid.UUID,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> list[ChapterVersion]:
        """List all versions of a chapter, newest first."""
        await self.get(chapter_id, novel_id, user_id)  # ownership check
        return await self._repo.list_versions(chapter_id)

    async def restore_version(
        self,
        chapter_id: uuid.UUID,
        version_id: uuid.UUID,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Chapter:
        """Restore a chapter to a previous version."""
        chapter = await self.get(chapter_id, novel_id, user_id)
        version = await self._repo.get_version(version_id, chapter_id)
        if not version:
            raise NotFoundError("Version", identifier=str(version_id))

        # Save current content as version before restoring
        latest = await self._repo.get_latest_version_number(chapter_id)
        await self._repo.save_version(chapter, latest + 1, source="manual")

        # Capture BEFORE the restore — the repo write overwrites the row in place.
        current_word_count = chapter.word_count

        # Restore content from version
        restored = await self._repo.update_content(chapter, version.content, version.word_count)

        # STATS-001 (ADR-095): restore = signed delta (0 when content is
        # identical — the recorder skips it internally, no guard here).
        if self._writing_stats_recorder is not None:
            await self._writing_stats_recorder.record_delta(
                user_id=user_id,
                novel_id=novel_id,
                chapter_id=chapter_id,
                delta_words=restored.word_count - current_word_count,
            )

        logger.info(
            "chapter_version_restored",
            chapter_id=str(chapter_id),
            version_id=str(version_id),
        )
        return restored
