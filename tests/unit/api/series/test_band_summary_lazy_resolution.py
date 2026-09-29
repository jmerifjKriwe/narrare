"""Lazy wiring contract for ``build_band_summary_service`` (ADR-086 L25).

The factory (``series/dependencies_band_summary.py::
build_band_summary_service``) wires a ``LazyModelResolution`` around the
SUMMARIZE routing cascade plus a deferred model-runtime composition awaiting
BOTH cascades (routing + token limits — RULE-18/18b: sources unchanged, only
timing moves; the M-budget / S4b shape). This file pins the FACTORY-side
contract:

- no resolution at construction (0 cascade calls),
- first use runs BOTH cascades exactly once with the eager factory's
  verbatim arguments, idempotent afterwards (``ensure_resolved``),
- the eager factory's verbatim composition (``temperature=0.3``,
  ``max_tokens=limits.output_limit``, per-user credentials) lands on the
  frozen runtime — WHAT unchanged, only WHEN.

The L25 background-task invariant (the closure captures the in-process
task's own session; first use before session close) and the service-side
first-use contract live in
``test_band_summary_task_first_use.py``. Mirrors
``test_series_history_preview_service_lazy_resolution.py`` (L27 M-budget
precedent).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.series._band_summary_support import BandSummaryModelRuntime
from narrare_core.llm.intents import LLMIntent

from ._band_summary_test_helpers import BandSummaryLazyWiringHarness

pytestmark = pytest.mark.asyncio


def _build(**kwargs: Any) -> Any:
    from narrare.series.dependencies_band_summary import build_band_summary_service

    args: dict[str, Any] = {
        "session": MagicMock(spec=AsyncSession, name="session"),
        **kwargs,
    }
    args.setdefault("user_id", uuid4())
    args.setdefault("novel_id", uuid4())
    return build_band_summary_service(**args)


class TestFactoryLazyWiring:
    """ADR-086 L25 — no resolution at construction; both cascades at first use."""

    async def test_no_resolution_at_construction(self) -> None:
        """Construction must not touch either cascade (0 resolve + 0 limits)."""
        async with BandSummaryLazyWiringHarness() as harness:
            await _build()

        assert harness.resolver.resolve.await_args_list == []
        assert harness.limits_service.calls == []

    async def test_first_use_resolves_both_cascades_with_verbatim_args(self) -> None:
        """First use runs BOTH cascades once, with the eager factory's exact
        arguments (SUMMARIZE / user / novel — routing; str-cast ids — limits).
        """
        user_id, novel_id = uuid4(), uuid4()
        async with BandSummaryLazyWiringHarness() as harness:
            service = await _build(user_id=user_id, novel_id=novel_id)
            assert harness.resolver.resolve.await_args_list == []

            runtime = await service.ensure_resolved()

            assert harness.resolver.resolve.await_args_list == [
                ((LLMIntent.SUMMARIZE, user_id, novel_id),)
            ]
            assert harness.limits_service.calls == [
                {"user_id": str(user_id), "project_id": str(novel_id)}
            ]
            assert runtime.api_key == "sk-user-key"
            assert runtime.base_url == "https://u.example/v1"

    async def test_ensure_resolved_composes_once_and_is_idempotent(self) -> None:
        """Repeat first use hits the cache — cascade counts stay at exactly 1."""
        async with BandSummaryLazyWiringHarness() as harness:
            service = await _build()

            first = await service.ensure_resolved()
            second = await service.ensure_resolved()

            assert first is second
            assert harness.resolver.resolve.await_count == 1
            assert len(harness.limits_service.calls) == 1

    async def test_composition_applies_eager_overlay_exactly_once(self) -> None:
        """Timing-only invariant: the frozen runtime carries the eager
        factory's verbatim sampling overlay (temperature 0.3, cascade
        ``output_limit``) over the resolved config — no other transformation.
        """
        async with BandSummaryLazyWiringHarness():
            service = await _build()
            runtime = await service.ensure_resolved()

        assert isinstance(runtime, BandSummaryModelRuntime)
        assert runtime.config.temperature == 0.3
        assert runtime.config.max_tokens == 2048
        # Untouched cascade passthroughs:
        assert runtime.config.provider_name == "zai"
        assert runtime.config.model_id == "glm-4.7"
        assert runtime.api_key == "sk-user-key"
