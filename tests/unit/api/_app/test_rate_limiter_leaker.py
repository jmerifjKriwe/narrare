"""Regression pin: rate-limit construction must not spawn background threads.

pyrate-limiter 4.x's default ``Limiter(Rate(...))`` construction spawns one
daemon thread — ``"PyrateLimiter's Leaker"``, each running its own asyncio
event loop — **per Limiter instance** (``SingleBucketFactory`` defaults to
``schedule_leak=True``, which starts a Leaker thread at construction; see
pyrate_limiter ``limiter.py`` and ``abstracts/bucket.py`` in the installed
package). With the 8 module-level limiters under
``narrare._app.rate_limits`` and ``narrare.auth.router``, that cost 8 threads
+ 8 event loops + their fds in every process importing those modules —
including every test process.

The fix under test: all in-memory limiters are built as
:class:`narrare._app.rate_limiter_dep.SelfPruningLimiter`, which disables the
background sweeper and prunes expired items at acquire time instead. For the
sliding-window admit decision this is semantically identical (stale items are
never counted by ``InMemoryBucket.put``), and the bucket stays hard-bounded
to roughly one rate window's worth of admitted requests.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import time
from pathlib import Path
from typing import Final

from pyrate_limiter import Duration, InMemoryBucket, Limiter, Rate, SingleBucketFactory

from narrare._app.rate_limiter_dep import SelfPruningLimiter
from narrare._app.rate_limits import (
    AI_ANALYSIS_LIMITER,
    AI_LIGHT_LIMITER,
    AI_PROMPT_LIVE_TEST_LIMITER,
    AI_WRITE_LIMITER,
    AI_WS_LIMITER,
    SETUP_MODELS_LIMITER,
)
from narrare.auth.router import (  # pyright: ignore[reportPrivateUsage]
    _LOGIN_LIMITER,
    _REGISTER_LIMITER,
)

_SHORT_WINDOW: Final[int] = Duration.SECOND * 10
#: 50 ms window — small enough to expire items quickly in tests.
_TINY_WINDOW: Final[int] = Duration.SECOND.value // 20
#: Definitely longer than ``_TINY_WINDOW`` so items are provably expired.
_PRUNE_SLEEP: Final[float] = 0.2

#: All 8 module-level limiter instances across both consumer modules.
_MODULE_LEVEL_LIMITERS: Final[tuple[Limiter, ...]] = (
    AI_WRITE_LIMITER.limiter,
    AI_ANALYSIS_LIMITER.limiter,
    AI_LIGHT_LIMITER.limiter,
    SETUP_MODELS_LIMITER.limiter,
    AI_PROMPT_LIVE_TEST_LIMITER.limiter,
    AI_WS_LIMITER,
    _REGISTER_LIMITER.limiter,
    _LOGIN_LIMITER.limiter,
)


class TestNoBackgroundSweeper:
    """The pyrate Leaker thread must never exist for our limiters."""

    def test_importing_rate_limit_modules_spawns_no_leaker_threads(self) -> None:
        """Fresh-interpreter observable: import both consumer modules, count
        ``"Leaker"`` threads. Pinned in a subprocess because Leaker threads
        live for the whole process lifetime — a bare ``Limiter`` constructed
        anywhere else in this pytest process would otherwise pollute the
        assertion."""
        repo_root = Path(__file__).resolve().parents[4]
        probe = (
            "import threading\n"
            "import narrare._app.rate_limits\n"
            "import narrare.auth.router\n"
            "leakers = [t.name for t in threading.enumerate() if 'Leaker' in t.name]\n"
            "print(leakers)\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
        assert "Leaker" not in result.stdout, result.stdout

    def test_module_level_limiters_have_no_background_sweeper(self) -> None:
        """Structural guard: pyrate creates the Leaker lazily inside
        ``BucketFactory.schedule_leak`` and stores it as ``factory._leaker``.
        With ``schedule_leak=False`` it must stay ``None`` forever."""
        for limiter in _MODULE_LEVEL_LIMITERS:
            assert limiter.bucket_factory._leaker is None  # pyright: ignore[reportPrivateUsage]


class TestSelfPruningLimiter:
    """SelfPruningLimiter behaves like a Limiter, minus the thread."""

    def test_is_a_limiter(self) -> None:
        """Is-a-Limiter so it slots into ``RateLimiter`` and type annotations
        expecting ``pyrate_limiter.Limiter``."""
        assert isinstance(SelfPruningLimiter(Rate(3, _SHORT_WINDOW)), Limiter)

    def test_enforces_rate(self) -> None:
        """Enforcement parity: 3 admitted, 4th rejected within the window."""
        limiter = SelfPruningLimiter(Rate(3, _SHORT_WINDOW))
        key = "leaker-test:enforce"
        for _ in range(3):
            assert limiter.try_acquire(key, blocking=False) is True
        assert limiter.try_acquire(key, blocking=False) is False

    def test_prunes_expired_items_on_sync_acquire(self) -> None:
        """After the window passes, the next acquire drops expired items —
        bucket holds only the new item, not both."""
        limiter = SelfPruningLimiter(Rate(1, _TINY_WINDOW))
        key = "leaker-test:prune-sync"
        assert limiter.try_acquire(key, blocking=False) is True
        time.sleep(_PRUNE_SLEEP)
        assert limiter.try_acquire(key, blocking=False) is True
        factory = limiter.bucket_factory
        assert isinstance(factory, SingleBucketFactory)
        bucket = factory.bucket
        assert isinstance(bucket, InMemoryBucket)
        assert bucket.count() == 1

    async def test_prunes_expired_items_on_async_acquire(self) -> None:
        """Same prune guarantee on the async path used by the FastAPI dep."""
        limiter = SelfPruningLimiter(Rate(1, _TINY_WINDOW))
        key = "leaker-test:prune-async"
        assert await limiter.try_acquire_async(key, blocking=False) is True
        await asyncio.sleep(_PRUNE_SLEEP)
        assert await limiter.try_acquire_async(key, blocking=False) is True
        factory = limiter.bucket_factory
        assert isinstance(factory, SingleBucketFactory)
        bucket = factory.bucket
        assert isinstance(bucket, InMemoryBucket)
        assert bucket.count() == 1
