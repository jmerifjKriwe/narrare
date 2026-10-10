"""Integration tests for OutlineRepository — DB queries for chapter outlines.

Tests each repository method against a real PostgreSQL database:
- create(): happy path, with/without optional fields
- get_by_chapter_id(): found, not found
- get_all_for_novel(): multiple outlines, empty list
- update(): single field, multiple fields, not found raises NotFoundError
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from narrare.auth.models import User
from narrare.chapters.models import Chapter
from narrare.novels.models import Novel
from narrare.planning.repository import OutlineRepository
from narrare_core.shared.errors import NotFoundError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_USER_ID = uuid.uuid4()


async def _ensure_user(session: AsyncSession) -> User:
    """Insert a user row (required for FK constraint on novels.user_id)."""
    user = User(
        id=_USER_ID,
        email="outline-test@example.com",
        hashed_password="not-a-real-hash",
    )
    session.add(user)
    await session.flush()
    return user


async def _create_novel(session: AsyncSession) -> Novel:
    """Insert a novel row and return the ORM instance."""
    novel = Novel(id=uuid.uuid4(), user_id=_USER_ID, title="Test Novel")
    session.add(novel)
    await session.flush()
    return novel


async def _create_chapter(
    session: AsyncSession,
    novel_id: uuid.UUID,
    *,
    position: int = 0,
    title: str = "Test Chapter",
) -> Chapter:
    """Insert a chapter row and return the ORM instance."""
    chapter = Chapter(
        id=uuid.uuid4(),
        novel_id=novel_id,
        title=title,
        position=position,
    )
    session.add(chapter)
    await session.flush()
    return chapter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(loop_scope="session")
async def repo(db_session: AsyncSession) -> OutlineRepository:
    """Fresh OutlineRepository bound to the transactional test session."""
    return OutlineRepository(db_session)


@pytest_asyncio.fixture(loop_scope="session", autouse=True)
async def _setup_user(  # pyright: ignore[reportUnusedFunction]
    db_session: AsyncSession,
) -> None:
    """Ensure a user exists for FK constraints (novels.user_id → users.id)."""
    await _ensure_user(db_session)


# ---------------------------------------------------------------------------
# Tests: create()
# ---------------------------------------------------------------------------


class TestCreate:
    """OutlineRepository.create() tests."""

    async def test_create_with_all_fields(
        self, db_session: AsyncSession, repo: OutlineRepository
    ) -> None:
        """Create an outline with all fields populated."""
        novel = await _create_novel(db_session)
        chapter = await _create_chapter(db_session, novel.id)

        outline = await repo.create(
            chapter_id=chapter.id,
            stage_assignment="act-1",
            outline_notes="Some notes",
        )

        assert outline.id is not None
        assert outline.chapter_id == chapter.id
        assert outline.stage_assignment == "act-1"
        assert outline.outline_notes == "Some notes"
        assert outline.created_at is not None
        assert outline.updated_at is not None

    async def test_create_with_defaults(
        self, db_session: AsyncSession, repo: OutlineRepository
    ) -> None:
        """Create an outline without optional fields — defaults applied.

        The legacy ``planned_beats`` column is NOT NULL until the T17 drop;
        ``create`` no longer names it and relies on the ORM column default
        (empty list).
        """
        novel = await _create_novel(db_session)
        chapter = await _create_chapter(db_session, novel.id)

        outline = await repo.create(
            chapter_id=chapter.id,
            stage_assignment="act-2",
        )

        await db_session.flush()
        await db_session.refresh(outline)
        assert outline.planned_beats == []
        assert outline.outline_notes == ""


# ---------------------------------------------------------------------------
# Tests: get_by_chapter_id()
# ---------------------------------------------------------------------------


class TestGetByChapterId:
    """OutlineRepository.get_by_chapter_id() tests."""

    async def test_returns_outline_when_found(
        self, db_session: AsyncSession, repo: OutlineRepository
    ) -> None:
        """Returns the outline for an existing chapter."""
        novel = await _create_novel(db_session)
        chapter = await _create_chapter(db_session, novel.id)
        await repo.create(
            chapter_id=chapter.id,
            stage_assignment="act-1",
        )

        result = await repo.get_by_chapter_id(chapter.id)

        assert result is not None
        assert result.chapter_id == chapter.id
        assert result.stage_assignment == "act-1"

    async def test_returns_none_when_not_found(self, repo: OutlineRepository) -> None:
        """Returns None for a non-existent chapter ID."""
        result = await repo.get_by_chapter_id(uuid.uuid4())
        assert result is None


# ---------------------------------------------------------------------------
# Tests: get_all_for_novel()
# ---------------------------------------------------------------------------


class TestGetAllForNovel:
    """OutlineRepository.get_all_for_novel() tests."""

    async def test_returns_multiple_outlines_ordered_by_chapter_position(
        self, db_session: AsyncSession, repo: OutlineRepository
    ) -> None:
        """Returns outlines ordered by chapter position."""
        novel = await _create_novel(db_session)
        ch1 = await _create_chapter(db_session, novel.id, position=1, title="Chapter 1")
        ch2 = await _create_chapter(db_session, novel.id, position=0, title="Chapter 0")

        await repo.create(chapter_id=ch1.id, stage_assignment="act-2")
        await repo.create(chapter_id=ch2.id, stage_assignment="act-1")

        outlines = await repo.get_all_for_novel(novel.id)

        assert len(outlines) == 2
        # Ordered by chapter position: ch2 (pos 0) first, ch1 (pos 1) second.
        assert outlines[0].chapter_id == ch2.id
        assert outlines[1].chapter_id == ch1.id

    async def test_returns_empty_for_novel_without_outlines(
        self, db_session: AsyncSession, repo: OutlineRepository
    ) -> None:
        """Returns empty list for a novel that has chapters but no outlines."""
        novel = await _create_novel(db_session)
        await _create_chapter(db_session, novel.id)

        outlines = await repo.get_all_for_novel(novel.id)

        assert outlines == []

    async def test_returns_empty_for_unknown_novel(self, repo: OutlineRepository) -> None:
        """Returns empty list for a completely unknown novel ID."""
        outlines = await repo.get_all_for_novel(uuid.uuid4())
        assert outlines == []


# ---------------------------------------------------------------------------
# Tests: update()
# ---------------------------------------------------------------------------


class TestUpdate:
    """OutlineRepository.update() tests."""

    async def test_update_single_field(
        self, db_session: AsyncSession, repo: OutlineRepository
    ) -> None:
        """Update a single field on an existing outline."""
        novel = await _create_novel(db_session)
        chapter = await _create_chapter(db_session, novel.id)
        await repo.create(
            chapter_id=chapter.id,
            stage_assignment="act-1",
        )

        updated = await repo.update(chapter.id, stage_assignment="climax")

        assert updated.stage_assignment == "climax"
        assert updated.chapter_id == chapter.id

    async def test_update_multiple_fields(
        self, db_session: AsyncSession, repo: OutlineRepository
    ) -> None:
        """Update multiple fields in a single call."""
        novel = await _create_novel(db_session)
        chapter = await _create_chapter(db_session, novel.id)
        await repo.create(
            chapter_id=chapter.id,
            stage_assignment="act-1",
        )

        updated = await repo.update(
            chapter.id,
            stage_assignment="resolution",
            outline_notes="Updated notes",
        )

        assert updated.stage_assignment == "resolution"
        assert updated.outline_notes == "Updated notes"

    async def test_update_raises_not_found_for_missing_chapter(
        self, repo: OutlineRepository
    ) -> None:
        """Update raises NotFoundError when no outline exists for the chapter."""
        with pytest.raises(NotFoundError) as exc_info:
            await repo.update(uuid.uuid4(), stage_assignment="act-1")

        assert "ChapterOutline" in str(exc_info.value)
