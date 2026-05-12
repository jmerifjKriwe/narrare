"""Chapter service contracts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid

    from narrare.chapters.models import Chapter, ChapterVersion
    from narrare.chapters.schemas import (
        CreateChapterRequest,
        UpdateChapterContentRequest,
        UpdateChapterMetaRequest,
    )


@runtime_checkable
class ChapterRepositoryProtocol(Protocol):
    async def get_by_id(self, chapter_id: uuid.UUID, novel_id: uuid.UUID) -> Chapter | None: ...
    async def list_by_novel(self, novel_id: uuid.UUID) -> list[Chapter]: ...
    async def create(
        self, novel_id: uuid.UUID, request: CreateChapterRequest, position: int
    ) -> Chapter: ...
    async def update_content(self, chapter: Chapter, content: str, word_count: int) -> Chapter: ...
    async def update_meta(self, chapter: Chapter, request: UpdateChapterMetaRequest) -> Chapter: ...
    async def reorder(self, novel_id: uuid.UUID, chapter_ids: list[uuid.UUID]) -> list[Chapter]: ...
    async def delete(self, chapter: Chapter) -> None: ...
    async def max_position(self, novel_id: uuid.UUID) -> int: ...
    async def save_version(
        self, chapter: Chapter, version_number: int, source: str = "autosave"
    ) -> ChapterVersion: ...
    async def get_latest_version_number(self, chapter_id: uuid.UUID) -> int: ...
    async def list_versions(
        self, chapter_id: uuid.UUID, limit: int = 50
    ) -> list[ChapterVersion]: ...
    async def get_version(
        self, version_id: uuid.UUID, chapter_id: uuid.UUID
    ) -> ChapterVersion | None: ...
    async def prune_versions(self, chapter_id: uuid.UUID, keep: int = 50) -> int: ...


@runtime_checkable
class ChapterServiceProtocol(Protocol):
    async def get(
        self, chapter_id: uuid.UUID, novel_id: uuid.UUID, user_id: uuid.UUID
    ) -> Chapter: ...
    async def list_chapters(self, novel_id: uuid.UUID, user_id: uuid.UUID) -> list[Chapter]: ...
    async def create(
        self, novel_id: uuid.UUID, user_id: uuid.UUID, request: CreateChapterRequest
    ) -> Chapter: ...
    async def update_content(
        self,
        chapter_id: uuid.UUID,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        request: UpdateChapterContentRequest,
    ) -> Chapter: ...
    async def update_meta(
        self,
        chapter_id: uuid.UUID,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        request: UpdateChapterMetaRequest,
    ) -> Chapter: ...
    async def reorder(
        self, novel_id: uuid.UUID, user_id: uuid.UUID, chapter_ids: list[uuid.UUID]
    ) -> list[Chapter]: ...
    async def delete(
        self, chapter_id: uuid.UUID, novel_id: uuid.UUID, user_id: uuid.UUID
    ) -> None: ...
    async def list_versions(
        self, chapter_id: uuid.UUID, novel_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[ChapterVersion]: ...
    async def restore_version(
        self,
        chapter_id: uuid.UUID,
        version_id: uuid.UUID,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Chapter: ...
