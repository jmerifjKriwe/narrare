"""Alembic migration regression tests for author voice (RULE-14).

Verifies that migration 0036 adds the ``project_settings.author_voice`` JSONB
column (nullable). Existing rows survive the migration (NULL default —
consumers degrade gracefully per RULE-11).

Mirrors ``tests/integration/adaptive/test_migrations.py`` (the ADR-069
adaptive_settings precedent ADR-074 binds this repository to).

Requires: ``just dev-services`` running (PostgreSQL on port 5433).
Schema comes exclusively from Alembic migrations (RULE-14) —
``Base.metadata.create_all()`` is forbidden in integration tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import sqlalchemy as sa

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.mark.asyncio
async def test_project_settings_has_author_voice_column(
    test_engine: AsyncEngine,
) -> None:
    """Migration 0036 adds author_voice JSONB column (nullable)."""
    async with test_engine.connect() as conn:
        columns = await conn.run_sync(
            lambda sync_conn: sa.inspect(sync_conn).get_columns("project_settings")
        )
    col_names = {c["name"] for c in columns}
    assert "author_voice" in col_names, "project_settings.author_voice missing — run migration 0036"
    author_voice_col = next(c for c in columns if c["name"] == "author_voice")
    assert author_voice_col["nullable"] is True, (
        "project_settings.author_voice must be nullable (NULL = no profile yet; "
        "existing rows survive the migration; RULE-11 graceful degradation)."
    )
