"""Integration tests for migration 0023 — token limit data migration.

Verifies the data migration from old columns
(user_ai_settings.token_limit_profile + token_limit_overrides and
project_settings.token_limit_profile + token_limit_overrides) into the
new tables (user_token_limits and project_token_limits).

Test scenarios (this file):
1. User data migration — old profile + overrides copied to new table
2. Project data migration — old profile + overrides copied to new table
5. Default profile behavior — edge cases (null profile, balanced+overrides)

See test_token_limit_migration_safety.py for:
3. Idempotency — running migration twice produces same result
4. Existing data preserved — pre-existing rows in new tables NOT overwritten

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
        email=f"migration-test-{user_id.hex[:8]}@example.com",
        hashed_password="not-a-real-hash",
    )
    db_session.add(user)
    await db_session.flush()


async def _create_novel(db_session: AsyncSession, novel_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Insert a minimal Novel row to satisfy FK constraints."""
    from narrare.novels.models import Novel

    novel = Novel(id=novel_id, user_id=user_id, title="Migration Test Novel")
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
# Tests — User data migration
# ---------------------------------------------------------------------------


class TestUserTokenLimitMigration:
    """Verify user token limit data is migrated to new table."""

    async def test_migrates_long_texts_profile_with_overrides(
        self, db_session: AsyncSession
    ) -> None:
        """User with 'long_texts' profile + overrides is migrated correctly."""
        user_id = uuid.uuid4()
        await _seed_user_with_limits(
            db_session,
            user_id,
            profile="long_texts",
            overrides={"writing": {"max_tokens": 8000, "temperature": 0.9}},
        )

        # Run migration SQL
        await db_session.execute(sqlalchemy.text(_MIGRATE_USERS_SQL))
        await db_session.flush()

        # Verify data in new table
        result = await db_session.execute(
            sqlalchemy.text("SELECT overrides FROM user_token_limits WHERE user_id = :uid"),
            {"uid": str(user_id)},
        )
        row = result.one_or_none()
        assert row is not None, "Expected a row in user_token_limits"
        overrides = dict(row[0])

        assert overrides["token_profile"] == "long_texts"
        assert overrides["output_limit"] == 8000
        assert "writing" in overrides.get("legacy_per_category_overrides", {})

    async def test_migrates_quick_profile_without_overrides(self, db_session: AsyncSession) -> None:
        """User with only profile change (no overrides) is migrated."""
        user_id = uuid.uuid4()
        await _seed_user_with_limits(db_session, user_id, profile="quick")

        await db_session.execute(sqlalchemy.text(_MIGRATE_USERS_SQL))
        await db_session.flush()

        result = await db_session.execute(
            sqlalchemy.text("SELECT overrides FROM user_token_limits WHERE user_id = :uid"),
            {"uid": str(user_id)},
        )
        row = result.one_or_none()
        assert row is not None
        overrides = dict(row[0])

        assert overrides["token_profile"] == "quick"
        assert overrides["output_limit"] == 500

    async def test_skips_balanced_profile_without_overrides(self, db_session: AsyncSession) -> None:
        """Default 'balanced' profile with empty overrides is NOT migrated."""
        user_id = uuid.uuid4()
        await _seed_user_with_limits(db_session, user_id, profile="balanced")

        await db_session.execute(sqlalchemy.text(_MIGRATE_USERS_SQL))
        await db_session.flush()

        result = await db_session.execute(
            sqlalchemy.text("SELECT COUNT(*) FROM user_token_limits WHERE user_id = :uid"),
            {"uid": str(user_id)},
        )
        count = result.scalar_one()
        assert count == 0, "Default settings should not be migrated"


class TestProjectTokenLimitMigration:
    """Verify project token limit data is migrated to new table."""

    async def test_migrates_quick_profile_with_overrides(self, db_session: AsyncSession) -> None:
        """Project with 'quick' profile + overrides is migrated correctly."""
        user_id = uuid.uuid4()
        await _create_user(db_session, user_id)

        novel_id = uuid.uuid4()
        await _seed_project_with_limits(
            db_session,
            novel_id,
            user_id,
            profile="quick",
            overrides={"analysis": {"max_tokens": 500, "temperature": 0.2}},
        )

        await db_session.execute(sqlalchemy.text(_MIGRATE_PROJECTS_SQL))
        await db_session.flush()

        result = await db_session.execute(
            sqlalchemy.text("SELECT overrides FROM project_token_limits WHERE project_id = :pid"),
            {"pid": str(novel_id)},
        )
        row = result.one_or_none()
        assert row is not None
        overrides = dict(row[0])

        assert overrides["token_profile"] == "quick"
        assert overrides["output_limit"] == 500
        assert "analysis" in overrides.get("legacy_per_category_overrides", {})

    async def test_migrates_long_texts_profile_without_overrides(
        self, db_session: AsyncSession
    ) -> None:
        """Project with only profile change is migrated."""
        user_id = uuid.uuid4()
        await _create_user(db_session, user_id)

        novel_id = uuid.uuid4()
        await _seed_project_with_limits(db_session, novel_id, user_id, profile="long_texts")

        await db_session.execute(sqlalchemy.text(_MIGRATE_PROJECTS_SQL))
        await db_session.flush()

        result = await db_session.execute(
            sqlalchemy.text("SELECT overrides FROM project_token_limits WHERE project_id = :pid"),
            {"pid": str(novel_id)},
        )
        row = result.one_or_none()
        assert row is not None
        overrides = dict(row[0])

        assert overrides["token_profile"] == "long_texts"
        assert overrides["output_limit"] == 8000


# ---------------------------------------------------------------------------
# Tests — Default (balanced) profile edge cases
# ---------------------------------------------------------------------------


class TestDefaultProfileBehavior:
    """Verify that default settings are handled correctly."""

    async def test_balanced_with_overrides_migrates(self, db_session: AsyncSession) -> None:
        """User with balanced profile BUT non-empty overrides IS migrated."""
        user_id = uuid.uuid4()
        await _seed_user_with_limits(
            db_session,
            user_id,
            profile="balanced",
            overrides={"writing": {"max_tokens": 4000}},
        )

        await db_session.execute(sqlalchemy.text(_MIGRATE_USERS_SQL))
        await db_session.flush()

        result = await db_session.execute(
            sqlalchemy.text("SELECT COUNT(*) FROM user_token_limits WHERE user_id = :uid"),
            {"uid": str(user_id)},
        )
        count = result.scalar_one()
        assert count == 1, "Balanced profile with overrides should be migrated"

    async def test_skips_balanced_default_without_any_overrides(
        self, db_session: AsyncSession
    ) -> None:
        """User with default 'balanced' profile and no overrides is skipped.

        The token_limit_profile column is NOT NULL with server_default='balanced',
        so the COALESCE in the migration is defensive — a NULL profile is impossible.
        This test verifies that the default row (which exists implicitly via
        server_default) does NOT migrate, since it matches the 'balanced' default.
        """
        user_id = uuid.uuid4()
        await _create_user(db_session, user_id)

        # Insert with explicit 'balanced' (same as server_default) and empty overrides
        settings = UserAiSettings(
            user_id=user_id,
            token_limit_profile="balanced",
            token_limit_overrides={},
        )
        db_session.add(settings)
        await db_session.flush()

        await db_session.execute(sqlalchemy.text(_MIGRATE_USERS_SQL))
        await db_session.flush()

        result = await db_session.execute(
            sqlalchemy.text("SELECT COUNT(*) FROM user_token_limits WHERE user_id = :uid"),
            {"uid": str(user_id)},
        )
        count = result.scalar_one()
        assert count == 0, "Default balanced profile with empty overrides should not migrate"
