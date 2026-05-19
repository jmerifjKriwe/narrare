"""Integration test configuration — pytest-asyncio 1.3.0 compatible."""

from __future__ import annotations

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
    """Skip all integration tests if database is not available."""
    try:
        engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
        async with engine.connect() as conn:
            await conn.execute(sqlalchemy.text("SELECT 1"))
        await engine.dispose()
    except Exception:
        pytest.skip("Database not available")


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def test_engine() -> AsyncGenerator[AsyncEngine]:
    """Session-scoped test engine."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, pool_pre_ping=True)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def _test_app() -> AsyncGenerator[FastAPI]:  # pyright: ignore[reportUnusedFunction]
    """Session-scoped FastAPI app — lifespan runs once, not per test."""
    app = create_app()
    yield app
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(loop_scope="session")
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession]:
    """Transaction-wrapped session — rolled back after each test."""
    async with test_engine.connect() as conn:
        transaction = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        yield session
        await session.close()
        await transaction.rollback()


@pytest_asyncio.fixture(loop_scope="session")
async def client(_test_app: FastAPI, db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    """Test HTTP client with DB session override."""

    async def override_session():
        yield db_session

    _test_app.dependency_overrides[get_async_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=_test_app), base_url="http://test") as c:
        yield c

    _test_app.dependency_overrides.pop(get_async_session, None)


@pytest_asyncio.fixture(loop_scope="session")
async def auth_headers(client: AsyncClient, db_session: AsyncSession) -> dict[str, str]:
    """Create a test user and return authorization headers with valid token."""
    import uuid
    from datetime import UTC, datetime, timedelta

    import jwt

    from narrare.auth.models import User
    from narrare.auth.security import hash_password

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

    # Create a valid JWT token
    secret_key = "test-secret-key-not-for-production"
    token = jwt.encode(
        {
            "sub": str(user.id),
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(minutes=60),
            "type": "access",
        },
        secret_key,
        algorithm="HS256",
    )

    return {"Authorization": f"Bearer {token}"}
