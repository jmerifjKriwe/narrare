"""Extraction's durability: an enqueued job survives an API restart.

The job is enqueued through the running API, then the API process goes down
and comes back up. The row in Postgres is the only thing that carries the work
across that boundary (spec §9 D10) — whether the lane ran the handler before
the polite stop or the fresh lane picks the queued row up after the restart,
the outcome must be the same: a done job and a queryable review queue.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from time import monotonic, sleep
from typing import TYPE_CHECKING
from uuid import UUID

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.kernel.db.testsupport import url_for

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

API = "http://127.0.0.1:8000"

DATABASE = "narrare_v2_knowledge_e2e"  # the stack's own database (e2e/conftest.py)

CHAPTER_BODY = (
    "Mira betrat das alte Haus am See. Der Leuchtturm schwieg, und Nebel zog über das Dorf."
)


def _extraction_audit(novel_id: str) -> tuple[str, str, int, int, float | None]:
    """The llm_calls row of the test's novel, from the stack's database.

    Runs in a worker thread: pytest-asyncio keeps a session loop running, and
    asyncio.run refuses to start a second one in the same thread.
    """

    async def run() -> tuple[str, str, int, int, float | None] | None:
        """Read the novel audit from a fresh async engine, returning None when absent."""
        engine = create_async_engine(url_for(DATABASE))
        async with engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        "SELECT status, task_key, input_tokens, output_tokens, cost_usd"
                        " FROM llm_calls WHERE novel_id = :novel_id"
                    ),
                    {"novel_id": UUID(novel_id)},
                )
            ).one_or_none()
        await engine.dispose()
        if row is None:
            return None
        return (row.status, row.task_key, row.input_tokens, row.output_tokens, row.cost_usd)

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, run()).result() or ("", "", 0, 0, 0.0)


def test_an_enqueued_extraction_completes_across_an_api_restart(stack: Stack) -> None:
    """Verify an API restart preserves extraction work, suggestions, and the successful audit."""
    with httpx.Client(base_url=API, timeout=30) as client:
        novel = client.post("/api/writing/novels", json={"title": "Der Nebel"})
        novel.raise_for_status()
        chapter = client.post(
            f"/api/writing/novels/{novel.json()['id']}/chapters", json={"title": "Ankunft"}
        )
        chapter.raise_for_status()
        written = client.put(
            f"/api/writing/chapters/{chapter.json()['id']}", json={"body": CHAPTER_BODY}
        )
        written.raise_for_status()

        accepted = client.post(
            f"/api/knowledge/extraction/{novel.json()['id']}",
            json={"chapter_id": chapter.json()["id"]},
        )
        assert accepted.status_code == 202
        job_id = accepted.json()["job_id"]

    # The process boundary. The stop is polite — a handler mid-flight gets to
    # record its outcome — so the row is queued or done here, never lost.
    stack.stop_api()
    with pytest.raises(httpx.ConnectError):
        httpx.get(f"{API}/openapi.json", timeout=5)  # really down, not just quiet
    stack.start_api()

    with httpx.Client(base_url=API, timeout=30) as client:
        deadline = monotonic() + 60  # the lane polls twice a second when idle
        while True:
            response = client.get(f"/api/jobs/{job_id}")
            response.raise_for_status()
            job = response.json()
            if job["status"] in {"done", "failed"} or monotonic() >= deadline:
                break
            sleep(0.5)
        assert job["status"] == "done", f"the restart lost the job: {job}"
        assert job["progress"] == 100
        assert job["result"] == {"suggestions": 3, "truncated": False}

        listed = client.get(
            f"/api/knowledge/novels/{novel.json()['id']}/suggestions",
            params={"status": "pending"},
        )
        listed.raise_for_status()
        suggestions = listed.json()
        assert [suggestion["name"] for suggestion in suggestions] == ["Mira", "Haus", "See"]
        assert all(suggestion["status"] == "pending" for suggestion in suggestions)

    # The call the handler made is audited in the same real database (plan
    # §3.4): one ok extraction for this novel, tokens counted, cost NULL.
    status, task_key, input_tokens, output_tokens, cost_usd = _extraction_audit(novel.json()["id"])
    assert task_key == "knowledge.extract-entities"
    assert status == "ok"
    assert input_tokens > 0
    assert output_tokens > 0
    assert cost_usd is None
