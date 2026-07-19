"""Integration test configuration — pytest-asyncio 1.3.0 compatible."""

from __future__ import annotations

import contextlib
import logging
import os
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
import sqlalchemy
from fastapi import (  # noqa: TC002 — needed at runtime for get_type_hints resolution (see _disable_rate_limiting)
    Request,
    Response,
)
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from narrare._app.database import get_async_session
from narrare._app.main import create_app

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Iterator

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
def _disable_rate_limiting(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    """Disable rate limiting in integration tests.

    Module-level rate-limiter singletons (``AI_WRITE_LIMITER`` etc.) accumulate
    state across rapid test requests, causing false 429 failures. This patches
    two separate limiter surfaces:

    1. ``RateLimiter.__call__`` — the FastAPI dependency entry point used by
       every HTTP limiter (write/analysis/light/setup).
    2. ``AI_WS_LIMITER.try_acquire`` — the raw ``pyrate_limiter.Limiter``
       method used directly by WebSocket handlers (NOT a FastAPI Dep, so the
       ``__call__`` patch does not cover it). Without this, 3+ WS connections
       within one minute trip ``Rate(3, LONG_WINDOW_MS)`` → close code 4003.

    Production behaviour is unaffected — both patches are scoped to the test
    process via ``monkeypatch``.
    """
    from narrare._app.rate_limiter_dep import RateLimiter
    from narrare._app.rate_limits import AI_WS_LIMITER

    async def _noop_call(self: object, request: Request, response: Response) -> None:
        return None

    monkeypatch.setattr(RateLimiter, "__call__", _noop_call)
    # WebSocket limiter is a raw pyrate_limiter.Limiter, not a FastAPI Dep —
    # patch its try_acquire directly to prevent cross-test state accumulation.
    monkeypatch.setattr(AI_WS_LIMITER, "try_acquire", lambda *a, **kw: True)


@pytest.fixture(autouse=True)
def _set_encryption_key(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    """Ensure NARRARE_ENCRYPTION_KEY is set for all integration tests."""
    from cryptography.fernet import Fernet

    monkeypatch.setenv("NARRARE_ENCRYPTION_KEY", Fernet.generate_key().decode())


@pytest.fixture(autouse=True, scope="session")
def _no_real_mem0_clients() -> Iterator[None]:  # pyright: ignore[reportUnusedFunction] — autouse fixture, invoked via decorator reflection.
    """Prevent real mem0/QdrantClient creation during the integration session (RULE-20).

    SESSION-SCOPED (ADR-068 Decision 2): the integration suite has a
    session-scoped ``_prewarm_composer`` fixture (in
    ``tests/integration/writing/conftest.py``) that calls ``get_composer()``
    → ``_get_preference_service_instance()``. A function-scoped guard would
    activate only at the first test function, AFTER ``_prewarm_composer``
    has already run at session start — creating a real ``mem0.AsyncMemory``
    client once per integration session before any guard could prevent it.
    Session-scoping the guard ensures it runs before ``_prewarm_composer``;
    the explicit fixture dependency declared in
    ``_prewarm_composer(_no_real_mem0_clients: None)`` pins the ordering
    (autouse session fixtures otherwise have non-deterministic order).

    Uses ``pytest.MonkeyPatch()`` instantiated directly — the ``monkeypatch``
    fixture is function-scoped by design and cannot be used at session
    scope. Teardown via ``mp.undo()`` runs at session end.

    Integration counterpart of the unit-test guard in
    ``tests/unit/conftest.py`` (which stays function-scoped — unit tests
    do not use session-scoped prewarm fixtures). Patches the re-imported
    ``is_mem0_available`` reference in each mem0-backed singleton module
    so the singletons short-circuit before reaching
    ``create_memory_client_sync()``.

    Without this guard, mem0-backed singletons create real
    ``mem0.AsyncMemory`` clients (mem0 IS installed in the test env and
    ``tests/conftest.py`` sets dummy ``OPENAI_API_KEY`` /
    ``ANTHROPIC_API_KEY``). The clients' Qdrant/sqlite resources bind to
    the event loop active at creation time, then leak across loops under
    pytest-asyncio + pytest-xdist (each worker process has its own
    session loop; TestClient-based tests additionally use a portal-thread
    loop). At teardown this surfaces as
    ``RuntimeError: Task got Future attached to a different loop`` — the
    proximate cause of the PR #126 regression in
    ``test_session_stop_and_recovery.py``.

    Targets the same module set as the unit-test guard:
    - ``narrare._app.dependencies_prompts`` — preference-service singleton
    - ``narrare.kb._feedback_memory_deps`` — consistency-feedback singleton
    - ``narrare.writing._session_memory_deps`` — session-memory singleton
      (extracted from ``deps_writing.py`` per RULE-04; the singleton
      state and module-level availability imports move together)

    Integration tests that specifically exercise the mem0-available path
    override ``is_mem0_available`` via their own ``monkeypatch.setattr``
    (function-scoped — those overrides are tighter than this session
    guard and compose correctly because they patch the same module
    attribute after the session guard has).
    """
    mp = pytest.MonkeyPatch()
    mp.setattr(
        "narrare._app.dependencies_prompts.is_mem0_available",
        lambda: False,
    )
    mp.setattr(
        "narrare.kb._feedback_memory_deps.is_mem0_available",
        lambda: False,
    )
    mp.setattr(
        "narrare.writing._session_memory_deps.is_mem0_available",
        lambda: False,
    )
    yield
    mp.undo()


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


@pytest_asyncio.fixture(autouse=True)
async def _clear_client_cookies(client: AsyncClient) -> AsyncGenerator[None]:  # pyright: ignore[reportUnusedFunction]
    """Clear cookies between tests to prevent session-scoped cookie leakage.

    The ``client`` fixture is session-scoped (one AsyncClient for all tests).
    Without cleanup, tests that explicitly set cookies (e.g. refresh-token
    tests) leak those cookies to subsequent tests, causing 401 errors when
    ``pytest-randomly`` shuffles execution order.
    """
    yield
    client.cookies.clear()


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
    """Transaction-wrapped session — rolled back after each test.

    This is a **function-scoped** fixture (pytest default).  Each test gets
    a fresh connection, a new transaction, and clean rollback on teardown.
    """
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


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def app() -> AsyncGenerator[FastAPI]:
    """Session-scoped FastAPI app.

    ``create_app()`` imports all routers, which cascades into hundreds of
    lazy imports.  Session-scoping avoids paying this cost per-test — the
    app is built once and reused across all integration tests.

    The ``get_async_session`` dependency override is NOT set here; it is
    applied per-test by the autouse ``_override_db_session`` fixture so
    that each test still gets its own function-scoped DB transaction.
    """
    from narrare.memory.dependencies import get_memory_client
    from narrare_core.memory._null_client import NullMemoryClient

    app = create_app(test_mode=True)

    async def override_memory_client():
        return NullMemoryClient()

    app.dependency_overrides[get_memory_client] = override_memory_client

    yield app

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(loop_scope="session", autouse=True)
async def _override_db_session(  # pyright: ignore[reportUnusedFunction]
    app: FastAPI,
    db_session: AsyncSession,
) -> AsyncGenerator[None]:
    """Override the async session dependency per-test.

    ``app`` is session-scoped (built once), but each test needs its own DB
    transaction.  This autouse fixture re-sets the ``get_async_session``
    override for every test function, pointing it at the fresh
    ``db_session`` that pytest created for this test.
    """

    async def _override():
        yield db_session

    app.dependency_overrides[get_async_session] = _override
    yield
    app.dependency_overrides.pop(get_async_session, None)


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient]:
    """Session-scoped test HTTP client (reused across tests).

    The underlying ``ASGITransport`` is stateless — each request goes
    through the same ``app``, which resolves ``get_async_session`` from
    the dependency override that ``_override_db_session`` set for the
    current test.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# Pre-computed bcrypt hash for "testpassword123" — avoids ~0.1s hash_password()
# call per test.  The hash is deterministic so caching is safe.
_cached_password_hash: str | None = None


def _get_test_password_hash() -> str:
    """Return cached bcrypt hash for the test password (computed once)."""
    global _cached_password_hash
    if _cached_password_hash is None:
        from narrare.auth.security import hash_password

        _cached_password_hash = hash_password("testpassword123")
    # Global narrowing does not persist across the hash_password() call above
    # (any function could rebind a module-level name), so narrow explicitly
    # before returning to satisfy pyright strict mode.
    assert _cached_password_hash is not None
    return _cached_password_hash


@pytest_asyncio.fixture(loop_scope="session")
async def auth_headers(client: AsyncClient, db_session: AsyncSession) -> dict[str, str]:
    """Create a test user and return authorization headers with valid token."""
    import uuid
    from datetime import UTC, datetime

    from narrare._app.config import get_settings
    from narrare.auth.models import User
    from narrare.auth.security import create_access_token

    # Create test user in the database with a unique email to prevent any
    # possible unique-constraint conflict across test runs (even when a prior
    # transaction rollback has an edge-case failure).
    user = User(
        id=uuid.uuid4(),
        email=f"test-{uuid.uuid4().hex[:12]}@example.com",
        hashed_password=_get_test_password_hash(),
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
