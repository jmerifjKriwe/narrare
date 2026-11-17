"""Scene: the prose unit under a chapter — columns, ownership, the deferrable
position invariant and the chapter-delete cascade.

W4 makes writing scene-centric (design D1/D2): a chapter is a grouping shell,
its scenes carry the prose. The position invariant is the chapters' (#521) —
one number per scene in a chapter, unique in the table, deferrable so a
renumber passes through states the plain form refuses and the check belongs
at commit. Ownership is the chapters' too: the row carries ``user_id`` itself
(UserOwned), the chapter link reaches the novel, and a chapter going away
takes its scenes with it — the database's cascade, not a caller's promise.
"""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.kernel.contracts.models import Chapter, Novel, Scene
from app.kernel.db.base import Base
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

SCENE_COLUMNS = {
    "id",
    "user_id",
    "chapter_id",
    "position",
    "title",
    "body",
    "setting",
    "story_time",
    "created_at",
    "updated_at",
}


def test_scenes_is_registered_with_exactly_these_columns() -> None:
    """The table exposes exactly the scene contract's columns — drift fails here."""
    table = Base.metadata.tables[Scene.__tablename__]
    assert set(table.columns.keys()) == SCENE_COLUMNS


def test_chapters_carries_a_nullable_target_words() -> None:
    """The per-chapter goal (W4 D8); unset is a real answer, not a zero."""
    column = Base.metadata.tables["chapters"].columns["target_words"]
    assert column.nullable is True


def test_users_carry_nullable_author_name_and_daily_goal_words() -> None:
    """The profile name (D9/D22) and the atelier-level daily goal (D8)."""
    users = Base.metadata.tables["users"]
    assert users.columns["author_name"].nullable is True
    assert users.columns["daily_goal_words"].nullable is True


def test_scene_ownership_reaches_the_users_table() -> None:
    """Rule 4: the row carries its owner, and the chapter link cascades.

    The same shape Chapter models: ``user_id`` from UserOwned reaches users
    directly; ``chapter_id`` reaches the chapter, whose own key reaches the
    novel. Both deletes cascade — a scene cannot outlive its chapter or user.
    """
    table = Base.metadata.tables["scenes"]
    (user_fk,) = table.columns["user_id"].foreign_keys
    assert user_fk.column.table.name == "users"
    assert user_fk.ondelete == "CASCADE"
    (chapter_fk,) = table.columns["chapter_id"].foreign_keys
    assert chapter_fk.column.table.name == "chapters"
    assert chapter_fk.ondelete == "CASCADE"


OWNER = uuid4()


@pytest.fixture
async def owner(empty_tables: None) -> UUID:
    """A seeded user on empty tables: the keys every scene row needs exist."""
    await seed_user(OWNER)
    return OWNER


async def _chapter(
    session: AsyncSession, *, position: int = 0, novel: Novel | None = None
) -> Chapter:
    """A chapter in a novel — the parents a scene row hangs from.

    Without a novel one is made; pass one to hang several chapters off the
    same book, the way the tree shows them.
    """
    if novel is None:
        novel = Novel(user_id=OWNER, title="Der Nebel")
        session.add(novel)
        await session.flush()
    chapter = Chapter(user_id=OWNER, novel_id=novel.id, title="", position=position)
    session.add(chapter)
    await session.flush()
    return chapter


async def test_a_new_scene_defaults_to_empty_prose_and_no_metadata(owner: UUID) -> None:
    """Title and body default to the empty string; the labels stay unset.

    An empty title is the localized placeholder's state (design §5), not a
    lie the column tells; setting/story_time are nullable labels, None until
    the writer answers.
    """
    async with Session() as session:
        chapter = await _chapter(session)
        scene = Scene(user_id=OWNER, chapter_id=chapter.id, position=0)
        session.add(scene)
        await session.commit()
        await session.refresh(scene)

    assert scene.title == ""
    assert scene.body == ""
    assert scene.setting is None
    assert scene.story_time is None
    assert scene.created_at is not None
    assert scene.updated_at is not None


async def test_positions_are_unique_per_chapter_not_per_book(owner: UUID) -> None:
    """Two chapters may each hold a scene at position 0 — the pair is the key."""
    async with Session() as session:
        novel = Novel(user_id=OWNER, title="Der Nebel")
        session.add(novel)
        await session.flush()
        first = await _chapter(session, position=0, novel=novel)
        second = await _chapter(session, position=1, novel=novel)
        session.add_all(
            [
                Scene(user_id=OWNER, chapter_id=first.id, position=0),
                Scene(user_id=OWNER, chapter_id=second.id, position=0),
            ]
        )
        await session.commit()


async def test_two_scenes_swap_positions_in_one_transaction(owner: UUID) -> None:
    """A swap is two writes and one commit — no refused state in between.

    The chapters' precedent (WP6 §1, #521): a renumber passes through shapes
    a plain unique constraint refuses (a sits at 1 while b still holds 1), so
    the check defers to the commit, where the pair is consistent again.
    """
    async with Session() as session:
        chapter = await _chapter(session)
        session.add_all(
            [
                Scene(user_id=OWNER, chapter_id=chapter.id, position=0),
                Scene(user_id=OWNER, chapter_id=chapter.id, position=1),
            ]
        )
        await session.commit()

    async with Session() as session:
        rows = (
            (
                await session.execute(
                    select(Scene).where(Scene.chapter_id == chapter.id).order_by(Scene.position)
                )
            )
            .scalars()
            .all()
        )
        a, b = rows
        a.position, b.position = 1, 0
        await session.commit()

    async with Session() as session:
        rows = (
            (
                await session.execute(
                    select(Scene).where(Scene.chapter_id == chapter.id).order_by(Scene.position)
                )
            )
            .scalars()
            .all()
        )
        assert [(scene.position, scene.id) for scene in rows] == [(0, b.id), (1, a.id)]


async def test_positions_constraint_is_deferred(owner: UUID) -> None:
    """The catalog carries the deferral: ``DEFERRABLE INITIALLY DEFERRED``.

    ``condeferrable`` alone would accept the ``INITIALLY IMMEDIATE`` form,
    which checks at statement time and refuses the swap all the same;
    ``condeferred`` pins the initial mode the renumber relies on.
    """
    async with Session() as session:
        deferrable, initially_deferred = (
            await session.execute(
                text(
                    "SELECT condeferrable, condeferred FROM pg_constraint "
                    "WHERE contype = 'u' AND conrelid = 'scenes'::regclass "
                    "AND conname = 'uq_scenes_chapter_id_position'"
                )
            )
        ).one()
    assert deferrable is True
    assert initially_deferred is True


async def test_a_direct_duplicate_position_is_refused_at_commit(owner: UUID) -> None:
    """Deferral is not amnesty: a real duplicate still dies — at commit.

    The raw INSERT walks past the statement (that is what deferral bought)
    and meets the check when the transaction ends, the same boundary every
    renumber is consistent at.
    """
    async with Session() as session:
        chapter = await _chapter(session)
        session.add(Scene(user_id=OWNER, chapter_id=chapter.id, position=0))
        await session.commit()

    async with Session() as session:
        await session.execute(
            text(
                "INSERT INTO scenes (id, user_id, chapter_id, position, title, body, "
                "created_at, updated_at) "
                "VALUES (:id, :user_id, :chapter_id, 0, '', '', now(), now())"
            ),
            {"id": uuid4(), "user_id": OWNER, "chapter_id": chapter.id},
        )
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_delete_chapter_cascades_its_scenes(owner: UUID) -> None:
    """The database's cascade, not a caller's promise: the deleted chapter's
    scenes went with it; the other chapter's stayed.
    """
    async with Session() as session:
        novel = Novel(user_id=OWNER, title="Der Nebel")
        session.add(novel)
        await session.flush()
        doomed = await _chapter(session, position=0, novel=novel)
        kept = await _chapter(session, position=1, novel=novel)
        session.add_all(
            [
                Scene(user_id=OWNER, chapter_id=doomed.id, position=0),
                Scene(user_id=OWNER, chapter_id=doomed.id, position=1),
                Scene(user_id=OWNER, chapter_id=kept.id, position=0),
            ]
        )
        await session.commit()

    async with Session() as session:
        chapter = await session.get(Chapter, doomed.id)
        assert chapter is not None
        await session.delete(chapter)
        await session.commit()

    async with Session() as session:
        remaining = (await session.scalars(select(Scene.chapter_id))).all()
    assert remaining == [kept.id]
