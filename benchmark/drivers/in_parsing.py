"""Shared response parsing + guard for the IN-direction drivers (Task 8).

The cross-driver plumbing of ``benchmark.drivers.in_direction`` (RULE-04
split; the driver modules keep only per-capability logic):

- ``guarded`` — wraps one drive function: snapshots the raw-event cursor,
  times the invocation, and converts failures into typed outcomes —
  ``MissingTargetError`` → ``SKIPPED(structural)`` (an absent
  ingest-discovered target is a structural precondition, never an
  HTTP failure), transport/HTTP (``ApiError``), SSE deadline
  (``SseDeadlineError``), malformed frames (``SseParseError``) and
  response-shape/SSE-protocol drift (``StreamProtocolError`` and other
  ``LookupError``s) → ``ERROR`` with the failure as ``reason``.
- Strict response-shape accessors (``response_field``/``as_text``/…) —
  a payload that deviates from the verified API map raises
  ``StreamProtocolError`` instead of being silently coerced; the REAL
  response schemas (pydantic dumps) always carry their fields, including
  defaults, so strict presence checking is schema-faithful.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, cast

from benchmark.client import ApiError
from benchmark.drivers.base import CapabilityResult, mark_events, take_events
from benchmark.drivers.shapes import SseDeadlineError
from benchmark.sse import SseErrorEvent, SseParseError

if TYPE_CHECKING:
    from collections.abc import Callable

    from benchmark.drivers.base import CapabilityContext
    from benchmark.sse import SseTerminal

__all__ = [
    "MissingTargetError",
    "StreamProtocolError",
    "as_bool",
    "as_float",
    "as_int",
    "as_list",
    "as_opt_float",
    "as_opt_int",
    "as_opt_object",
    "as_opt_str_list",
    "as_opt_text",
    "as_str_tuple",
    "as_text",
    "check_terminal",
    "guarded",
    "require_target",
    "response_field",
]


class MissingTargetError(LookupError):
    """A driver's required ingest-discovered target is absent from the map."""


class StreamProtocolError(RuntimeError):
    """The response shape or SSE stream protocol drifted from the API map."""


def require_target(ctx: CapabilityContext, key: str) -> str:
    value = ctx.targets.get(key)
    if value is None:
        raise MissingTargetError(f"required target {key!r} missing from ctx.targets")
    return value


def response_field(body: object, key: str) -> object:
    if not isinstance(body, dict) or key not in body:
        raise StreamProtocolError(f"response shape drift: expected object with key {key!r}")
    return cast("dict[str, object]", body)[key]


def as_text(value: object) -> str:
    if isinstance(value, str):
        return value
    raise StreamProtocolError(f"response shape drift: expected string, got {type(value).__name__}")


def as_opt_text(value: object) -> str | None:
    if value is None or isinstance(value, str):
        return value
    raise StreamProtocolError(
        f"response shape drift: expected string|null, got {type(value).__name__}"
    )


def as_float(value: object) -> float:
    if isinstance(value, float):
        return value
    raise StreamProtocolError(f"response shape drift: expected number, got {type(value).__name__}")


def as_int(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise StreamProtocolError(f"response shape drift: expected integer, got {type(value).__name__}")


def as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    raise StreamProtocolError(f"response shape drift: expected boolean, got {type(value).__name__}")


def as_opt_object(value: object) -> dict[str, object] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return cast("dict[str, object]", value)
    raise StreamProtocolError(
        f"response shape drift: expected object|null, got {type(value).__name__}"
    )


def as_opt_int(value: object) -> int | None:
    if value is None or (isinstance(value, int) and not isinstance(value, bool)):
        return value
    raise StreamProtocolError(
        f"response shape drift: expected integer|null, got {type(value).__name__}"
    )


def as_opt_float(value: object) -> float | None:
    if value is None or isinstance(value, float):
        return value
    raise StreamProtocolError(
        f"response shape drift: expected number|null, got {type(value).__name__}"
    )


def as_opt_str_list(value: object) -> tuple[str, ...] | None:
    """Optional string list → tuple (record immutability), None passes through."""
    if value is None:
        return None
    return as_str_tuple(value)


def as_str_tuple(value: object) -> tuple[str, ...]:
    return tuple(as_text(item) for item in as_list(value, "string list"))


def as_list(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise StreamProtocolError(f"response shape drift: expected a {label}")
    return cast("list[object]", value)


def check_terminal(terminal: SseTerminal | None, cap_id: str) -> None:
    """Fail on a non-success terminal: in-band error or missing terminal."""
    if isinstance(terminal, SseErrorEvent):
        raise StreamProtocolError(
            f"in-band stream error ({cap_id}): {terminal.message} [{terminal.code}]"
        )
    if terminal is None:
        raise StreamProtocolError(f"stream ended without a terminal event ({cap_id})")


def guarded(
    cap_id: str,
    ctx: CapabilityContext,
    drive: Callable[[CapabilityContext], object],
) -> CapabilityResult:
    """Run one driver, converting failures into typed outcomes (module doc)."""
    cursor = mark_events(ctx)
    started = time.perf_counter()
    try:
        parsed = drive(ctx)
    except MissingTargetError as exc:
        return CapabilityResult.skipped(cap_id, reason=f"structural: {exc}")
    except (ApiError, SseDeadlineError, SseParseError, StreamProtocolError, LookupError) as exc:
        return CapabilityResult.error(
            cap_id,
            reason=str(exc),
            raw_events=take_events(ctx, cursor),
            elapsed_seconds=time.perf_counter() - started,
        )
    return CapabilityResult.ok(
        cap_id,
        parsed=parsed,
        raw_events=take_events(ctx, cursor),
        elapsed_seconds=time.perf_counter() - started,
    )
