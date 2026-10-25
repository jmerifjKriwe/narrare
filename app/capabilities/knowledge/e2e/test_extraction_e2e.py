"""Extraction's durability: an enqueued job survives an API restart.

The job is enqueued through the running API, then the API process goes down
and comes back up. The row in Postgres is the only thing that carries the work
across that boundary (spec §9 D10) — whether the lane ran the handler before
the polite stop or the fresh lane picks the queued row up after the restart,
the outcome must be the same: a done job and a queryable review queue.
"""

from time import monotonic, sleep
from typing import TYPE_CHECKING

import httpx
import pytest

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

API = "http://127.0.0.1:8000"

CHAPTER_BODY = (
    "Mira betrat das alte Haus am See. Der Leuchtturm schwieg, und Nebel zog über das Dorf."
)


def test_an_enqueued_extraction_completes_across_an_api_restart(stack: Stack) -> None:
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
        assert job["result"] == {"suggestions": 3}

        listed = client.get(
            f"/api/knowledge/novels/{novel.json()['id']}/suggestions",
            params={"status": "pending"},
        )
        listed.raise_for_status()
        suggestions = listed.json()
        assert [suggestion["name"] for suggestion in suggestions] == ["Mira", "Haus", "See"]
        assert all(suggestion["status"] == "pending" for suggestion in suggestions)
