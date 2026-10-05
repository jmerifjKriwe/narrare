"""Shared analysis-budget pacer for the bulk extraction job (ADR-092 D7a).

Spec §7: the batch runner acquires one slot per chapter on the SAME
``SelfPruningLimiter`` bucket that backs the interactive
``AI_ANALYSIS_LIMITER`` FastAPI dep, so a bulk pass and interactive
analysis share ONE budget governed by ``NARRARE_RATE_LIMIT_ANALYSIS``
(RULE-18b — no new settings surface; restart to apply).

Never blocks the event loop (plan invariant 4): the acquire is
``try_acquire_async(key, blocking=False)`` with an ``asyncio.sleep`` retry
loop — a blocking acquire would stall every request for up to a rate
window. The key is informational (single shared bucket — see the
``RateLimiter._identifier`` note in ``_app/rate_limiter_dep.py``); isolation
comes from separate limiter instances and there is deliberately only ONE
analysis instance.

The runner binds this module's :func:`acquire_analysis_pacer_slot` lazily
(``runner._resolve_pacer_acquire``); the pacer itself resolves its default
limiter eagerly at import — the hoisted raw handle already exists there.
"""

from __future__ import annotations

import asyncio
from typing import Final, Protocol

from narrare._app.rate_limits import AI_ANALYSIS_LIMITER_RAW
from narrare_core.settings import get_core_settings

#: Poll interval while a slot is denied — short enough for responsive
#: pacing, long enough not to spin the event loop.
PACER_POLL_SECONDS: Final[float] = 1.0


class PacerLimiter(Protocol):
    """Minimal structural seam the pacer needs.

    A Protocol instead of the concrete ``SelfPruningLimiter`` type so unit
    tests can inject a fake without a ``# type: ignore`` (RULE-23);
    ``SelfPruningLimiter`` satisfies it structurally, keeping the production
    default honest.
    """

    async def try_acquire_async(
        self,
        name: str = ...,
        weight: int = ...,
        blocking: bool = ...,
        timeout: int | float = ...,
    ) -> bool:
        """Attempt one slot acquire (production passes ``blocking=False``)."""
        ...


async def acquire_analysis_pacer_slot(
    key: str = "kb-bulk-extraction",
    limiter: PacerLimiter | None = None,
) -> None:
    """Cooperatively block until one shared-analysis-budget slot is acquired.

    Args:
        key: Informational bucket key (single shared bucket — the dep's
            ``_identifier`` note applies verbatim).
        limiter: Test injection seam; defaults to the hoisted raw handle
            :data:`narrare._app.rate_limits.AI_ANALYSIS_LIMITER_RAW` so the
            batch pacer and the interactive dep consume ONE budget.
    """
    # E2E test mode: disable all rate limiting (prevents false 429 failures),
    # mirroring the dep short-circuit in ``_app/rate_limiter_dep.py``.
    # NARRARE_E2E_TEST is owned by CoreSettings (ADR-071 §3) — read via
    # get_core_settings(), not os.environ.
    if get_core_settings().e2e_test:
        return
    effective = AI_ANALYSIS_LIMITER_RAW if limiter is None else limiter
    while not await effective.try_acquire_async(key, blocking=False):
        await asyncio.sleep(PACER_POLL_SECONDS)
