"""Integration test configuration and shared fixtures."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import sqlalchemy
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from narrare._app.database import Base, get_async_session
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
        pytest.skip("Database not available - run `just dev-services` first")


@pytest.fixture(scope="session")
async def test_engine() -> AsyncGenerator[AsyncEngine]:
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    # Skip migrations if tables already exist (CI already ran them)
    # This prevents duplicate migration attempts and async/sync conflicts
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                sqlalchemy.text(
                    "SELECT COUNT(*) FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = 'users'"
                )
            )
            table_exists = (result.scalar() or 0) > 0
    except Exception:
        table_exists = False

    if not table_exists:
        await _run_test_migrations(TEST_DATABASE_URL)

    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def _run_test_migrations(db_url: str) -> None:
    """Run Alembic migrations against the test database.

    Uses the real migration path so that integration tests validate
    that ``alembic upgrade head`` works end-to-end.
    """
    import asyncio

    from alembic.config import Config

    from alembic import command

    # Resolve alembic config relative to the workspace root
    # tests/integration/conftest.py -> workspace root
    workspace_root = Path(__file__).resolve().parents[2]
    api_dir = workspace_root / "apps" / "api"
    alembic_cfg = Config(str(api_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(api_dir / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, lambda: command.upgrade(alembic_cfg, "head"))


@pytest.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession]:
    """Transaction-wrapped session — rolls back after each test."""
    async with test_engine.connect() as conn:
        await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        yield session
        await session.close()
        await conn.rollback()


@pytest.fixture
async def client(db_session: AsyncSession):
    """Test HTTP client with DB session override."""
    app = create_app()

    async def override_session():
        yield db_session

    app.dependency_overrides[get_async_session] = override_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
async def auth_token(client: AsyncClient) -> str:
    """Register a test user and return their access token."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "password": "testpassword123",
            "display_name": "Test User",
        },
    )
    assert response.status_code == 201
    return response.json()["access_token"]


@pytest.fixture
def auth_headers(auth_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
async def registered_user(client: AsyncClient) -> dict[str, str]:
    """Register a unique test user, return credentials and token."""
    email = f"test-{uuid.uuid4().hex[:8]}@example.com"
    password = "testpassword123"
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "display_name": "Test User",
        },
    )
    assert response.status_code == 201, response.text
    return {
        "email": email,
        "password": password,
        "access_token": response.json()["access_token"],
    }


@pytest.fixture
async def novel_id(client: AsyncClient, auth_headers: dict[str, str]) -> str:
    """Create a novel and return its ID."""
    response = await client.post(
        "/api/v1/novels",
        json={"title": "Test Novel", "language": "en"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    return response.json()["id"]
