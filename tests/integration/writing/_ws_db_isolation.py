"""DB-isolated ``TestClient`` for WebSocket integration tests.

TestClient runs the FastAPI app in a separate thread/event loop (anyio
portal).  The integration conftest's ``db_session`` fixture is async and
tied to the pytest-asyncio session event loop — it cannot be shared with
the portal's loop.  Without isolation, HTTP calls made through the
TestClient (e.g. ``_register_user``) commit ``UserProvider`` rows to the
real database.  Under pytest-xdist parallelism, those committed rows are
visible to other tests' transactions (PostgreSQL READ COMMITTED),
causing ``InvalidToken`` errors in the encryption-key rotation tests.

This module provides :func:`ws_db_test_client`, a context manager that:

1. Creates a dedicated engine, connection, and transaction **lazily**
   inside the TestClient's portal event loop (on first session resolution).
2. Overrides ``get_async_session`` on **both** surfaces:
   - ``app.dependency_overrides`` — for FastAPI ``Depends`` (HTTP endpoints)
   - ``unittest.mock.patch`` — for direct module-level imports (the WS
     handler in ``router_sessions.py`` calls ``get_async_session()`` directly,
     not via ``Depends``)
3. Shares a single :class:`AsyncSession` across all requests so that data
   created by HTTP endpoints (register user, create provider) is visible
   to the WebSocket handler.
4. Rolls back the root transaction on cleanup so no data reaches the DB.

Cleanup runs via ``client.portal.call()`` while the TestClient's portal
is still active, ensuring async disposal happens in the correct event loop.
"""

from __future__ import annotations

import contextlib
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Iterator

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy.ext.asyncio import (
        AsyncConnection,
        AsyncEngine,
        AsyncSession,
        AsyncTransaction,
    )


class _IsolationState:
    """Mutable container for lazily-created async DB resources.

    All fields start as ``None`` and are initialised on first
    :func:`_isolated_session` call, which runs inside the TestClient's
    portal event loop.
    """

    engine: AsyncEngine | None = None
    conn: AsyncConnection | None = None
    transaction: AsyncTransaction | None = None
    session: AsyncSession | None = None


@contextlib.contextmanager
def ws_db_test_client(app: FastAPI) -> Iterator[TestClient]:
    """Yield a ``TestClient`` with DB transaction isolation.

    Wraps ``TestClient(app)`` so that every DB operation — whether via
    FastAPI dependency injection or the direct ``get_async_session()``
    call in the WebSocket handler — runs inside a single transaction that
    is rolled back on exit.

    Args:
        app: A FastAPI application (typically ``create_app(test_mode=True)``).

    Yields:
        A ``TestClient`` whose HTTP and WebSocket requests share one
        isolated, rolled-back DB session.
    """
    from unittest.mock import patch

    from fastapi.testclient import TestClient

    from narrare._app.database import get_async_session as _original_fn

    state = _IsolationState()

    async def _isolated_session() -> AsyncGenerator[AsyncSession]:
        """Yield the shared session, creating DB resources on first call.

        Creates engine / connection / transaction / session lazily so they
        belong to the TestClient's portal event loop, not the pytest loop.
        Subsequent calls yield the SAME session, ensuring data created by
        HTTP endpoints is visible to the WebSocket handler.
        """
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from sqlalchemy.pool import NullPool

        if state.engine is None:
            db_url = os.environ.get(
                "TEST_DATABASE_URL",
                "postgresql+asyncpg://narrare:narrare@localhost:5433/narrare_test",
            )
            state.engine = create_async_engine(db_url, poolclass=NullPool)
            state.conn = await state.engine.connect()
            state.transaction = await state.conn.begin()
            state.session = AsyncSession(
                bind=state.conn,
                expire_on_commit=False,
            )

        # Narrowed by the lazy-init block above or by a prior call.
        assert state.session is not None
        yield state.session

    # Override BOTH surfaces:
    # 1. FastAPI Depends(get_async_session) — for HTTP endpoints.
    app.dependency_overrides[_original_fn] = _isolated_session

    # 2. Module-level get_async_session — the WS handler in
    #    router_sessions.py imports it directly, bypassing Depends.
    with (
        patch("narrare._app.database.get_async_session", new=_isolated_session),
        TestClient(app) as client,
    ):
        try:
            yield client
        finally:
            # Cleanup MUST run while the portal is still active so async
            # disposal happens in the correct event loop.
            portal = client.portal
            assert portal is not None  # guaranteed by TestClient.__enter__

            async def _cleanup() -> None:
                if state.session is not None:
                    with contextlib.suppress(Exception):
                        await state.session.close()
                if state.transaction is not None:
                    with contextlib.suppress(Exception):
                        await state.transaction.rollback()
                if state.conn is not None:
                    with contextlib.suppress(Exception):
                        await state.conn.close()
                if state.engine is not None:
                    with contextlib.suppress(Exception):
                        await state.engine.dispose()

            portal.call(_cleanup)

    app.dependency_overrides.pop(_original_fn, None)
