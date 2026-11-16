"""wrap chapter bodies into scenes

Writing owns prose scenes (W4 design §5): the scene arrives as the writing
unit under a chapter, and every chapter's existing prose is carried into it.
The wrap is 1:1 with nothing to guess — each chapter becomes ONE scene at
position 1 with an empty title (the localized placeholder's state, not a
stored label), the chapter's body verbatim, and no setting or story_time
(the drafted overline and in-story label start unset). The scene's user is
the chapter's own, so ownership rides the chapter → novel chain unchanged
(rule 4). Empty and whitespace-only bodies wrap to empty scenes, not to
nothing: an empty chapter is a real state (D16).

The three answer columns land beside it: the chapter's own word goal
(``chapters.target_words``, distinct from the book's), and the user's author
name and atelier-level daily goal (``users.author_name``,
``users.daily_goal_words``). All nullable — a row without an answer does not
lie.

``chapters.body`` is deliberately retained by this revision: the models still
declare it and the reading code still counts from it, and the models-vs-history
gate requires the two schema paths to stay equal. Its removal rides the task
that moves the last reader onto scenes — dropping it here would either redden
that gate or strand the prose's readers. The wrap copies the prose; it does not
yet retire the column it copies from.

Revision ID: 666563abba5d
Revises: 9c651aea0d75
Create Date: 2026-11-16 16:40:51.600205

"""

from collections.abc import Sequence

import pgvector.sqlalchemy  # pyright: ignore[reportUnusedImport]
import sqlalchemy as sa  # pyright: ignore[reportUnusedImport]
from alembic import op  # pyright: ignore[reportUnusedImport]

revision: str = "666563abba5d"
down_revision: str | Sequence[str] | None = "9c651aea0d75"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scenes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("chapter_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("setting", sa.String(length=200), nullable=True),
        sa.Column("story_time", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["chapter_id"],
            ["chapters.id"],
            name=op.f("fk_scenes_chapter_id_chapters"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_scenes_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scenes")),
        # The chapters invariant (#521) in its deferrable form: a scene reorder
        # passes through states the plain form refuses, so the check belongs at
        # commit. Autogenerate renders the deferral; the replay gate pins it.
        sa.UniqueConstraint(
            "chapter_id",
            "position",
            deferrable=True,
            initially="DEFERRED",
            name=op.f("uq_scenes_chapter_id_position"),
        ),
    )
    op.create_index(op.f("ix_scenes_user_id"), "scenes", ["user_id"], unique=False)
    # The wrap runs against whatever chapters exist: one scene per chapter, the
    # chapter's own user and prose, position 1, empty title, no metadata. The
    # id is the database's own UUID; the timestamps are the scene's, from now().
    op.execute("""
        INSERT INTO scenes (id, user_id, chapter_id, position, title, body,
            setting, story_time, created_at, updated_at)
        SELECT gen_random_uuid(), c.user_id, c.id, 1, '', c.body, NULL, NULL, now(), now()
        FROM chapters c
    """)
    op.add_column("chapters", sa.Column("target_words", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("author_name", sa.String(length=200), nullable=True))
    op.add_column("users", sa.Column("daily_goal_words", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade is not a script: the pre-migration dump is the way back.

    Design D6 / ADR-103 — the history never runs destructive DDL downward;
    restore the dump ``prepare_database`` took before the upgrade instead.
    """
    raise RuntimeError(
        "downgrade is not supported; restore the pre-migration dump (design D6, ADR-103)"
    )
