"""The consistency check's durability: an enqueued job survives an API restart.

The mirror of the extraction proof for the second job kind: the check is
enqueued through the running API, the process goes down and comes back up,
and the row in Postgres is the only thing that carries the work across that
boundary (spec §9 D10) — whether the lane ran the handler before the polite
stop or the fresh lane picks the queued row up after the restart, the outcome
must be the same: a done job and a queryable findings queue.
"""

from time import monotonic, sleep
from typing import TYPE_CHECKING

import httpx
import pytest

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

API = "http://127.0.0.1:8000"

# Two chapters that disagree about Mira's age; the texts steer the fake
# provider's contradiction derivation, the way extraction's text steers names.
# The titles stay number-free: the fake's passage assembly carries every
# heading after the first marker inside a passage, and a numbered title would
# feed the derivation a (word, number) pair of its own.
CONTRADICTING_BODIES = (
    ("Ankunft", "Mira ist 34 Jahre alt und kennt das Dorf."),
    ("Später", "Später steht geschrieben: Mira ist 37 und will fort."),
)


def test_an_enqueued_check_completes_across_an_api_restart(stack: Stack) -> None:
    with httpx.Client(base_url=API, timeout=30) as client:
        novel = client.post("/api/writing/novels", json={"title": "Der Nebel"})
        novel.raise_for_status()
        for title, body in CONTRADICTING_BODIES:
            chapter = client.post(
                f"/api/writing/novels/{novel.json()['id']}/chapters",
                json={"title": title},
            )
            chapter.raise_for_status()
            written = client.put(
                f"/api/writing/chapters/{chapter.json()['id']}", json={"body": body}
            )
            written.raise_for_status()

        accepted = client.post(f"/api/knowledge/consistency/{novel.json()['id']}")
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
        assert job["result"] == {"findings": 1}

        listed = client.get(
            f"/api/knowledge/novels/{novel.json()['id']}/findings",
            params={"status": "pending"},
        )
        listed.raise_for_status()
        findings = listed.json()
        assert len(findings) == 1
        assert findings[0]["summary"] == "Mira: 34 vs. 37"
        assert all(finding["status"] == "pending" for finding in findings)
