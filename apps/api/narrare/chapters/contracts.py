"""Chapter service contracts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import uuid

    from narrare.chapters.models import Chapter
    from narrare.chapters.schemas import (
        CreateChapterRequest,
        UpdateChapterContentRequest,
        UpdateChapterMetaRequest,
    )


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
