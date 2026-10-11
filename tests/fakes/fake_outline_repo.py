"""Fake outline repository for unit tests."""

from __future__ import annotations

import uuid

from narrare.planning.models import ChapterOutline
from tests.fakes._shared import CallRecord, _apply_setattr


class FakeOutlineRepository:
    """In-memory fake for OutlineRepositoryProtocol."""

    def __init__(self) -> None:
        self._store: dict[uuid.UUID, ChapterOutline] = {}
        self.calls: list[CallRecord] = []

    def seed(self, *outlines: ChapterOutline) -> None:
        """Pre-populate with outlines. Keyed by chapter_id."""
        for o in outlines:
            self._store[o.chapter_id] = o

    async def get_by_chapter_id(self, chapter_id: uuid.UUID) -> ChapterOutline | None:
        self.calls.append(CallRecord("get_by_chapter_id", kwargs={"chapter_id": chapter_id}))
        return self._store.get(chapter_id)

    async def get_all_for_novel(self, novel_id: uuid.UUID) -> list[ChapterOutline]:
        self.calls.append(CallRecord("get_all_for_novel", kwargs={"novel_id": novel_id}))
        return list(self._store.values())

    async def create(
        self,
        chapter_id: uuid.UUID,
        stage_assignment: str,
        outline_notes: str = "",
    ) -> ChapterOutline:
        self.calls.append(
            CallRecord(
                "create",
                kwargs={
                    "chapter_id": chapter_id,
                    "stage_assignment": stage_assignment,
                    "outline_notes": outline_notes,
                },
            )
        )
        outline = ChapterOutline()
        from datetime import UTC, datetime

        _apply_setattr(
            outline,
            {
                "id": uuid.uuid4(),
                "chapter_id": chapter_id,
                "stage_assignment": stage_assignment,
                "outline_notes": outline_notes,
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
            },
        )
        self._store[chapter_id] = outline
        return outline

    async def update(self, chapter_id: uuid.UUID, **fields: object) -> ChapterOutline:
        self.calls.append(CallRecord("update", kwargs={"chapter_id": chapter_id, **fields}))
        outline = self._store.get(chapter_id)
        if outline is None:
            from narrare_core.shared.errors import NotFoundError

            raise NotFoundError("ChapterOutline", identifier=str(chapter_id))
        _apply_setattr(outline, fields)
        return outline

    def call_count(self, method: str) -> int:
        return sum(1 for c in self.calls if c.method == method)

    def assert_called_once(self, method: str) -> None:
        count = self.call_count(method)
        if count != 1:
            raise AssertionError(f"Expected 1 call to {method}, got {count}")
