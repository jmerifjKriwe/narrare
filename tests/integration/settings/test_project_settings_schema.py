"""Regression test: project_settings.token_limit_profile column exists after migrations.

Migration 0004_ai_settings added token_limit_profile to user_ai_settings
but forgot project_settings. Migration 0005 fixes this.

This test MUST fail before 0005 is applied and pass afterwards.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
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
    ORM model), so we must create a User row first.
    """
    user_id = uuid.uuid4()
    await _create_user(session, user_id)
    novel = Novel(
        id=novel_id,
        user_id=user_id,
        title="Test Novel for Schema",
    )
    session.add(novel)
    await session.flush()
    return novel


pytestmark = [
    pytest.mark.requires_db,
]


class TestProjectSettingsTokenLimitProfile:
    """Verify the token_limit_profile column exists and works on project_settings."""

    async def test_column_exists_in_information_schema(self, db_session: AsyncSession) -> None:
        """The token_limit_profile column must exist in the project_settings table.

        This is the most direct check — if the column is missing the migration
        has not been applied correctly.
        """
        result = await db_session.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'project_settings' "
                "AND column_name = 'token_limit_profile'"
            )
        )
        row = result.scalar_one_or_none()
        assert row == "token_limit_profile", (
            "column 'token_limit_profile' is missing from project_settings — "
            "migration 0005_project_settings_token_limit_profile not applied"
        )

    async def test_insert_with_token_limit_profile_succeeds(self, db_session: AsyncSession) -> None:
        """INSERT into project_settings with token_limit_profile must succeed.

        This is the exact failure the setup wizard triggers: the SQLAlchemy model
        includes token_limit_profile but the column was missing from the table.
        """
        novel_id = uuid.uuid4()
        await _create_novel(db_session, novel_id)

        settings = ProjectSettings(
            novel_id=novel_id,
            token_limit_profile="balanced",
        )
        db_session.add(settings)
        await db_session.flush()

        result = await db_session.execute(
            select(ProjectSettings).where(ProjectSettings.novel_id == novel_id)
        )
        found = result.scalar_one()
        assert found.token_limit_profile == "balanced"

    async def test_default_value_is_balanced(self, db_session: AsyncSession) -> None:
        """When token_limit_profile is not specified, the server default is 'balanced'."""
        novel_id = uuid.uuid4()
        await _create_novel(db_session, novel_id)

        settings = ProjectSettings(novel_id=novel_id)
        db_session.add(settings)
        await db_session.flush()

        result = await db_session.execute(
            select(ProjectSettings).where(ProjectSettings.novel_id == novel_id)
        )
        found = result.scalar_one()
        assert found.token_limit_profile == "balanced"

    async def test_non_default_profile_value(self, db_session: AsyncSession) -> None:
        """token_limit_profile accepts non-default values like 'quick'."""
        novel_id = uuid.uuid4()
        await _create_novel(db_session, novel_id)

        settings = ProjectSettings(
            novel_id=novel_id,
            token_limit_profile="quick",
        )
        db_session.add(settings)
        await db_session.flush()

        result = await db_session.execute(
            select(ProjectSettings).where(ProjectSettings.novel_id == novel_id)
        )
        found = result.scalar_one()
        assert found.token_limit_profile == "quick"
