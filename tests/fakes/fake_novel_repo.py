"""Fake novel repository for unit tests."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from narrare.novels.models import Novel
from tests.fakes._shared import CallRecord, _apply_setattr

if TYPE_CHECKING:
    from narrare.novels.schemas import CreateNovelRequest, UpdateNovelRequest


class FakeNovelRepository:
    """
    In-memory fake for NovelRepositoryProtocol.

    Stores novels keyed by (novel_id, user_id).
    """

    def __init__(self) -> None:
        self._store: dict[tuple[uuid.UUID, uuid.UUID], Novel] = {}
        self.calls: list[CallRecord] = []

    def seed(self, *novels: Novel) -> None:
        for n in novels:
            self._store[(n.id, n.user_id)] = n

    async def get_by_id(self, novel_id: uuid.UUID, user_id: uuid.UUID) -> Novel | None:
        self.calls.append(
            CallRecord("get_by_id", kwargs={"novel_id": novel_id, "user_id": user_id})
        )
        return self._store.get((novel_id, user_id))

    async def list_by_user(self, user_id: uuid.UUID) -> list[Novel]:
        self.calls.append(CallRecord("list_by_user", kwargs={"user_id": user_id}))
        return [n for n in self._store.values() if n.user_id == user_id]

    async def create(self, user_id: uuid.UUID, request: CreateNovelRequest) -> Novel:
        self.calls.append(CallRecord("create", kwargs={"user_id": user_id}))
        novel = Novel()
        _apply_setattr(
            novel,
            {
                "id": uuid.uuid4(),
                "user_id": user_id,
                "title": request.title,
                "author": "",
                "genre": "",
                "writing_language": "en",
                "tone": "",
                "story_structure": "three_act",
                "logline": "",
                "synopsis": "",
                "is_demo": False,
            },
        )
        self._store[(novel.id, user_id)] = novel
        return novel

    async def update(self, novel: Novel, request: UpdateNovelRequest) -> Novel:
        self.calls.append(CallRecord("update"))
        updates = request.model_dump(exclude_none=True)
        _apply_setattr(novel, updates)
        return novel

    async def delete(self, novel: Novel) -> None:
        self.calls.append(CallRecord("delete"))
        self._store.pop((novel.id, novel.user_id), None)

    def call_count(self, method: str) -> int:
        return sum(1 for c in self.calls if c.method == method)

    def assert_called_once(self, method: str) -> None:
        count = self.call_count(method)
        if count != 1:
            raise AssertionError(f"Expected 1 call to {method}, got {count}")
