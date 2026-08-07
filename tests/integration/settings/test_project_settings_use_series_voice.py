"""Regression test: project_settings.use_series_voice column (Spec 3 / Task 1).

Migration 0039 adds the per-novel opt-out flag for the Series Voice
Hierarchy (Delta model). The column is ``BOOLEAN NOT NULL DEFAULT TRUE`` —
every novel opts INTO series voice by default (series voice is the
foundation; novel voice is additive).

These tests MUST fail before 0039 is applied (column missing) and pass
afterwards. They mirror the established pattern in
``test_project_settings_schema.py`` (token_limit_profile regression) and
cover the three behaviours the column must guarantee:

1. The column exists on ``project_settings``.
2. An ORM insert succeeds and the Python default (``True``) is applied.
3. The server default backfills existing / non-ORM inserts to ``True``.
4. The flag accepts ``False`` (the actual opt-out path).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select, text

from narrare.auth.models import User
from narrare.novels.models import Novel
from narrare.settings.models import ProjectSettings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def _create_user(session: AsyncSession, user_id: uuid.UUID) -> User:
    """Insert a minimal User row to satisfy FK constraints."""
    user = User(
        id=user_id,
        email=f"test-{user_id}@example.com",
        hashed_password="not-a-real-hash",
    )
    session.add(user)
    await session.flush()
    return user


async def _create_novel(session: AsyncSession, novel_id: uuid.UUID) -> Novel:
    """Insert a minimal Novel row to satisfy FK constraints.

    Novel.user_id references users.id via a DB-level FK (not declared in the
    ORM model), so a User row must exist first.
    """
    user_id = uuid.uuid4()
    await _create_user(session, user_id)
    novel = Novel(
        id=novel_id,
        user_id=user_id,
        title="Test Novel for Series Voice",
    )
    session.add(novel)
    await session.flush()
    return novel


class TestProjectSettingsUseSeriesVoice:
    """Verify the use_series_voice column exists and behaves correctly."""

    async def test_column_exists_in_information_schema(self, db_session: AsyncSession) -> None:
        """The use_series_voice column must exist on the project_settings table.

        Most direct check — if missing, migration 0039 has not been applied.
        """
        result = await db_session.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'project_settings' "
                "AND column_name = 'use_series_voice'"
            )
        )
        row = result.scalar_one_or_none()
        assert row == "use_series_voice", (
            "column 'use_series_voice' is missing from project_settings — "
            "migration 0039_series_voice not applied"
        )

    async def test_column_is_not_nullable(self, db_session: AsyncSession) -> None:
        """The use_series_voice column must be NOT NULL.

        Spec 3 requires a definitive opt-in/opt-out decision — NULL would
        force every consumer into a three-valued check. NOT NULL guarantees
        the flag always resolves to a boolean.
        """
        result = await db_session.execute(
            text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_name = 'project_settings' "
                "AND column_name = 'use_series_voice'"
            )
        )
        assert result.scalar_one() == "NO"

    async def test_orm_insert_defaults_to_true(self, db_session: AsyncSession) -> None:
        """An ORM insert without the flag must default to True (opt-in)."""
        novel_id = uuid.uuid4()
        await _create_novel(db_session, novel_id)

        settings = ProjectSettings(novel_id=novel_id)
        db_session.add(settings)
        await db_session.flush()

        result = await db_session.execute(
            select(ProjectSettings).where(ProjectSettings.novel_id == novel_id)
        )
        found = result.scalar_one()
        assert found.use_series_voice is True

    async def test_server_default_backfills_to_true(self, db_session: AsyncSession) -> None:
        """A raw INSERT (no ORM) must hit the server default of True.

        This is the backfill guarantee for existing rows and any non-ORM
        insert path — the server_default added in migration 0039.
        """
        novel_id = uuid.uuid4()
        await _create_novel(db_session, novel_id)

        await db_session.execute(
            text("INSERT INTO project_settings (novel_id) VALUES (:novel_id)"),
            {"novel_id": str(novel_id)},
        )

        result = await db_session.execute(
            text("SELECT use_series_voice FROM project_settings WHERE novel_id = :novel_id"),
            {"novel_id": str(novel_id)},
        )
        assert result.scalar_one() is True

    async def test_can_be_set_to_false(self, db_session: AsyncSession) -> None:
        """The opt-out path: use_series_voice accepts False.

        This is the per-novel opt-out exercised by Spec 3 Task 3 (novel
        settings PATCH) and consumed by Task 4 (AuthorVoiceConsumer Delta).
        """
        novel_id = uuid.uuid4()
        await _create_novel(db_session, novel_id)

        settings = ProjectSettings(novel_id=novel_id, use_series_voice=False)
        db_session.add(settings)
        await db_session.flush()

        result = await db_session.execute(
            select(ProjectSettings).where(ProjectSettings.novel_id == novel_id)
        )
        found = result.scalar_one()
        assert found.use_series_voice is False
