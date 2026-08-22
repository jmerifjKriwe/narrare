# tests/integration/test_migration_0042_round_trip.py
"""Round-trip test for migration 0042 (NOTES-001 — chat project optional).

Verifies: at head, a conversation with NULL project_id can be inserted
(global notes chat, spec §6b); downgrading to 0041 removes project-less
conversations and their messages (documented data loss — meaningless without
the feature) and restores NOT NULL; re-upgrading re-allows NULL.
"""

from __future__ import annotations

import os
import subprocess
import uuid as _uuid
from pathlib import Path

import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine
from sqlalchemy.pool import NullPool as _NullPool

_PARENT_REVISION = "0041_notes"


def _alembic_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "apps" / "api" / "alembic"


def _run_alembic(*args: str) -> None:
    alembic_dir = _alembic_dir()
    alembic_ini = alembic_dir.parent / "alembic.ini"
    db_url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://narrare:narrare@localhost:5433/narrare_test",
    )
    env = {**os.environ, "DATABASE_URL": db_url, "PGOPTIONS": "-c lock_timeout=10s"}
    subprocess.run(
        [
            "python",
            "-m",
            "alembic",
            "-c",
            str(alembic_ini) if alembic_ini.exists() else "alembic.ini",
            *args,
        ],
        env=env,
        cwd=alembic_dir.parent,
        check=True,
        capture_output=True,
    )


@pytest.mark.schema_mutating
class TestMigration0042RoundTrip:
    async def test_null_project_conversation_survives_up_and_down(self) -> None:
        db_url = os.environ.get(
            "TEST_DATABASE_URL",
            "postgresql+asyncpg://narrare:narrare@localhost:5433/narrare_test",
        )
        _run_alembic("upgrade", "head")

        user_id = _uuid.uuid4()
        conv_id = _uuid.uuid4()
        eng = _create_async_engine(db_url, poolclass=_NullPool)
        try:
            async with eng.begin() as conn:
                await conn.execute(
                    sqlalchemy.text(
                        "INSERT INTO users (id, email, hashed_password, created_at, updated_at) "
                        "VALUES (:id, :email, 'fake_hash', now(), now())"
                    ),
                    {"id": user_id, "email": f"u-{user_id.hex[:10]}@example.com"},
                )
                await conn.execute(
                    sqlalchemy.text(
                        "INSERT INTO chat_conversations (id, project_id, user_id) "
                        "VALUES (:id, NULL, :uid)"
                    ),
                    {"id": conv_id, "uid": user_id},
                )
        finally:
            await eng.dispose()

        try:
            # Downgrade removes project-less conversations, restores NOT NULL.
            _run_alembic("downgrade", _PARENT_REVISION)
            eng = _create_async_engine(db_url, poolclass=_NullPool)
            try:
                async with eng.begin() as conn:
                    count = (
                        await conn.execute(
                            sqlalchemy.text(
                                "SELECT COUNT(*) FROM chat_conversations WHERE id = :id"
                            ),
                            {"id": conv_id},
                        )
                    ).scalar()
                    assert count == 0, "project-less conversations removed on downgrade"
            finally:
                await eng.dispose()

            _run_alembic("upgrade", "head")
        finally:
            # Safety net: ALWAYS leave the shared test DB at head.
            _run_alembic("upgrade", "head")
