"""Capability driver framework — the contracts (plan Task 7).

- ``CapabilityContext`` — everything a driver may touch: the authenticated
  client, the corpus view, the run's novel/chapter ids, the timing
  config, and the run's raw-event sink.
- ``CapabilityResult`` — the typed outcome slot: ``status``
  (OK|ERROR|SKIPPED), the parsed payload, raw-event refs into the run
  sink, wall-time; SKIPPED and ERROR carry a ``reason``, OK must not.
- ``CapabilityDriver`` — the driver protocol (contract-first): every
  capability driver implements ``invoke(ctx) -> CapabilityResult``.

The three invocation-shape helpers (REST-JSON, SSE-collect with a total
deadline, poll-until-done; api-surface.md §7) live in
``benchmark.drivers.shapes`` — this module stays contract-only (RULE-04
split). All shape helpers record their HTTP exchanges into
``ctx.events`` as sanitized ``IngestEvent`` records
(``benchmark.ingest_events``) — ONE uniform, secret-free sink for ingest
and capability drivers, consumed by the Task 14 artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Final, Protocol

if TYPE_CHECKING:
    from collections.abc import Mapping

    from benchmark.client import BenchmarkClient
    from benchmark.corpus_loader import Corpus
    from benchmark.ingest_events import IngestEvent

API_V1_PREFIX: Final[str] = "/api/v1"
"""Path prefix every registry endpoint template is relative to (map §1)."""


def api_v1_path(endpoint_path: str) -> str:
    """Join a registry endpoint template onto the ``/api/v1`` prefix."""
    return f"{API_V1_PREFIX}{endpoint_path}"


class CapabilityStatus(StrEnum):
    """Outcome status of one capability invocation (plan Task 7)."""

    OK = "ok"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class CapabilityTimings:
    """Driver timing config — wired by the runner from the benchmark config.

    ``sse_deadline_seconds`` is the TOTAL stream deadline (T3 rider);
    ``poll_timeout_seconds``/``poll_interval_seconds`` bound the
    poll-until-done shape. All three must be strictly positive.
    """

    sse_deadline_seconds: float
    poll_timeout_seconds: float
    poll_interval_seconds: float

    def __post_init__(self) -> None:
        for field in ("sse_deadline_seconds", "poll_timeout_seconds", "poll_interval_seconds"):
            if getattr(self, field) <= 0:
                raise ValueError(f"{field} must be > 0, got {getattr(self, field)!r}")


@dataclass(frozen=True)
class CapabilityContext:
    """Everything a capability driver may touch during one invocation."""

    client: BenchmarkClient
    corpus: Corpus
    novel_id: str
    chapter_ids: Mapping[str, str]
    config: CapabilityTimings
    events: list[IngestEvent]


@dataclass(frozen=True)
class CapabilityResult:
    """Typed outcome slot of one capability invocation (plan Task 7).

    ``parsed`` holds the driver's typed/JSON payload slot (OK) or is
    None; ``raw_events`` are the refs of THIS invocation's recorded
    exchanges; ``reason`` is mandatory on SKIPPED/ERROR and forbidden on
    OK (a "successful" result with a reason is a contradiction).
    """

    cap_id: str
    status: CapabilityStatus
    parsed: object | None = None
    raw_events: tuple[IngestEvent, ...] = ()
    elapsed_seconds: float = 0.0
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.status is CapabilityStatus.SKIPPED and not self.reason:
            raise ValueError(f"{self.cap_id}: SKIPPED results must carry a reason")
        if self.status is CapabilityStatus.ERROR and not self.reason:
            raise ValueError(f"{self.cap_id}: ERROR results must carry a reason")
        if self.status is CapabilityStatus.OK and self.reason is not None:
            raise ValueError(f"{self.cap_id}: OK results must not carry a reason")

    @classmethod
    def ok(
        cls,
        cap_id: str,
        *,
        parsed: object | None,
        raw_events: tuple[IngestEvent, ...] = (),
        elapsed_seconds: float = 0.0,
    ) -> CapabilityResult:
        return cls(
            cap_id=cap_id,
            status=CapabilityStatus.OK,
            parsed=parsed,
            raw_events=raw_events,
            elapsed_seconds=elapsed_seconds,
        )

    @classmethod
    def error(
        cls,
        cap_id: str,
        *,
        reason: str,
        raw_events: tuple[IngestEvent, ...] = (),
        elapsed_seconds: float = 0.0,
    ) -> CapabilityResult:
        return cls(
            cap_id=cap_id,
            status=CapabilityStatus.ERROR,
            reason=reason,
            raw_events=raw_events,
            elapsed_seconds=elapsed_seconds,
        )

    @classmethod
    def skipped(cls, cap_id: str, *, reason: str) -> CapabilityResult:
        return cls(cap_id=cap_id, status=CapabilityStatus.SKIPPED, reason=reason)


class CapabilityDriver(Protocol):
    """Driver protocol (contract-first): one capability per implementation."""

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        """Execute the capability against ``ctx``; return the typed outcome."""
        ...


# ---------------------------------------------------------------------------
# Raw-event refs — slice THIS invocation's records out of the run sink
# ---------------------------------------------------------------------------


def mark_events(ctx: CapabilityContext) -> int:
    """Snapshot the sink length; pair with :func:`take_events`."""
    return len(ctx.events)


def take_events(ctx: CapabilityContext, cursor: int) -> tuple[IngestEvent, ...]:
    """The events appended since ``cursor`` — a result's raw-event refs."""
    return tuple(ctx.events[cursor:])
