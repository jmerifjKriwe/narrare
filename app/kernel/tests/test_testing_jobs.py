"""The E2E job poller: one settle, or a named timeout.

The helper's contract is the one the four knowledge suites used to spell out
themselves — stop on ``done``/``failed``, return the row, and name the last
state when the window closes. These tests pin it without a stack, so a change
to the loop fails here rather than in a ten-minute browser run.
"""

from typing import TYPE_CHECKING, Any, cast

import pytest

from app.kernel.testing.jobs import wait_for_job

if TYPE_CHECKING:
    import httpx


class _Response:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict[str, Any]:
        return self._payload


class _Client:
    """Answers the statuses in order, then repeats the last one."""

    def __init__(self, statuses: list[str]) -> None:
        self._statuses = statuses
        self.calls = 0

    def get(self, url: str) -> _Response:
        status = self._statuses[min(self.calls, len(self._statuses) - 1)]
        self.calls += 1
        return _Response({"status": status})


def _waiting(statuses: list[str], timeout: float = 5.0) -> dict[str, Any]:
    return wait_for_job(cast("httpx.Client", _Client(statuses)), "job-1", timeout=timeout)


def test_the_poller_returns_the_settled_row() -> None:
    assert _waiting(["queued", "running", "done"])["status"] == "done"


def test_a_failed_row_stops_the_poll_the_same_way() -> None:
    """A failure is an outcome, not a reason to keep waiting; the caller asserts."""
    client = _Client(["running", "failed"])
    assert wait_for_job(cast("httpx.Client", client), "job-1")["status"] == "failed"
    assert client.calls == 2


def test_a_row_that_never_settles_names_the_timeout_and_the_last_state() -> None:
    with pytest.raises(TimeoutError, match=r"job-1 did not settle.*'running'"):
        _waiting(["running"], timeout=0.0)
