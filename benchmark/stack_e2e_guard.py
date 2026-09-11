"""E2E-test-mode honesty gate for the benchmark (rehearsal finding #6).

The spawned API subprocess inherits the shell environment, and
pydantic-settings lets a repo-root ``.env`` leak into ``CoreSettings``
(ADR-071 — lru-cached at startup). A ``.env`` with
``NARRARE_E2E_TEST=1`` silently switches ALL LLM providers to
``TestModel``, so the benchmark would "succeed" while measuring canned
output.

Two defenses (belt and braces — the stack pins ``NARRARE_E2E_TEST=false``
in the subprocess env; see ``stack_hybrid._start_uvicorn``):

1. Env pin (prevention): a real env var beats any ``.env`` file in
   pydantic-settings precedence.
2. :func:`ensure_not_e2e_test_mode` (detection — this module):
   re-verifies the OBSERVED startup behaviour by scanning the captured
   uvicorn log for the ``e2e_test_mode_active`` marker that
   ``narrare._app.lifespan`` emits when test mode is actually on, and
   refuses before any LLM work happens. Honest gate — no trust in env
   plumbing alone.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from benchmark.stack_common import StackError

if TYPE_CHECKING:
    from pathlib import Path

E2E_TEST_MODE_MARKER: Final[str] = "e2e_test_mode_active"


def ensure_not_e2e_test_mode(log_path: Path) -> None:
    """Raise unless the uvicorn log shows a REAL (non-TestModel) API.

    Scans the whole captured startup log for the lifespan's
    ``e2e_test_mode_active`` marker. An unreadable log is tolerated:
    this gate only ever ADDS a failure mode, never masks one (the env
    pin still applies, and the health-wait already surfaces log tails
    on startup failure).
    """
    try:
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    if E2E_TEST_MODE_MARKER in log_text:
        raise StackError(
            "API started in E2E test mode (TestModel) — benchmark refuses "
            "to measure canned output; check NARRARE_E2E_TEST / .env"
        )
