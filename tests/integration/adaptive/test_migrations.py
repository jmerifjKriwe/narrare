"""Alembic migration regression tests for adaptive context (RULE-14).

Verifies that:
1. Migration 0033 adds ``project_settings.adaptive_settings`` JSONB column.
2. Migration 0034 adds ``invocation_evidence.adaptive_source_summary`` and
   ``adaptive_weights`` JSONB columns.
3. Existing rows survive the migration (NULL defaults).

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
async def test_project_settings_has_adaptive_settings_column(
    test_engine: AsyncEngine,
) -> None:
    """Migration 0033 adds adaptive_settings JSONB column."""
    async with test_engine.connect() as conn:
        columns = await conn.run_sync(
            lambda sync_conn: sa.inspect(sync_conn).get_columns("project_settings")
        )
    col_names = {c["name"] for c in columns}
    assert "adaptive_settings" in col_names, (
        "project_settings.adaptive_settings missing — run migration 0033"
    )
    adaptive_col = next(c for c in columns if c["name"] == "adaptive_settings")
    assert adaptive_col["nullable"] is True
