"""Shared database helpers for capability E2E suites.

Capability E2E tests read and reset their own database through these helpers
instead of each file redefining the plumbing. The worker thread is required
because pytest-asyncio keeps a session loop running and ``asyncio.run`` refuses
a second one in the same thread. Engine creation and disposal stay per call,
so a failed query never leaks a connection.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.kernel.db.testsupport import url_for

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine


def _off_loop[T](run: Callable[[], Coroutine[Any, Any, T]]) -> T:
    """One worker thread per call, off pytest-asyncio's session loop."""
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, run()).result()


def rows(
    database: str, statement: str, params: dict[str, Any] | None = None
) -> list[tuple[Any, ...]]:
    """Run ``statement`` against ``database`` and return the rows as tuples."""

    async def run() -> list[tuple[Any, ...]]:
        engine = create_async_engine(url_for(database))
        try:
            async with engine.connect() as connection:
                return [
                    tuple(each) for each in await connection.execute(text(statement), params or {})
                ]
        finally:
            await engine.dispose()

    return _off_loop(run)


def reset(database: str) -> None:
    """Empty every user table — back to an uninstalled instance.

    The cascade takes the tables' rows, so the list of tables never has to be
    hand-kept (see follow-up #361). ``alembic_version`` stays: the schema is
    the suite's, only its contents reset.
    """

    async def run() -> None:
        engine = create_async_engine(url_for(database))
        try:
            async with engine.begin() as connection:
                result = await connection.execute(
                    text(
                        "SELECT tablename FROM pg_tables "
                        "WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
                    )
                )
                tables = [row[0] for row in result]
                if tables:
                    await connection.execute(
                        text("TRUNCATE " + ", ".join(f'"{t}"' for t in tables) + " CASCADE")
                    )
        finally:
            await engine.dispose()

    _off_loop(run)
