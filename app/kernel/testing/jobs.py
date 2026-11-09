"""Wait for a background job the way a caller of the product would.

The worker rides the API process and settles its row in Postgres; a test that
enqueued through the API has no event to subscribe to, only that row. The
knowledge E2E suites each polled it with a copy of a bounded loop — two
shapes, two timeouts, and a deadline whose ``break`` left the caller's own
assert to explain the timeout. One helper here: poll, stop on
``done``/``failed``, and name the last state when the window closes.
"""

from time import monotonic, sleep
from typing import Any

import httpx

# Half the idle lane's own interval (``IDLE_SLEEP = 0.5``, kernel jobs
# runtime), so a settle is seen on the next turn rather than racing the
# worker.
POLL_INTERVAL_S = 0.25


def _unsettled(job_id: str, timeout: float, last: dict[str, Any]) -> str:
    return f"job {job_id} did not settle within {timeout:.0f}s (last: {last})"


def wait_for_job(client: httpx.Client, job_id: str, *, timeout: float = 60.0) -> dict[str, Any]:
    """Poll ``/api/jobs/{job_id}`` until it settles, or fail naming the last state.

    Every request is bounded by what is left of the window: the client's own
    timeout can outlast it, and a request that hangs would otherwise block
    past the deadline this helper promises. Returns the row as last read; the
    caller asserts what it expects of the outcome, the way the product's own
    caller does.
    """
    deadline = monotonic() + timeout
    last: dict[str, Any] = {}
    while (remaining := deadline - monotonic()) > 0:
        try:
            response = client.get(f"/api/jobs/{job_id}", timeout=remaining)
        except httpx.TimeoutException as error:
            raise TimeoutError(_unsettled(job_id, timeout, last)) from error
        response.raise_for_status()
        last = response.json()
        if last["status"] in {"done", "failed"}:
            return last
        sleep(min(POLL_INTERVAL_S, max(deadline - monotonic(), 0.0)))
    raise TimeoutError(_unsettled(job_id, timeout, last))
