"""Chapter service — business logic."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.chapters.repository import count_words
from narrare_core.shared.errors import NotFoundError, ValidationError

if TYPE_CHECKING:
    import uuid

    from narrare.chapters.contracts import ChapterRepositoryProtocol
    from narrare.chapters.models import Chapter, ChapterVersion
    from narrare.chapters.schemas import (
        CreateChapterRequest,
        UpdateChapterContentRequest,
        UpdateChapterMetaRequest,
    )
    from narrare.novels.contracts import NovelServiceProtocol
    from narrare.volumes.contracts import VolumeRepositoryProtocol

logger = structlog.get_logger(__name__)


class ChapterService:
    def __init__(
        self,
        repo: ChapterRepositoryProtocol,
        novel_service: NovelServiceProtocol,
        volume_repo: VolumeRepositoryProtocol | None = None,
        *,
        max_content_length: int = 100_000,
    ) -> None:
        self._repo = repo
        self._novel_service = novel_service
        self._volume_repo = volume_repo
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

        # Save current content as version BEFORE updating
        latest = await self._repo.get_latest_version_number(chapter_id)
        await self._repo.save_version(chapter, latest + 1, source="autosave")

        updated = await self._repo.update_content(chapter, request.content, word_count)

        # Prune old versions (keep last 50)
        await self._repo.prune_versions(chapter_id, keep=50)

        logger.debug("chapter_content_updated", chapter_id=str(chapter_id), words=word_count)

        # Publish event — never blocks or fails the main operation
        await self._publish_content_event(chapter_id, novel_id, user_id, word_count)

        return updated

    async def update_meta(
        self,
        chapter_id: uuid.UUID,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        request: UpdateChapterMetaRequest,
    ) -> Chapter:
        chapter = await self.get(chapter_id, novel_id, user_id)
        return await self._repo.update_meta(chapter, request)

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
        await self._repo.delete(chapter)
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

        # Restore content from version
        restored = await self._repo.update_content(chapter, version.content, version.word_count)
        logger.info(
            "chapter_version_restored",
            chapter_id=str(chapter_id),
            version_id=str(version_id),
        )
        return restored

    # -- Event helpers --

    async def _publish_content_event(
        self,
        chapter_id: uuid.UUID,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        word_count: int,
    ) -> None:
        """Publish a CHAPTER_CONTENT_UPDATED event.

        Wrapped in try/except so event publishing never blocks or fails
        the main operation (RULE-11: no silent failures — errors are logged).
        """
        try:
            from narrare._app.events import get_event_bus
            from narrare_core.events.types import DomainEvent, EventType

            bus = get_event_bus()
            await bus.publish(
                DomainEvent(
                    event_type=EventType.CHAPTER_CONTENT_UPDATED,
                    aggregate_id=chapter_id,
                    payload={"novel_id": str(novel_id), "word_count": word_count},
                    user_id=user_id,
                )
            )
        except RuntimeError:
            # Bus not initialized — graceful degradation
            logger.debug("event_bus_not_available", chapter_id=str(chapter_id))
        except Exception:
            logger.debug("event_publish_failed_chapter_update", exc_info=True)
