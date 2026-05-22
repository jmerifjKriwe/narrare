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


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line("markers", "requires_db: marks tests requiring database connection")


@pytest.fixture(autouse=True)
def _set_encryption_key(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    """Ensure NARRARE_ENCRYPTION_KEY is set for all integration tests."""
    from cryptography.fernet import Fernet

    monkeypatch.setenv("NARRARE_ENCRYPTION_KEY", Fernet.generate_key().decode())


@pytest_asyncio.fixture(scope="session", loop_scope="session", autouse=True)
async def check_db_available() -> None:
    """Skip all integration tests if database is not available, run migrations."""
    try:
        engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
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
    """Session-scoped test engine."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, pool_pre_ping=True)
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


def _override_factory_deps(app: FastAPI, db_session: AsyncSession) -> None:
    """Override dependency factories that don't use ``Depends(get_async_session)``.

    Some factories (e.g. ``get_kb_service``) accept ``session: AsyncSession``
    as a bare parameter instead of ``session = Depends(get_async_session)``.
    FastAPI therefore treats it as a query parameter and fails with 422.
    We bypass this by overriding the entire factory with a closure that
    already captures the test session.
    """
    from narrare.kb.dependencies import get_kb_service, get_rel_service
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.relationship_service import RelationshipService
    from narrare.kb.repository import KBRepository
    from narrare.kb.service import KBService
    from narrare.novels.repository import NovelRepository

    def _make_kb_service() -> KBService:
        return KBService(
            repo=KBRepository(db_session),
            novel_repo=NovelRepository(db_session),
        )

    def _make_rel_service() -> RelationshipService:
        return RelationshipService(
            rel_repo=RelationshipRepository(db_session),
            entry_repo=KBRepository(db_session),
        )

    app.dependency_overrides[get_kb_service] = _make_kb_service  # type: ignore[assignment]
    app.dependency_overrides[get_rel_service] = _make_rel_service  # type: ignore[assignment]


@pytest_asyncio.fixture(loop_scope="session")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    """Test HTTP client with DB session override."""
    app = create_app()

    async def override_session():
        yield db_session

    app.dependency_overrides[get_async_session] = override_session

    # Some dependency factories (e.g. KB) accept ``session: AsyncSession``
    # without ``Depends(get_async_session)``, which prevents FastAPI from
    # resolving the session through the dependency override above.  We
    # override these factories directly so they receive the test session.
    _override_factory_deps(app, db_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(loop_scope="session")
async def auth_headers(client: AsyncClient, db_session: AsyncSession) -> dict[str, str]:
    """Create a test user and return authorization headers with valid token."""
    import uuid
    from datetime import UTC, datetime

    from narrare._app.config import get_settings
    from narrare.auth.models import User
    from narrare.auth.security import create_access_token, hash_password

    # Create test user in the database
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
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
