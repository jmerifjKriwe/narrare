"""Shared row reader for capability E2E suites.

Capability E2E tests read their own database through this helper instead of each
file redefining ``_rows``. The worker thread is required because pytest-asyncio
keeps a session loop running and ``asyncio.run`` refuses a second one in the
same thread. Engine creation and disposal stay per call, so a failed query never
leaks a connection.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.kernel.db.testsupport import url_for


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

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, run()).result()
