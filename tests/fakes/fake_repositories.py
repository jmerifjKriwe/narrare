"""
Fake repository implementations for unit tests.

Each Fake implements the corresponding Protocol from contracts.py.
Uses in-memory storage (dicts) instead of a database.

Usage:
    fake_repo = FakeChapterRepository()
    fake_repo.seed(make_chapter(id=uuid4(), novel_id=novel_id))
    result = await fake_repo.get_by_id(chapter_id, novel_id)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from narrare.auth.models import User
from narrare.chapters.models import Chapter
from narrare.novels.models import Novel
from narrare.volumes.models import Volume

if TYPE_CHECKING:
    from narrare.chapters.schemas import CreateChapterRequest, UpdateChapterMetaRequest
    from narrare.novels.schemas import CreateNovelRequest, UpdateNovelRequest
    from narrare.volumes.schemas import UpdateVolumeRequest


@dataclass
class CallRecord:
    """Record of a single method call on a Fake."""

    method: str
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)

    def matches(self, expected_kwargs: dict[str, Any]) -> bool:
        """Check if this call's kwargs contain all expected key-value pairs."""
        return all(self.kwargs.get(k) == v for k, v in expected_kwargs.items())


# ======================================================================
# Shared helper
# ======================================================================


def _apply_setattr(obj: Any, updates: dict[str, Any]) -> None:
    """Set attributes on a SQLAlchemy model instance."""
    from sqlalchemy.orm.attributes import set_attribute

    for key, value in updates.items():
        set_attribute(obj, key, value)


# ======================================================================
# FakeChapterRepository
# ======================================================================


class FakeChapterRepository:
    """
    In-memory fake for ChapterRepositoryProtocol.

    Stores chapters keyed by (chapter_id, novel_id).
    """

    def __init__(self) -> None:
        self._store: dict[tuple[uuid.UUID, uuid.UUID], Chapter] = {}
        self.calls: list[CallRecord] = []

    def seed(self, *chapters: Chapter) -> None:
        """Pre-populate the store with chapters."""
        for ch in chapters:
            self._store[(ch.id, ch.novel_id)] = ch

    async def get_by_id(self, chapter_id: uuid.UUID, novel_id: uuid.UUID) -> Chapter | None:
        self.calls.append(
            CallRecord("get_by_id", kwargs={"chapter_id": chapter_id, "novel_id": novel_id})
        )
        return self._store.get((chapter_id, novel_id))

    async def list_by_novel(self, novel_id: uuid.UUID) -> list[Chapter]:
        self.calls.append(CallRecord("list_by_novel", kwargs={"novel_id": novel_id}))
        return sorted(
            [ch for ch in self._store.values() if ch.novel_id == novel_id],
            key=lambda c: c.position,
        )

    async def max_position(self, novel_id: uuid.UUID) -> int:
        self.calls.append(CallRecord("max_position", kwargs={"novel_id": novel_id}))
        chapters = [ch for ch in self._store.values() if ch.novel_id == novel_id]
        if not chapters:
            return -1
        return max(ch.position for ch in chapters)

    async def create(
        self, novel_id: uuid.UUID, request: CreateChapterRequest, position: int
    ) -> Chapter:
        self.calls.append(CallRecord("create", kwargs={"novel_id": novel_id, "position": position}))
        chapter = Chapter()
        _apply_setattr(
            chapter,
            {
                "id": uuid.uuid4(),
                "novel_id": novel_id,
                "title": request.title,
                "content": request.content or "",
                "position": position,
                "word_count": len(request.content.split()) if request.content else 0,
                "status": "draft",
                "pov_character_id": "",
                "timeline_position": "",
                "embeddings_dirty": True,
            },
        )
        self._store[(chapter.id, novel_id)] = chapter
        return chapter

    async def update_content(self, chapter: Chapter, content: str, word_count: int) -> Chapter:
        self.calls.append(
            CallRecord(
                "update_content",
                kwargs={"content": content, "word_count": word_count},
            )
        )
        chapter.content = content
        chapter.word_count = word_count
        chapter.embeddings_dirty = True
        return chapter

    async def update_meta(self, chapter: Chapter, request: UpdateChapterMetaRequest) -> Chapter:
        self.calls.append(CallRecord("update_meta"))
        updates = request.model_dump(exclude_none=True)
        _apply_setattr(chapter, updates)
        return chapter

    async def reorder(self, novel_id: uuid.UUID, chapter_ids: list[uuid.UUID]) -> list[Chapter]:
        self.calls.append(
            CallRecord("reorder", kwargs={"novel_id": novel_id, "chapter_ids": chapter_ids})
        )
        for position, cid in enumerate(chapter_ids):
            for key, chapter in self._store.items():
                if key[0] == cid and key[1] == novel_id:
                    chapter.position = position
        return await self.list_by_novel(novel_id)

    async def delete(self, chapter: Chapter) -> None:
        self.calls.append(CallRecord("delete"))
        self._store.pop((chapter.id, chapter.novel_id), None)

    # ------------------------------------------------------------------
    # Assertion helpers
    # ------------------------------------------------------------------

    def call_count(self, method: str) -> int:
        return sum(1 for c in self.calls if c.method == method)

    def assert_called(self, method: str, **kwargs: Any) -> None:
        for call in self.calls:
            if call.method == method and call.matches(kwargs):
                return
        raise AssertionError(f"No call to {method} with {kwargs}")

    def assert_called_once(self, method: str) -> None:
        count = self.call_count(method)
        if count != 1:
            raise AssertionError(f"Expected 1 call to {method}, got {count}")

    def assert_not_called(self, method: str) -> None:
        count = self.call_count(method)
        if count > 0:
            raise AssertionError(f"Expected 0 calls to {method}, got {count}")


# ======================================================================
# FakeNovelRepository
# ======================================================================


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


# ======================================================================
# FakeVolumeRepository
# ======================================================================


class FakeVolumeRepository:
    """
    In-memory fake for VolumeRepositoryProtocol.

    Stores volumes keyed by (volume_id, novel_id).
    """

    def __init__(self) -> None:
        self._store: dict[tuple[uuid.UUID, uuid.UUID], Volume] = {}
        self.calls: list[CallRecord] = []

    def seed(self, *volumes: Volume) -> None:
        for v in volumes:
            self._store[(v.id, v.novel_id)] = v

    async def get_by_id(self, volume_id: uuid.UUID, novel_id: uuid.UUID) -> Volume | None:
        self.calls.append(
            CallRecord("get_by_id", kwargs={"volume_id": volume_id, "novel_id": novel_id})
        )
        return self._store.get((volume_id, novel_id))

    async def list_by_novel(self, novel_id: uuid.UUID) -> list[Volume]:
        self.calls.append(CallRecord("list_by_novel", kwargs={"novel_id": novel_id}))
        return sorted(
            [v for v in self._store.values() if v.novel_id == novel_id],
            key=lambda v: v.position,
        )

    async def max_position(self, novel_id: uuid.UUID) -> int:
        self.calls.append(CallRecord("max_position", kwargs={"novel_id": novel_id}))
        volumes = [v for v in self._store.values() if v.novel_id == novel_id]
        if not volumes:
            return -1
        return max(v.position for v in volumes)

    async def create(self, novel_id: uuid.UUID, title: str, position: int) -> Volume:
        self.calls.append(
            CallRecord(
                "create", kwargs={"novel_id": novel_id, "title": title, "position": position}
            )
        )
        volume = Volume()
        _apply_setattr(
            volume,
            {
                "id": uuid.uuid4(),
                "novel_id": novel_id,
                "title": title,
                "position": position,
            },
        )
        self._store[(volume.id, novel_id)] = volume
        return volume

    async def update(self, volume: Volume, request: UpdateVolumeRequest) -> Volume:
        self.calls.append(CallRecord("update"))
        updates = request.model_dump(exclude_none=True)
        _apply_setattr(volume, updates)
        return volume

    async def delete(self, volume: Volume) -> None:
        self.calls.append(CallRecord("delete"))
        self._store.pop((volume.id, volume.novel_id), None)

    def assert_called_once(self, method: str) -> None:
        count = sum(1 for c in self.calls if c.method == method)
        if count != 1:
            raise AssertionError(f"Expected 1 call to {method}, got {count}")

    def assert_called(self, method: str, **kwargs: Any) -> None:
        for call in self.calls:
            if call.method == method and call.matches(kwargs):
                return
        raise AssertionError(f"No call to {method} with {kwargs}")


# ======================================================================
# FakeAuthRepository
# ======================================================================


class FakeAuthRepository:
    """
    In-memory fake for AuthRepositoryProtocol.

    Stores users keyed by email and by id.
    """

    def __init__(self) -> None:
        self._by_email: dict[str, User] = {}
        self._by_id: dict[uuid.UUID, User] = {}
        self.calls: list[CallRecord] = []

    def seed(self, *users: User) -> None:
        for u in users:
            self._by_email[u.email.lower()] = u
            self._by_id[u.id] = u

    async def get_by_email(self, email: str) -> User | None:
        self.calls.append(CallRecord("get_by_email", kwargs={"email": email}))
        return self._by_email.get(email.lower())

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        self.calls.append(CallRecord("get_by_id", kwargs={"user_id": user_id}))
        return self._by_id.get(user_id)

    async def create(self, email: str, hashed_password: str, display_name: str = "") -> User:
        self.calls.append(
            CallRecord("create", kwargs={"email": email, "display_name": display_name})
        )
        user = User()
        _apply_setattr(
            user,
            {
                "id": uuid.uuid4(),
                "email": email.lower(),
                "hashed_password": hashed_password,
                "display_name": display_name,
                "is_active": True,
                "is_verified": False,
            },
        )
        self._by_email[user.email] = user
        self._by_id[user.id] = user
        return user

    async def set_verified(self, user_id: uuid.UUID) -> None:
        self.calls.append(CallRecord("set_verified", kwargs={"user_id": user_id}))
        user = self._by_id.get(user_id)
        if user:
            user.is_verified = True

    def assert_called_once(self, method: str) -> None:
        count = sum(1 for c in self.calls if c.method == method)
        if count != 1:
            raise AssertionError(f"Expected 1 call to {method}, got {count}")

    def call_count(self, method: str) -> int:
        return sum(1 for c in self.calls if c.method == method)
