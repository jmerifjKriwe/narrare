"""S5 — unit tests for the writing access helper ``verify_chapter_access``.

The helper is the shared foundation for the IDOR remediation wiring
slices (S6 writing endpoints, S3 WS sessions): it composes the EXISTING
repository methods (:meth:`ChapterRepository.get`,
:meth:`NovelRepository.get_by_id`) into one compound gate —
chapter exists ∧ chapter∈novel ∧ novel∈caller — with zero repository
signature changes.

Matrix (plan S5): owned chapter → returns the ``Chapter``; foreign novel
(chapter real, novel owned by another user) → ``NotFoundError``; unknown
chapter → ``NotFoundError``; chapter∉novel → ``NotFoundError``; foreign ≡
unknown (anti-enumeration: every failure is the identical ``NotFoundError``
shape, so callers cannot distinguish *which* check failed).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

import pytest

from narrare.writing._helpers import verify_chapter_access
from narrare_core.shared.errors import NotFoundError
from tests.factories import make_chapter

if TYPE_CHECKING:
    from narrare.chapters.models import Chapter
    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository

USER_A = uuid4()  # rightful owner of the novel + chapter
USER_B = uuid4()  # foreign caller


# ---------------------------------------------------------------------------
# Fakes (ADR-030 — fake-based, not MagicMock)
# ---------------------------------------------------------------------------


class _FakeChapterRepo:
    """In-memory ``ChapterRepository`` stand-in (``get`` only)."""

    def __init__(self, *chapters: Chapter) -> None:
        self._chapters: dict[UUID, Chapter] = {c.id: c for c in chapters}
        self.get_calls: list[UUID] = []

    async def get(self, chapter_id: UUID) -> Chapter | None:
        self.get_calls.append(chapter_id)
        return self._chapters.get(chapter_id)


class _FakeNovelRepo:
    """In-memory ``NovelRepository`` stand-in mapping novel → owner."""

    def __init__(self, ownership: dict[UUID, UUID]) -> None:
        self._ownership = ownership
        self.get_by_id_calls: list[tuple[UUID, UUID]] = []

    async def get_by_id(self, novel_id: UUID, user_id: UUID) -> object | None:
        self.get_by_id_calls.append((novel_id, user_id))
        if self._ownership.get(novel_id) != user_id:
            return None
        return object()  # helper only checks existence


def _repos(
    chapter: Chapter | None = None, ownership: dict[UUID, UUID] | None = None
) -> tuple[_FakeChapterRepo, _FakeNovelRepo]:
    chapters = (chapter,) if chapter is not None else ()
    return _FakeChapterRepo(*chapters), _FakeNovelRepo(ownership or {})


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestVerifyChapterAccess:
    """``verify_chapter_access`` compound gate (chapter ∧ novel ∧ owner)."""

    @pytest.mark.asyncio
    async def test_owned_chapter_returns_chapter(self) -> None:
        """Owner: chapter exists, belongs to the novel, novel belongs to
        the caller → the Chapter is returned (identity, not a copy)."""

        chapter = make_chapter(novel_id=uuid4())
        chapter_repo, novel_repo = _repos(chapter, {chapter.novel_id: USER_A})

        result = await verify_chapter_access(
            cast("ChapterRepository", chapter_repo),
            cast("NovelRepository", novel_repo),
            chapter.id,
            chapter.novel_id,
            str(USER_A),
        )

        assert result is chapter

    @pytest.mark.asyncio
    async def test_unknown_chapter_raises_not_found_before_novel_lookup(self) -> None:
        """Unknown chapter id → NotFoundError; the novel repo is never
        queried (fail fast, no information leak)."""

        unknown_chapter_id = uuid4()
        novel_id = uuid4()
        chapter_repo, novel_repo = _repos()

        with pytest.raises(NotFoundError, match="Chapter"):
            await verify_chapter_access(
                cast("ChapterRepository", chapter_repo),
                cast("NovelRepository", novel_repo),
                unknown_chapter_id,
                novel_id,
                str(USER_A),
            )

        assert novel_repo.get_by_id_calls == []

    @pytest.mark.asyncio
    async def test_chapter_not_in_novel_raises_not_found(self) -> None:
        """The chapter exists but belongs to a different novel → 404-shape
        NotFoundError; the novel lookup is skipped (binding failed first)."""

        chapter = make_chapter()  # novel_id is some OTHER novel
        addressed_novel = uuid4()
        chapter_repo, novel_repo = _repos(chapter, {addressed_novel: USER_A})

        with pytest.raises(NotFoundError, match="Chapter"):
            await verify_chapter_access(
                cast("ChapterRepository", chapter_repo),
                cast("NovelRepository", novel_repo),
                chapter.id,
                addressed_novel,
                str(USER_A),
            )

        assert novel_repo.get_by_id_calls == []

    @pytest.mark.asyncio
    async def test_foreign_novel_raises_not_found(self) -> None:
        """Chapter∈novel holds, but the novel belongs to USER_A while the
        caller is USER_B → NotFoundError (foreign ≡ unknown)."""

        chapter = make_chapter(novel_id=uuid4())
        chapter_repo, novel_repo = _repos(chapter, {chapter.novel_id: USER_A})

        with pytest.raises(NotFoundError, match="Chapter"):
            await verify_chapter_access(
                cast("ChapterRepository", chapter_repo),
                cast("NovelRepository", novel_repo),
                chapter.id,
                chapter.novel_id,
                str(USER_B),
            )

        # The ownership lookup ran with the CALLER's id (not the owner's).
        assert novel_repo.get_by_id_calls == [(chapter.novel_id, USER_B)]

    @pytest.mark.asyncio
    async def test_unknown_novel_raises_not_found(self) -> None:
        """Chapter exists and matches the addressed novel_id, but that novel
        does not exist at all → same NotFoundError as the foreign case."""

        chapter = make_chapter(novel_id=uuid4())
        chapter_repo, novel_repo = _repos(chapter, {})  # no known novels

        with pytest.raises(NotFoundError, match="Chapter"):
            await verify_chapter_access(
                cast("ChapterRepository", chapter_repo),
                cast("NovelRepository", novel_repo),
                chapter.id,
                chapter.novel_id,
                str(USER_A),
            )

    @pytest.mark.asyncio
    async def test_foreign_and_unknown_chapter_are_indistinguishable(self) -> None:
        """Anti-enumeration: a foreign (real but not owned) chapter and a
        purely unknown chapter produce the identical error type + shape."""

        foreign_chapter = make_chapter(novel_id=uuid4())  # USER_A's novel
        chapter_repo, novel_repo = _repos(foreign_chapter, {foreign_chapter.novel_id: USER_A})
        unknown_chapter_id = uuid4()

        with pytest.raises(NotFoundError) as foreign_exc:
            await verify_chapter_access(
                cast("ChapterRepository", chapter_repo),
                cast("NovelRepository", novel_repo),
                foreign_chapter.id,
                foreign_chapter.novel_id,
                str(USER_B),
            )
        with pytest.raises(NotFoundError) as unknown_exc:
            await verify_chapter_access(
                cast("ChapterRepository", _FakeChapterRepo()),
                cast("NovelRepository", _FakeNovelRepo({})),
                unknown_chapter_id,
                uuid4(),
                str(USER_B),
            )

        assert type(foreign_exc.value) is type(unknown_exc.value) is NotFoundError
        assert str(foreign_exc.value) == f"Chapter ({foreign_chapter.id}) not found"
        assert str(unknown_exc.value) == f"Chapter ({unknown_chapter_id}) not found"
