"""Integration test configuration - minimal setup for debugging."""

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


@pytest.fixture(scope="session", autouse=True)
async def check_db_available() -> None:
    """Skip all integration tests if database is not available."""
    try:
        engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
        async with engine.connect() as conn:
            await conn.execute(sqlalchemy.text("SELECT 1"))
        await engine.dispose()
    except Exception:
        pytest.skip("Database not available")


@pytest_asyncio.fixture(scope="session")
async def test_engine() -> AsyncGenerator[AsyncEngine]:
    """Session-scoped test engine."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, pool_pre_ping=True)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession]:
    """Transaction-wrapped session."""
    async with test_engine.connect() as conn:
        transaction = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        yield session
        await session.close()
        await transaction.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    """Test HTTP client with DB session override."""
    app = create_app()

    async def override_session():
        yield db_session

    app.dependency_overrides[get_async_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
