"""
Fake service implementations for unit tests.

These Fakes are used when a test needs a service as a *dependency* of the SUT.
For example, ChapterService depends on NovelService for ownership checks.

Usage:
    fake_novel_service = FakeNovelService()
    fake_novel_service.seed(make_novel(id=novel_id, user_id=user_id))
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException, status

from narrare.novels.models import Novel

if TYPE_CHECKING:
    from narrare.novels.schemas import CreateNovelRequest, UpdateNovelRequest


class FakeNovelService:
    """
    In-memory fake for NovelServiceProtocol.

    Supports ownership checks (get) and basic CRUD.
    """

    def __init__(self) -> None:
        self._store: dict[tuple[uuid.UUID, uuid.UUID], Novel] = {}
        self.calls: list[dict[str, Any]] = []

    def seed(self, *novels: Novel) -> None:
        """Pre-populate with novels. Keyed by (novel_id, user_id)."""
        for n in novels:
            self._store[(n.id, n.user_id)] = n

    async def get(self, novel_id: uuid.UUID, user_id: uuid.UUID) -> Novel:
        """Get a novel, raising 404 if not found or not owned by user."""
        self.calls.append({"method": "get", "novel_id": novel_id, "user_id": user_id})
        novel = self._store.get((novel_id, user_id))
        if not novel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Novel not found",
            )
        return novel

    async def list_novels(self, user_id: uuid.UUID) -> list[Novel]:
        self.calls.append({"method": "list_novels", "user_id": user_id})
        return [n for n in self._store.values() if n.user_id == user_id]

    async def create(self, user_id: uuid.UUID, request: CreateNovelRequest) -> Novel:
        self.calls.append({"method": "create", "user_id": user_id})
        novel = Novel()
        from tests.fakes.fake_repositories import _apply_setattr

        _apply_setattr(
            novel,
            {
                "id": uuid.uuid4(),
                "user_id": user_id,
                "title": request.title,
                "author": "",
                "genre": "",
                "language": "en",
                "tone": "",
                "story_structure": "three_act",
                "logline": "",
                "synopsis": "",
                "is_demo": False,
            },
        )
        self._store[(novel.id, user_id)] = novel
        return novel

    async def update(
        self, novel_id: uuid.UUID, user_id: uuid.UUID, request: UpdateNovelRequest
    ) -> Novel:
        self.calls.append({"method": "update", "novel_id": novel_id})
        novel = await self.get(novel_id, user_id)
        updates = request.model_dump(exclude_none=True)
        from tests.fakes.fake_repositories import _apply_setattr

        _apply_setattr(novel, updates)
        return novel

    async def delete(self, novel_id: uuid.UUID, user_id: uuid.UUID) -> None:
        self.calls.append({"method": "delete", "novel_id": novel_id})
        await self.get(novel_id, user_id)  # ownership check
        self._store.pop((novel_id, user_id), None)
