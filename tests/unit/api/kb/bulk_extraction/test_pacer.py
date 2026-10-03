"""Shared analysis-budget pacer tests (F2, ADR-092 D7a — spec §7).

Pins the D7a hoist: ONE ``SelfPruningLimiter`` bucket behind the
``AI_ANALYSIS_LIMITER`` FastAPI dep, with the bulk pacer acquiring on the
SAME raw instance (``AI_ANALYSIS_LIMITER_RAW``) — interactive + batch share
one budget governed by ``NARRARE_RATE_LIMIT_ANALYSIS`` (RULE-18b: no new
settings surface). Also pins the runner's lazy importlib binding
(``runner._resolve_pacer_acquire``) against the REAL pacer module — no
import monkeypatching — so a production dispatch resolves end-to-end.

The per-test bucket flush (``tests/unit/conftest.py``) keeps the real-limiter
tests independent of every other file on the worker.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import TYPE_CHECKING

from pyrate_limiter import Duration

from narrare._app import rate_limits
from narrare._app.rate_limiter_dep import SelfPruningLimiter
from narrare.kb.bulk_extraction import pacer, runner
from narrare.kb.bulk_extraction.pacer import (
    PACER_POLL_SECONDS,
    acquire_analysis_pacer_slot,
)

if TYPE_CHECKING:
    import pytest


class TestSharedBudget:
    """D7a: the interactive dep and the batch pacer hit the SAME bucket."""

    def test_dep_wraps_the_raw_instance(self) -> None:
        # One budget: the FastAPI dep and the pacer MUST hit the same bucket.
        assert rate_limits.AI_ANALYSIS_LIMITER.limiter is rate_limits.AI_ANALYSIS_LIMITER_RAW

    def test_raw_instance_is_self_pruning(self) -> None:
        """The hoisted handle is the no-sweeper-thread subclass (same as the dep)."""
        assert isinstance(rate_limits.AI_ANALYSIS_LIMITER_RAW, SelfPruningLimiter)

    def test_governed_default_unchanged(self) -> None:
        """The hoist is behavior-preserving: same governed count and window."""
        assert rate_limits.RATE_LIMIT_ANALYSIS_DEFAULT == 5
        assert rate_limits.ANALYSIS_RATE.limit == 5
        assert rate_limits.ANALYSIS_RATE.interval == Duration.MINUTE


class _FakeLimiter:
    """Non-pyrate stand-in: denies until ``denials`` exhausted, then admits."""

    def __init__(self, denials: int) -> None:
        self._denials = denials
        self.calls = 0
        self.names: list[str] = []

    async def try_acquire_async(
        self,
        name: str = "p",
        weight: int = 1,
        blocking: bool = True,
        timeout: int | float = -1,
    ) -> bool:
        self.calls += 1
        self.names.append(name)
        if self._denials > 0:
            self._denials -= 1
            return False
        return True


class TestAcquireLoop:
    """Non-blocking acquire + sleep retry — never blocks the event loop."""

    async def test_retries_until_admitted_without_loop_block(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(pacer, "PACER_POLL_SECONDS", 0.01)
        fake = _FakeLimiter(denials=2)
        await asyncio.wait_for(acquire_analysis_pacer_slot(limiter=fake), timeout=5)
        assert fake.calls == 3

    async def test_key_is_forwarded_to_the_limiter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(pacer, "PACER_POLL_SECONDS", 0.01)
        fake = _FakeLimiter(denials=0)
        await asyncio.wait_for(
            acquire_analysis_pacer_slot(key="kb-bulk-extraction", limiter=fake), timeout=5
        )
        assert fake.names == ["kb-bulk-extraction"]

    async def test_poll_interval_is_short(self) -> None:
        assert 0 < PACER_POLL_SECONDS <= 1.0


class TestE2EShortCircuit:
    """e2e_test mode skips the limiter entirely — mirrors the dep path."""

    async def test_e2e_mode_returns_without_touching_the_limiter(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(pacer, "get_core_settings", lambda: SimpleNamespace(e2e_test=True))
        fake = _FakeLimiter(denials=999)  # would deny forever if consulted
        await asyncio.wait_for(acquire_analysis_pacer_slot(limiter=fake), timeout=1)
        assert fake.calls == 0


class TestDefaultResolution:
    """``limiter=None`` resolves to the hoisted raw handle (the shared bucket)."""

    async def test_default_binds_the_hoisted_raw_handle(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake = _FakeLimiter(denials=0)
        monkeypatch.setattr(pacer, "AI_ANALYSIS_LIMITER_RAW", fake)
        await asyncio.wait_for(acquire_analysis_pacer_slot(), timeout=5)
        assert fake.calls == 1


class TestRunnerBinding:
    """The runner's lazy importlib seam resolves against the REAL module.

    Only the cached seam attribute is reset (the same re-arm the runner tests
    do per test) — the ``importlib.import_module`` target itself is NOT
    monkeypatched, so this proves a production dispatch binds the shipped
    pacer (end-to-end D7a wiring).
    """

    def test_resolve_pacer_acquire_binds_the_real_pacer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(runner, "_pacer_acquire", None)
        resolved = runner._resolve_pacer_acquire()
        assert resolved is acquire_analysis_pacer_slot

    async def test_resolved_default_is_awaitable_end_to_end(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(runner, "_pacer_acquire", None)
        monkeypatch.setattr(pacer, "PACER_POLL_SECONDS", 0.01)
        acquire = runner._resolve_pacer_acquire()
        # One real acquire against the real shared bucket (flushed per test);
        # an empty bucket admits on the first try.
        await asyncio.wait_for(acquire(), timeout=5)
