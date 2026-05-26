"""Integration tests for migration 0023 — safety properties.

Verifies safety guarantees of the token limit data migration:
- Idempotency: running migration twice produces identical results
- Existing data preserved: pre-existing rows in new tables are
  NOT overwritten by the migration

This is the companion to test_token_limit_migration.py (which covers
the core data migration scenarios).

Note: The conftest already runs ``alembic upgrade head`` before tests.
Since migration 0023 does not yet exist at that point, the test manually
executes the migration SQL via raw ``session.execute()``.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import sqlalchemy

from narrare.settings.models import ProjectSettings, UserAiSettings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# Migration SQL (same as apps/api/alembic/versions/0023_token_limit_migration.py)
# ---------------------------------------------------------------------------

_MIGRATE_USERS_SQL = """
    INSERT INTO user_token_limits (user_id, overrides)
    SELECT
        uas.user_id::text,
        jsonb_build_object(
            'token_profile', COALESCE(uas.token_limit_profile, 'balanced'),
            'output_limit',
                CASE COALESCE(uas.token_limit_profile, 'balanced')
                    WHEN 'quick' THEN 500
                    WHEN 'balanced' THEN 2000
                    WHEN 'long_texts' THEN 8000
                    ELSE 4096
                END,
            'legacy_per_category_overrides',
                COALESCE(uas.token_limit_overrides, '{}'::jsonb)
        )
    FROM user_ai_settings uas
    WHERE NOT EXISTS (
        SELECT 1 FROM user_token_limits utl
        WHERE utl.user_id = uas.user_id::text
    )
    AND (
        uas.token_limit_overrides IS NOT NULL
        AND uas.token_limit_overrides != '{}'::jsonb
        OR uas.token_limit_profile != 'balanced'
    )
"""

_MIGRATE_PROJECTS_SQL = """
    INSERT INTO project_token_limits (project_id, overrides)
    SELECT
        ps.novel_id::text,
        jsonb_build_object(
            'token_profile', COALESCE(ps.token_limit_profile, 'balanced'),
            'output_limit',
                CASE COALESCE(ps.token_limit_profile, 'balanced')
                    WHEN 'quick' THEN 500
                    WHEN 'balanced' THEN 2000
                    WHEN 'long_texts' THEN 8000
                    ELSE 4096
                END,
            'legacy_per_category_overrides',
                COALESCE(ps.token_limit_overrides, '{}'::jsonb)
        )
    FROM project_settings ps
    WHERE NOT EXISTS (
        SELECT 1 FROM project_token_limits ptl
        WHERE ptl.project_id = ps.novel_id::text
    )
    AND (
        ps.token_limit_overrides IS NOT NULL
        AND ps.token_limit_overrides != '{}'::jsonb
        OR ps.token_limit_profile != 'balanced'
    )
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_user(db_session: AsyncSession, user_id: uuid.UUID) -> None:
    """Insert a minimal User row to satisfy FK constraints on user_ai_settings."""
    from narrare.auth.models import User

    user = User(
        id=user_id,
        email=f"migration-safety-{user_id.hex[:8]}@example.com",
        hashed_password="not-a-real-hash",
    )
    db_session.add(user)
    await db_session.flush()


async def _create_novel(db_session: AsyncSession, novel_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Insert a minimal Novel row to satisfy FK constraints."""
    from narrare.novels.models import Novel

    novel = Novel(id=novel_id, user_id=user_id, title="Safety Test Novel")
    db_session.add(novel)
    await db_session.flush()


async def _seed_user_with_limits(
    db_session: AsyncSession,
    user_id: uuid.UUID,
    profile: str = "balanced",
    overrides: dict[str, object] | None = None,
) -> None:
    """Insert a user with old-style token limit settings."""
    await _create_user(db_session, user_id)
    settings = UserAiSettings(
        user_id=user_id,
        token_limit_profile=profile,
        token_limit_overrides=overrides or {},
    )
    db_session.add(settings)
    await db_session.flush()


async def _seed_project_with_limits(
    db_session: AsyncSession,
    novel_id: uuid.UUID,
    user_id: uuid.UUID,
    profile: str = "balanced",
    overrides: dict[str, object] | None = None,
) -> None:
    """Insert a project with old-style token limit settings."""
    await _create_novel(db_session, novel_id, user_id)
    settings = ProjectSettings(
        novel_id=novel_id,
        token_limit_profile=profile,
        token_limit_overrides=overrides or {},
    )
    db_session.add(settings)
    await db_session.flush()


# ---------------------------------------------------------------------------
# Tests — Idempotency
# ---------------------------------------------------------------------------


class TestMigrationIdempotency:
    """Running migration twice produces identical results."""

    async def test_running_twice_does_not_create_duplicates(self, db_session: AsyncSession) -> None:
        """Second migration run does not insert duplicate rows."""
        user_id = uuid.uuid4()
        await _seed_user_with_limits(
            db_session, user_id, profile="long_texts", overrides={"writing": {}}
        )

        # First run
        await db_session.execute(sqlalchemy.text(_MIGRATE_USERS_SQL))
        await db_session.flush()

        # Second run
        await db_session.execute(sqlalchemy.text(_MIGRATE_USERS_SQL))
        await db_session.flush()

        # Verify only one row
        result = await db_session.execute(
            sqlalchemy.text("SELECT COUNT(*) FROM user_token_limits WHERE user_id = :uid"),
            {"uid": str(user_id)},
        )
        count = result.scalar_one()
        assert count == 1, "Second run should not create duplicates"

    async def test_data_unchanged_after_second_run(self, db_session: AsyncSession) -> None:
        """Data values remain the same after running migration twice."""
        user_id = uuid.uuid4()
        await _seed_user_with_limits(
            db_session,
            user_id,
            profile="quick",
            overrides={"writing": {"max_tokens": 2000}},
        )

        # First run
        await db_session.execute(sqlalchemy.text(_MIGRATE_USERS_SQL))
        await db_session.flush()

        result_first = await db_session.execute(
            sqlalchemy.text("SELECT overrides FROM user_token_limits WHERE user_id = :uid"),
            {"uid": str(user_id)},
        )
        first_overrides = dict(result_first.scalar_one())

        # Second run
        await db_session.execute(sqlalchemy.text(_MIGRATE_USERS_SQL))
        await db_session.flush()

        result_second = await db_session.execute(
            sqlalchemy.text("SELECT overrides FROM user_token_limits WHERE user_id = :uid"),
            {"uid": str(user_id)},
        )
        second_overrides = dict(result_second.scalar_one())

        assert first_overrides == second_overrides

    async def test_project_idempotent(self, db_session: AsyncSession) -> None:
        """Project migration is also idempotent."""
        user_id = uuid.uuid4()
        await _create_user(db_session, user_id)

        novel_id = uuid.uuid4()
        await _seed_project_with_limits(
            db_session,
            novel_id,
            user_id,
            profile="quick",
            overrides={"analysis": {"max_tokens": 500}},
        )

        # Run twice
        await db_session.execute(sqlalchemy.text(_MIGRATE_PROJECTS_SQL))
        await db_session.flush()
        await db_session.execute(sqlalchemy.text(_MIGRATE_PROJECTS_SQL))
        await db_session.flush()

        result = await db_session.execute(
            sqlalchemy.text("SELECT COUNT(*) FROM project_token_limits WHERE project_id = :pid"),
            {"pid": str(novel_id)},
        )
        count = result.scalar_one()
        assert count == 1, "Idempotency: second run should not duplicate"


# ---------------------------------------------------------------------------
# Tests — Existing data preserved
# ---------------------------------------------------------------------------


class TestExistingDataPreserved:
    """Pre-existing rows in new tables are NOT overwritten by migration."""

    async def test_existing_user_limits_not_overwritten(self, db_session: AsyncSession) -> None:
        """User row already in user_token_limits stays unchanged after migration."""
        from narrare.settings.token_limits.models import UserTokenLimits

        user_id = uuid.uuid4()
        await _seed_user_with_limits(
            db_session,
            user_id,
            profile="long_texts",
            overrides={"writing": {"max_tokens": 9999}},
        )

        # Pre-insert a row in the new table (simulating existing configuration via API)
        existing = UserTokenLimits(
            user_id=str(user_id),
            overrides={
                "token_profile": "custom",
                "output_limit": 4096,
                "tier_percentages": {"immediate": 0.5},
            },
        )
        db_session.add(existing)
        await db_session.flush()

        # Run migration — WHERE NOT EXISTS should skip this user
        await db_session.execute(sqlalchemy.text(_MIGRATE_USERS_SQL))
        await db_session.flush()

        # Verify existing data is unchanged
        result = await db_session.execute(
            sqlalchemy.text("SELECT overrides FROM user_token_limits WHERE user_id = :uid"),
            {"uid": str(user_id)},
        )
        overrides = dict(result.scalar_one())

        assert overrides["token_profile"] == "custom"
        assert overrides["output_limit"] == 4096
        assert "tier_percentages" in overrides
        # The migration should NOT have set output_limit to 8000 (long_texts default)
        assert overrides["output_limit"] != 8000
        # legacy_per_category_overrides should NOT appear (migration skipped this row)
        assert "legacy_per_category_overrides" not in overrides

    async def test_existing_project_limits_not_overwritten(self, db_session: AsyncSession) -> None:
        """Project row already in project_token_limits stays unchanged."""
        from narrare.settings.token_limits.models import ProjectTokenLimits

        user_id = uuid.uuid4()
        await _create_user(db_session, user_id)

        novel_id = uuid.uuid4()
        await _seed_project_with_limits(
            db_session,
            novel_id,
            user_id,
            profile="long_texts",
            overrides={"analysis": {"max_tokens": 9999}},
        )

        # Pre-insert a row in the new table (simulating existing configuration via API)
        existing = ProjectTokenLimits(
            project_id=str(novel_id),
            overrides={
                "token_profile": "custom",
                "output_limit": 2048,
            },
        )
        db_session.add(existing)
        await db_session.flush()

        # Run migration — WHERE NOT EXISTS should skip this project
        await db_session.execute(sqlalchemy.text(_MIGRATE_PROJECTS_SQL))
        await db_session.flush()

        # Verify existing data is unchanged
        result = await db_session.execute(
            sqlalchemy.text("SELECT overrides FROM project_token_limits WHERE project_id = :pid"),
            {"pid": str(novel_id)},
        )
        overrides = dict(result.scalar_one())

        assert overrides["token_profile"] == "custom"
        assert overrides["output_limit"] == 2048
        # The migration should NOT have overwritten this row
        assert overrides["output_limit"] != 8000
