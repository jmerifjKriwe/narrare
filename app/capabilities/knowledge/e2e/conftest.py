"""Full stack for the knowledge E2E: own database, real API, real web app.

Hebel 2: stack acquired once per worker and reused across knowledge modules.
The embeddings stand-in is also cached per worker so its base URL stays stable
for the API process's lifetime.
"""

import asyncio
from collections.abc import Iterator  # noqa: TC003
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.kernel.db import testsupport
from app.kernel.db.testsupport import url_for
from app.kernel.testing.stack import Stack, acquire_stack
from app.kernel.testing.vendor import EmbeddingsVendor, embeddings_vendor

DATABASE = testsupport.test_database("narrare_v2_knowledge_e2e")

# Worker-process-wide cache of the embeddings stand-in (see Hebel 2).
_VENDOR: EmbeddingsVendor | None = None


def _vendor() -> EmbeddingsVendor:
    global _VENDOR
    if _VENDOR is None:
        ctx = embeddings_vendor()
        _VENDOR = ctx.__enter__()  # type: ignore[union-attr]
        # keep context alive for process lifetime
        import atexit

        atexit.register(ctx.__exit__, None, None, None)
    return _VENDOR


def _truncate() -> None:
    async def run() -> None:
        engine = create_async_engine(url_for(DATABASE))
        async with engine.begin() as connection:
            await connection.execute(text("TRUNCATE chunks, documents CASCADE"))
        await engine.dispose()

    asyncio.run(run())


@pytest.fixture(scope="module")
def vendor() -> Iterator[EmbeddingsVendor]:
    yield _vendor()


@pytest.fixture(scope="module")
def stack(vendor: EmbeddingsVendor) -> Iterator[Stack]:
    running = acquire_stack(
        "knowledge",
        database=DATABASE,
        seed_user=True,
        env={
            "NARRE_EMBEDDING_PROVIDER": "openai-compatible",
            "NARRE_EMBEDDING_BASE_URL": f"{vendor.base_url}/v1",
            "NARRE_EMBEDDING_MODEL": "stand-in-model",
        },
    )
    yield running


@pytest.fixture(autouse=True)
def clean_corpus(vendor: EmbeddingsVendor) -> Iterator[None]:
    vendor.set_width(384)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(_truncate).result()
    yield
