"""Shared fixtures for ``tests/unit/api/_app/``."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def no_e2e_test_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove ``NARRARE_E2E_TEST`` env var — breaks rate limit tests when set.

    The ``just`` command runner loads ``.env`` which sets
    ``NARRARE_E2E_TEST=1``.  The ``RateLimiter.__call__`` method checks this
    var at runtime and returns early (no rate limiting) when set — causing
    all rate-limit-enforcement tests (which expect 429) to fail.

    This fixture runs before every test in this directory, ensuring clean
    env state for rate limiter tests.  Tests that need ``NARRARE_E2E_TEST``
    can still use ``monkeypatch.setenv("NARRARE_E2E_TEST", "1")`` (as
    ``test_lifespan.py::test_e2e_test_mode_logs_message`` already does).
    """
    monkeypatch.delenv("NARRARE_E2E_TEST", raising=False)
