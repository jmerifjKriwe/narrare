"""Integration test configuration — pytest-asyncio 1.3.0 compatible."""

from __future__ import annotations

import contextlib
import logging
import os
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
import sqlalchemy
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from narrare._app.database import get_async_session
from narrare._app.main import create_app

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastapi import FastAPI


TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://narrare:narrare@localhost:5433/narrare_test",
)

# Ensure the app's lifespan runs migrations on the SAME database the tests use.
# Without this, the lifespan reads DATABASE_URL from the dev environment
# (e.g. postgres:5432/narrare_dev) while tests use TEST_DATABASE_URL
# (e.g. postgres_test:5432/narrare_test) — tables never get created.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL


@pytest.fixture(autouse=True)
def _set_encryption_key(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    """Ensure NARRARE_ENCRYPTION_KEY is set for all integration tests."""
    from cryptography.fernet import Fernet

    monkeypatch.setenv("NARRARE_ENCRYPTION_KEY", Fernet.generate_key().decode())


@pytest.fixture(autouse=True)
def gc_after_test():
    """Force garbage collection after each test to finalize asyncpg connections.

    asyncpg closes connections asynchronously (Terminate message + socket close).
    Without explicit GC, these pending closes can race with pytest's
    ``collect_unraisable`` hook, producing false-positive ``ResourceWarning``
    errors that the ``unraisableexception`` plugin escalates to test errors.

    Calling ``gc.collect()`` after each test triggers ``__del__`` finalizers,
    ensuring connections are fully cleaned up before the next test's teardown
    validation runs.
    """
    import gc

    yield
    gc.collect()


@pytest_asyncio.fixture(scope="session", loop_scope="session", autouse=True)
async def check_db_available() -> None:
    """Skip all integration tests if database is not available, run migrations."""
    try:
        engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
        async with engine.connect() as conn:
            await conn.execute(sqlalchemy.text("SELECT 1"))
        await engine.dispose()
    except Exception:
        pytest.skip("Database not available")

    # Run migrations once per session via subprocess to avoid event-loop conflicts.
    # The alembic env.py uses asyncio.run() which would clash with our session loop.
    # On CI this is idempotent (migrations already ran in the CI step before tests).
    import subprocess
    from pathlib import Path

    alembic_dir = Path(__file__).resolve().parent.parent.parent / "apps" / "api" / "alembic"
    alembic_ini = alembic_dir.parent / "alembic.ini"
    subprocess.run(
        [
            "python",
            "-m",
            "alembic",
            "-c",
            str(alembic_ini) if alembic_ini.exists() else "alembic.ini",
            "upgrade",
            "head",
        ],
        env={
            **os.environ,
            "DATABASE_URL": TEST_DATABASE_URL,
        },
        cwd=alembic_dir.parent,
        check=True,
        capture_output=True,
    )


@pytest_asyncio.fixture(scope="session", loop_scope="session", autouse=True)
async def _dispose_module_engine() -> AsyncGenerator[None]:  # pyright: ignore[reportUnusedFunction]
    """Safety net: dispose module-level engine after all integration tests.

    The app lifespan already calls ``dispose_database()`` on shutdown, so
    this fixture is a belt-and-suspenders cleanup for edge cases where the
    module-level engine is imported without running the lifespan.
    """
    yield
    try:
        from narrare._app.database import _engine  # pyright: ignore[reportPrivateUsage]

        await _engine.dispose()
    except Exception:
        logging.debug("Safety-net engine dispose failed (already disposed or unavailable)")


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def test_engine() -> AsyncGenerator[AsyncEngine]:
    """Session-scoped test engine.

    Uses NullPool to prevent connection leaks that Python 3.14's
    pytest unraisableexception plugin would escalate to test failures.
    Each checkout creates a fresh connection that is immediately closed
    on checkin — the standard approach for test engines.
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=NullPool,
    )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession]:
    """Transaction-wrapped session — rolled back after each test."""
    async with test_engine.connect() as conn:
        transaction = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        yield session
        await session.close()
        # Rollback may fail if a DB error (e.g. IntegrityError) already
        # invalidated the underlying transaction.  Suppress the resulting
        # SAWarning ("transaction already deassociated from connection")
        # which would be escalated to an error by filterwarnings=["error"].
        with contextlib.suppress(Exception):
            await transaction.rollback()


@pytest_asyncio.fixture(loop_scope="session")
async def app(db_session: AsyncSession) -> AsyncGenerator[FastAPI]:
    """Create a FastAPI app with DB session and memory client overrides."""
    from narrare.memory.dependencies import get_memory_client
    from narrare_core.memory.mem0_client import NullMemoryClient

    app = create_app()

    async def override_session():
        yield db_session

    async def override_memory_client():
        return NullMemoryClient()

    app.dependency_overrides[get_async_session] = override_session
    app.dependency_overrides[get_memory_client] = override_memory_client

    yield app

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(loop_scope="session")
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient]:
    """Test HTTP client backed by the test app."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture(loop_scope="session")
async def auth_headers(client: AsyncClient, db_session: AsyncSession) -> dict[str, str]:
    """Create a test user and return authorization headers with valid token."""
    import uuid
    from datetime import UTC, datetime

    from narrare._app.config import get_settings
    from narrare.auth.models import User
    from narrare.auth.security import create_access_token, hash_password

    # Create test user in the database with a unique email to prevent any
    # possible unique-constraint conflict across test runs (even when a prior
    # transaction rollback has an edge-case failure).
    user = User(
        id=uuid.uuid4(),
        email=f"test-{uuid.uuid4().hex[:12]}@example.com",
        hashed_password=hash_password("testpassword123"),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(user)
    await db_session.flush()

    # Create a valid JWT token using the same settings the app uses.
    # get_settings() is @lru_cache'd — create_app() already populated it,
    # so both the app and this fixture use the identical secret_key.
    settings = get_settings()
    token = create_access_token(
        subject=str(user.id),
        secret_key=settings.secret_key,
        expires_minutes=settings.access_token_expire_minutes,
    )

    return {"Authorization": f"Bearer {token}"}
