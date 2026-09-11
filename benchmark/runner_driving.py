"""Capability selection + driving loop (plan Task 15).

``selected_capabilities`` resolves the ``--capabilities`` filter against
the registry BEFORE any stack is created: an unknown id raises
``UnknownCapabilityError``, a duplicate id raises ``ValueError`` — both
fail fast without spinning up compose. An empty filter drives ALL 26
registry entries in registry order (PO decision F2=A).

``drive_capabilities`` builds ONE shared ``CapabilityContext`` (drivers
consume it read-only) and invokes each selected driver in order,
projecting every ``CapabilityResult`` into the artifact writer's
``CapabilityAnswer`` record (status, elapsed, reason, parsed payload).

Timing policy: the config template carries no timing section (template
parity validation), so the SSE/poll timings are pinned runner constants.
The SSE total deadline (T3 rider) must comfortably exceed an LLM-backed
analysis stream; the poll cadence mirrors the stack manager's health
polling.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from benchmark.artifacts_records import CapabilityAnswer
from benchmark.capabilities import CAPABILITIES, capability
from benchmark.drivers.base import CapabilityContext, CapabilityResult, CapabilityTimings

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from benchmark.capabilities_registry import CapabilitySpec
    from benchmark.client import BenchmarkClient
    from benchmark.config_schemas import BenchmarkConfig
    from benchmark.corpus_loader import Corpus
    from benchmark.drivers.base import CapabilityDriver
    from benchmark.ingest_events import IngestEvent

__all__ = [
    "POLL_INTERVAL_SECONDS",
    "POLL_TIMEOUT_SECONDS",
    "SSE_DEADLINE_SECONDS",
    "capability_timings",
    "drive_capabilities",
    "selected_capabilities",
]

SSE_DEADLINE_SECONDS: Final[float] = 600.0
"""Total SSE stream deadline (T3 rider) — LLM-backed analysis streams."""
POLL_TIMEOUT_SECONDS: Final[float] = 300.0
"""Poll-until-done overall budget (api-surface.md §7 shape 3)."""
POLL_INTERVAL_SECONDS: Final[float] = 2.0
"""Poll cadence — mirrors the stack manager's health-poll interval."""


def capability_timings(_config: BenchmarkConfig) -> CapabilityTimings:
    """Wire the pinned timing policy (module docstring) into the context."""
    return CapabilityTimings(
        sse_deadline_seconds=SSE_DEADLINE_SECONDS,
        poll_timeout_seconds=POLL_TIMEOUT_SECONDS,
        poll_interval_seconds=POLL_INTERVAL_SECONDS,
    )


def selected_capabilities(filter_ids: Sequence[str]) -> tuple[CapabilitySpec, ...]:
    """Resolve the capability filter against the registry (fail fast).

    Empty filter → every registry entry in registry order. Unknown ids
    raise ``UnknownCapabilityError``; duplicates raise ``ValueError`` —
    duplicate answers would violate the artifact writer's unique-cap-id
    contract at the very END of a run, so they are rejected up front.
    """
    if not filter_ids:
        return CAPABILITIES
    specs: list[CapabilitySpec] = []
    for cap_id in filter_ids:
        if any(spec.cap_id == cap_id for spec in specs):
            raise ValueError(f"duplicate capability id in --capabilities: {cap_id}")
        specs.append(capability(cap_id))
    return tuple(specs)


def drive_capabilities(
    client: BenchmarkClient,
    corpus: Corpus,
    novel_id: str,
    chapter_ids: Mapping[str, str],
    config: BenchmarkConfig,
    events: list[IngestEvent],
    selected: Sequence[CapabilitySpec],
    driver_for_fn: Callable[[str], CapabilityDriver],
    targets: Mapping[str, str],
) -> tuple[CapabilityAnswer, ...]:
    """Drive every selected capability once; project results to answers."""
    ctx = CapabilityContext(
        client=client,
        corpus=corpus,
        novel_id=novel_id,
        chapter_ids=chapter_ids,
        config=capability_timings(config),
        events=events,
        targets=targets,
    )
    return tuple(_answer(driver_for_fn(spec.cap_id).invoke(ctx)) for spec in selected)


def _answer(result: CapabilityResult) -> CapabilityAnswer:
    """Project one ``CapabilityResult`` into the artifact answer record."""
    return CapabilityAnswer(
        cap_id=result.cap_id,
        status=result.status,
        elapsed_seconds=result.elapsed_seconds,
        reason=result.reason,
        parsed=result.parsed,
    )
