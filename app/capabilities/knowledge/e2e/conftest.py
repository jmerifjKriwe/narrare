"""Full stack for the knowledge E2E: own database, real API, real web app.

The embedding provider is the real openai-compatible strategy pointed at a local
stand-in whose width a test can flip — that is the one boundary a fake may hold
(spec §Testing), and flipping the width is how the browser test changes models.
"""

import asyncio
from collections.abc import Iterator  # noqa: TC003
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.kernel.testing.stack import Stack, run_stack
from app.kernel.testing.vendor import EmbeddingsVendor, embeddings_vendor

DATABASE = "narrare_v2_knowledge_e2e"


def _truncate() -> None:
    """Runs in a worker thread: pytest-asyncio keeps a session loop running."""

    async def run() -> None:
        engine = create_async_engine(
            f"postgresql+asyncpg://narrare:narrare@localhost:5433/{DATABASE}"
        )
        async with engine.begin() as connection:
            await connection.execute(text("TRUNCATE chunks, documents CASCADE"))
        await engine.dispose()

    asyncio.run(run())


@pytest.fixture(scope="module")
def vendor() -> Iterator[EmbeddingsVendor]:
    with embeddings_vendor() as stand_in:
        yield stand_in


@pytest.fixture(scope="module")
def stack(vendor: EmbeddingsVendor) -> Iterator[Stack]:
    with run_stack(
        database=DATABASE,
        seed_user=True,
        env={
            "NARRE_EMBEDDING_PROVIDER": "openai-compatible",
            "NARRE_EMBEDDING_BASE_URL": f"{vendor.base_url}/v1",
            "NARRE_EMBEDDING_MODEL": "stand-in-model",
        },
    ) as running:
        yield running


@pytest.fixture(autouse=True)
def clean_corpus(vendor: EmbeddingsVendor) -> Iterator[None]:
    """Every test starts from an empty knowledge base at the vendor's width.

    The stack and the vendor live for the whole module; without this, one test's
    documents and width change would decide whether the next one passes.
    """
    vendor.set_width(384)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(_truncate).result()
    yield
