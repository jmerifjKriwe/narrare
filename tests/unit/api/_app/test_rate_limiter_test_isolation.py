"""Regression pin: module-level rate-limiter state must not leak across tests.

Cross-file 429 flakiness (CI, PR #201): the API rate limiters are
intentionally process-wide singletons (AR-05-02 — ``Limiter`` must
accumulate across requests or limits would never trigger), so in a shared
pytest-xdist worker (``pytest tests/unit/ -n auto --dist loadfile``) every
request through a limiter-protected route consumes the SAME in-memory
bucket. The series voice / voice-drift / consistency router tests alone
consume 19 requests from ``AI_ANALYSIS_LIMITER``'s 5/minute budget, so
whichever file runs next on that worker — e.g. the KB entity-resolution
router tests, which need exactly 5 — fails with spurious
``assert 429 == 200`` depending on the pytest-randomly seed.

The autouse fixture ``_reset_rate_limiter_buckets`` in
``tests/unit/conftest.py`` flushes every singleton bucket before each
test. The two parametrized cases here pin that wiring symmetrically:
EACH asserts a fresh 5-token budget at start, so whichever runs second
fails deterministically unless the fixture flushed the bucket in
between. Removing the fixture (or dropping ``AI_ANALYSIS_LIMITER`` from
its coverage) turns this file RED regardless of shuffle order.

Rate-limit ENFORCEMENT itself is pinned elsewhere (per-instance
accumulation within a single test): ``test_rate_limits.py``,
``test_rate_limiter_compat.py``, ``test_auth_rate_limits.py``.
"""

from __future__ import annotations

from typing import Final

import pytest

from narrare._app.rate_limits import AI_ANALYSIS_LIMITER

_RATE: Final[int] = 5
""" Governed default of ``AI_ANALYSIS_LIMITER`` (rate_limits.py:151). """

_KEY: Final[str] = "test-isolation-pin"
""" Bucket key — informational only (single shared in-memory bucket). """


@pytest.mark.parametrize("slot", [1, 2], ids=["first", "second"])
def test_analysis_limiter_budget_is_fresh_per_test(slot: int) -> None:
    """Start-of-test budget must be untouched by any earlier test.

    Asserts the full 5-request budget is available, which leaves the
    bucket exhausted — poisoning the sibling case unless the autouse
    fixture flushes between tests.
    """
    del slot  # only distinguishes the two symmetric order positions
    limiter = AI_ANALYSIS_LIMITER.limiter

    for _ in range(_RATE):
        assert limiter.try_acquire(_KEY, blocking=False) is True, (
            "AI_ANALYSIS_LIMITER budget was already consumed by an earlier "
            "test in this worker — module-level limiter state leaked across "
            "tests (the _reset_rate_limiter_buckets autouse fixture in "
            "tests/unit/conftest.py must flush it)."
        )
